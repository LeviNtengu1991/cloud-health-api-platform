#!/usr/bin/env python3
"""Exercise the real Compose databases and API; no AWS credentials needed."""
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request


def compose(*args, success=True):
    result = subprocess.run(['docker', 'compose', *args], capture_output=True, text=True, timeout=180)
    if success and result.returncode:
        raise RuntimeError(f'Compose operation failed: {args}\n{result.stderr}')
    if not success and result.returncode == 0:
        raise AssertionError(f'Expected failure: {args}')
    return result.stdout


def api(path, data=None, method=None):
    token = dict(line.split('=', 1) for line in Path('.env').read_text().splitlines())['API_TOKEN']
    req = urllib.request.Request('http://127.0.0.1:8080' + path,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 method=method, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def wait_ready():
    for _ in range(60):
        try:
            if api('/ready')[0] == 200:
                return
        except (OSError, ValueError):
            pass
        time.sleep(1)
    raise RuntimeError('API did not become ready')


def main():
    wait_ready()
    for number in range(10):
        status, _ = api('/incidents', {'title': f'Recovery test {number}', 'severity': 'medium'})
        assert status == 201
    status, incident = api('/incidents', {'title': "A quote ' should remain data"})
    assert status == 201
    body = {'status': 'resolved', 'version': incident['version']}
    assert api('/incidents/' + str(incident['id']), body, 'PATCH')[0] == 200
    assert api('/incidents/' + str(incident['id']), body, 'PATCH')[0] == 409
    # The app role cannot drop the table.
    denied = compose('exec', '-T', '-e', 'PGUSER=cloud_api', 'db', 'sh', '-c',
                     'PGPASSWORD="$APP_DB_PASSWORD" psql -h localhost -d cloud_health -v ON_ERROR_STOP=1 -c "DROP TABLE incidents"', success=False)
    first = json.loads(compose('run', '--rm', 'ops', 'backup'))
    # Change live data after the snapshot. The drill must restore the older state.
    assert api('/incidents', {'title': 'Written after backup'})[0] == 201
    before = api('/incidents')[1]
    report = json.loads(compose('run', '--rm', 'ops', 'drill', '--snapshot', first['snapshot']))
    assert report['success'] and report['actual']['rows'] == first['data']['rows']
    assert api('/incidents')[1] == before, 'Drill changed the source database'
    assert compose('exec', '-T', 'restore-db', 'psql', '-U', 'recovery_owner', '-d', 'postgres', '-Atc',
                   "SELECT count(*) FROM pg_database WHERE datname ~ '^recovery_[0-9a-f]{32}$'").strip() == '0'
    compose('run', '--rm', 'ops', 'drill', '--snapshot', first['snapshot'], '--max-age', '0', success=False)
    compose('run', '--rm', '-e', 'RESTORE_HOST=db', 'ops', 'drill', success=False)
    # Corrupt a completed archive and prove checksum protection runs before restore.
    compose('run', '--rm', '--entrypoint', 'python', 'ops', '-c',
            "from pathlib import Path; p=Path('/backups')/" + repr(first['snapshot']) + "/'database.dump'; p.write_bytes(b'corrupt')")
    compose('run', '--rm', 'ops', 'drill', '--snapshot', first['snapshot'], success=False)
    second = json.loads(compose('run', '--rm', 'ops', 'backup'))
    compose('run', '--rm', 'ops', 'prune', '--keep', '1')
    report = json.loads(compose('run', '--rm', 'ops', 'drill', '--snapshot', second['snapshot']))
    assert report['success']
    compose('stop', 'db')
    try:
        assert api('/health')[0] == 200
        assert api('/ready')[0] == 503
    finally:
        compose('start', 'db')
    wait_ready()
    Path('artifacts').mkdir(exist_ok=True)
    Path('artifacts/restore-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'result': 'passed', 'checks': ['API writes', 'optimistic concurrency',
          'app database permissions', 'snapshot consistency', 'isolated restore', 'scratch cleanup',
          'stale backup refusal', 'same-server refusal', 'corruption refusal', 'retention',
          'liveness versus readiness'], 'report': report}, indent=2))


if __name__ == '__main__':
    main()
