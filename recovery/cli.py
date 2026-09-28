"""Backup a PostgreSQL snapshot, then prove it can be restored elsewhere."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

import psycopg
from psycopg import sql

NAME = re.compile(r'snapshot_[0-9a-f]{32}')
ROW_SQL = ('SELECT id::text, title, severity, status, version::text, '
           'created_at::text, updated_at::text FROM public.incidents ORDER BY id')


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        with temp.open('x') as file:
            json.dump(value, file, indent=2, sort_keys=True)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def fingerprint(connection):
    result = hashlib.sha256()
    count = 0
    # Server-side cursor avoids holding the entire table in client memory.
    with connection.cursor(name='recovery_fingerprint') as cursor:
        cursor.execute(ROW_SQL)
        for row in cursor:
            result.update(json.dumps(list(row), ensure_ascii=False, separators=(',', ':')).encode())
            result.update(b'\n')
            count += 1
    return {'rows': count, 'sha256': result.hexdigest()}


def config(target=False, database=None):
    prefix = 'RESTORE_' if target else 'PG'
    values = {
        'host': os.environ.get('RESTORE_HOST' if target else 'PGHOST', ''),
        'port': os.environ.get('RESTORE_PORT' if target else 'PGPORT', '5432'),
        'user': os.environ.get('RESTORE_USER' if target else 'PGUSER', ''),
        'password': os.environ.get('RESTORE_PASSWORD' if target else 'PGPASSWORD', ''),
        'dbname': database or ('postgres' if target else os.environ.get('PGDATABASE', '')),
        'connect_timeout': 5,
        'options': '-c timezone=UTC -c statement_timeout=300000',
    }
    if not all(values[k] for k in ('host', 'user', 'password', 'dbname')):
        raise ValueError(f'Missing {prefix} connection settings')
    return values


def execute(command, settings):
    env = os.environ.copy()
    for key, value in {'PGHOST': settings['host'], 'PGPORT': settings['port'],
                       'PGUSER': settings['user'], 'PGPASSWORD': settings['password'],
                       'PGDATABASE': settings['dbname'], 'PGCONNECT_TIMEOUT': '5',
                       'PGOPTIONS': '-c timezone=UTC -c statement_timeout=300000'}.items():
        env[key] = value
    result = subprocess.run(command, env=env, capture_output=True, timeout=900)
    if result.returncode:
        # Do not dump connection details or database contents into CI logs.
        raise RuntimeError(f'{command[0]} failed with exit code {result.returncode}')


@contextmanager
def locked(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.lock').open('a') as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another backup, drill, or prune is running') from exc
        try:
            yield
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


def read_manifest(folder):
    if folder.is_symlink() or not NAME.fullmatch(folder.name):
        raise ValueError('Invalid snapshot directory')
    manifest_file = folder / 'manifest.json'
    archive = folder / 'database.dump'
    if manifest_file.is_symlink() or archive.is_symlink():
        raise ValueError('Snapshot files must not be symbolic links')
    value = json.loads(manifest_file.read_text())
    if value['format'] != 1 or value['snapshot'] != folder.name:
        raise ValueError('Unsupported or mismatched manifest')
    timestamp = datetime.fromisoformat(value['created_at'])
    if timestamp.tzinfo is None:
        raise ValueError('Manifest timestamp requires a timezone')
    if not re.fullmatch('[0-9a-f]{64}', value['dump_sha256']):
        raise ValueError('Invalid archive hash')
    return value


def snapshots(root):
    found = []
    for folder in root.glob('snapshot_*'):
        # A malformed published snapshot is a visible error, not silently skipped.
        manifest = read_manifest(folder)
        found.append((datetime.fromisoformat(manifest['created_at']), folder, manifest))
    return sorted(found, key=lambda entry: (entry[0], entry[1].name))


def select(root, name):
    if name == 'latest':
        available = snapshots(root)
        if not available:
            raise ValueError('No completed backups found')
        return available[-1][1], available[-1][2]
    if not NAME.fullmatch(name):
        raise ValueError('Invalid snapshot name')
    folder = root / name
    return folder, read_manifest(folder)


def verify(folder, manifest):
    archive = folder / 'database.dump'
    if archive.stat().st_size != manifest['dump_bytes'] or digest(archive) != manifest['dump_sha256']:
        raise ValueError('Backup checksum mismatch; refusing to restore')


def backup(root):
    with locked(root):
        identifier = 'snapshot_' + uuid.uuid4().hex
        staging = root / ('.partial_' + uuid.uuid4().hex)
        staging.mkdir(mode=0o700)
        started = time.monotonic()
        try:
            source = config()
            with psycopg.connect(**source) as db:
                db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                exported = db.execute('SELECT pg_export_snapshot()').fetchone()[0]
                manifest = {'format': 1, 'snapshot': identifier, 'created_at': now(),
                            'source_database': source['dbname']}
                archive = staging / 'database.dump'
                execute(['pg_dump', '--format=custom', '--no-owner', '--no-acl',
                         '--snapshot=' + exported, '--file=' + str(archive)], source)
                manifest['data'] = fingerprint(db)
            manifest.update(dump_sha256=digest(archive), dump_bytes=archive.stat().st_size,
                            backup_seconds=round(time.monotonic() - started, 3))
            atomic_json(staging / 'manifest.json', manifest)
            staging.rename(root / identifier)
            atomic_json(root / 'backup-attempt.json', {'success': True, 'at': now()})
            return manifest
        except Exception as exc:
            atomic_json(root / 'backup-attempt.json', {'success': False, 'at': now(), 'error_type': type(exc).__name__})
            raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def assert_separate(source, target):
    if (source['host'], source['port']) == (target['host'], target['port']):
        raise ValueError('Recovery target must be a separate PostgreSQL server')
    with psycopg.connect(**source) as left, psycopg.connect(**target) as right:
        query = 'SELECT system_identifier::text FROM pg_control_system()'
        if left.execute(query).fetchone()[0] == right.execute(query).fetchone()[0]:
            raise ValueError('Source and target resolve to the same PostgreSQL cluster')


def drill(root, name='latest', max_age=7200, max_seconds=120):
    with locked(root):
        report = {'success': False, 'checked_at': now()}
        started = time.monotonic()
        scratch = 'recovery_' + uuid.uuid4().hex
        created = False
        target = None
        try:
            folder, manifest = select(root, name)
            verify(folder, manifest)
            source, target = config(), config(target=True)
            assert_separate(source, target)
            with psycopg.connect(**target, autocommit=True) as admin:
                admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(scratch)))
            created = True
            target_db = config(target=True, database=scratch)
            execute(['pg_restore', '--exit-on-error', '--no-owner', '--no-acl',
                     '--dbname=' + scratch, str(folder / 'database.dump')], target_db)
            with psycopg.connect(**target_db) as restored:
                actual = fingerprint(restored)
                # Prove writes work after restore and the identity sequence is usable.
                restored.execute("INSERT INTO incidents (title) VALUES ('restore write probe')")
                restored.rollback()
            duration = round(time.monotonic() - started, 3)
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(manifest['created_at'])).total_seconds()
            report.update(snapshot=folder.name, expected=manifest['data'], actual=actual,
                          restore_seconds=duration, backup_age_seconds=round(age, 3),
                          max_backup_age_seconds=max_age, max_restore_seconds=max_seconds)
            if actual != manifest['data']:
                raise ValueError('Restored data does not match the snapshot fingerprint')
            if age < 0 or age > max_age or duration > max_seconds:
                raise ValueError('Restore verified, but recovery targets were missed')
            report['success'] = True
        except Exception as exc:
            report.update(error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            if created:
                try:
                    with psycopg.connect(**target, autocommit=True) as admin:
                        admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(scratch)))
                except Exception:
                    report.update(success=False, cleanup_failed=True, scratch_database=scratch)
            report['checked_at'] = now()
            atomic_json(root / 'restore-report.json', report)
        if not report['success']:
            raise RuntimeError('Restore finished but scratch database cleanup failed; see report')
        return report


def prune(root, keep):
    if keep < 1:
        raise ValueError('Keep at least one backup')
    with locked(root):
        available = snapshots(root)
        # Verify the retained set before discarding anything.
        for _, folder, manifest in available[-keep:]:
            verify(folder, manifest)
        removed = []
        for _, folder, _ in available[:-keep]:
            shutil.rmtree(folder)
            removed.append(folder.name)
        return {'removed': removed, 'keep': keep}


def report(root):
    path = root / 'restore-report.json'
    return json.loads(path.read_text()) if path.exists() else {'success': False, 'error': 'No drill has run'}


def metrics(root):
    items = snapshots(root)
    newest = items[-1][0].timestamp() if items else 0
    last = report(root)
    attempt_path = root / 'backup-attempt.json'
    attempt = json.loads(attempt_path.read_text()) if attempt_path.exists() else {'success': False}
    values = {
        'recovery_backup_last_success_timestamp_seconds': newest,
        'recovery_backup_last_attempt_success': int(attempt['success']),
        'recovery_restore_last_attempt_success': int(last['success']),
        'recovery_restore_last_attempt_timestamp_seconds': datetime.fromisoformat(last['checked_at']).timestamp() if 'checked_at' in last else 0,
        'recovery_restore_duration_seconds': last.get('restore_seconds', 0),
        'recovery_backup_count': len(items),
    }
    return ''.join(f'# TYPE {name} gauge\n{name} {value}\n' for name, value in values.items())


def serve(root, port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ('/metrics', '/health'):
                self.send_error(404)
                return
            try:
                body = metrics(root) if self.path == '/metrics' else 'ok\n'
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; version=0.0.4')
                self.end_headers()
                self.wfile.write(body.encode())
            except (ValueError, OSError, KeyError):
                self.send_error(503, 'Backup metadata unavailable')
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('backup')
    restore = sub.add_parser('drill')
    restore.add_argument('--snapshot', default='latest')
    restore.add_argument('--max-age', type=int, default=7200)
    restore.add_argument('--max-seconds', type=int, default=120)
    retain = sub.add_parser('prune')
    retain.add_argument('--keep', type=int, default=7)
    sub.add_parser('report')
    sub.add_parser('metrics')
    server = sub.add_parser('serve')
    server.add_argument('--port', type=int, default=9101)
    scheduler = sub.add_parser('schedule')
    scheduler.add_argument('--interval', type=int, default=3600)
    scheduler.add_argument('--keep', type=int, default=7)
    args = parser.parse_args()
    root = Path(os.environ.get('BACKUP_DIR', '/backups'))
    if args.command == 'schedule':
        if args.interval < 10 or args.keep < 1:
            parser.error('interval must be >=10 and keep >=1')
        while True:
            try:
                print(json.dumps(backup(root)), flush=True)
                print(json.dumps(prune(root, args.keep)), flush=True)
            except Exception as exc:
                print(json.dumps({'success': False, 'error_type': type(exc).__name__}), file=sys.stderr, flush=True)
            time.sleep(args.interval)
    elif args.command == 'serve':
        serve(root, args.port)
    else:
        operations = {
            'backup': lambda: backup(root),
            'drill': lambda: drill(root, args.snapshot, args.max_age, args.max_seconds),
            'prune': lambda: prune(root, args.keep),
            'report': lambda: report(root),
            'metrics': lambda: metrics(root),
        }
        try:
            result = operations[args.command]()
            print(result if isinstance(result, str) else json.dumps(result, indent=2))
        except Exception as exc:
            print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
            raise SystemExit(1)


if __name__ == '__main__':
    main()
