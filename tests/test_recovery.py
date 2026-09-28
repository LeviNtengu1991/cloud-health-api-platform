import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from recovery import cli


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def snapshot(self, n=1):
        folder = self.root / ('snapshot_' + f'{n:032x}')
        folder.mkdir()
        archive = folder / 'database.dump'
        archive.write_bytes(b'PGDMP-test-data')
        manifest = {'format': 1, 'snapshot': folder.name,
                    'created_at': f'2026-09-{n:02d}T00:00:00+00:00',
                    'dump_bytes': archive.stat().st_size,
                    'dump_sha256': cli.digest(archive)}
        cli.atomic_json(folder / 'manifest.json', manifest)
        return folder, manifest

    def test_valid_checksum(self):
        folder, manifest = self.snapshot()
        cli.verify(folder, manifest)

    def test_corruption_fails_before_database_connections(self):
        folder, _ = self.snapshot()
        (folder / 'database.dump').write_bytes(b'corrupted')
        with patch.object(cli.psycopg, 'connect') as connect:
            with self.assertRaisesRegex(ValueError, 'checksum'):
                cli.drill(self.root)
            connect.assert_not_called()
        self.assertFalse(cli.report(self.root)['success'])

    def test_missing_backup(self):
        with self.assertRaisesRegex(ValueError, 'No completed'):
            cli.select(self.root, 'latest')

    def test_path_traversal_rejected(self):
        for name in ('../secret', '/tmp/snapshot', 'snapshot_../outside'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                cli.select(self.root, name)

    def test_symlink_rejected(self):
        folder, manifest = self.snapshot()
        (folder / 'database.dump').unlink()
        (folder / 'database.dump').symlink_to(self.root / 'outside')
        with self.assertRaisesRegex(ValueError, 'symbolic'):
            cli.read_manifest(folder)

    def test_prune_keeps_newest(self):
        for n in range(1, 5):
            self.snapshot(n)
        result = cli.prune(self.root, 2)
        self.assertEqual(len(result['removed']), 2)
        self.assertEqual([m['snapshot'] for _, _, m in cli.snapshots(self.root)],
                         ['snapshot_' + f'{n:032x}' for n in (3, 4)])

    def test_prune_refuses_corrupt_retained_backup(self):
        old, _ = self.snapshot(1)
        new, _ = self.snapshot(2)
        (new / 'database.dump').write_bytes(b'broken')
        with self.assertRaises(ValueError):
            cli.prune(self.root, 1)
        self.assertTrue(old.exists())

    def test_prune_refuses_zero(self):
        with self.assertRaises(ValueError):
            cli.prune(self.root, 0)

    def test_partial_backups_are_not_selected(self):
        (self.root / '.partial_deadbeef').mkdir()
        self.assertEqual(cli.snapshots(self.root), [])

    def test_lock_excludes_second_operation(self):
        with cli.locked(self.root):
            with self.assertRaisesRegex(RuntimeError, 'Another'):
                with cli.locked(self.root):
                    pass

    def test_same_target_refused_without_connecting(self):
        settings = {'host': 'db', 'port': '5432'}
        with patch.object(cli.psycopg, 'connect') as connect:
            with self.assertRaisesRegex(ValueError, 'separate'):
                cli.assert_separate(settings, settings)
            connect.assert_not_called()

    def test_empty_metrics_exposes_missing_backup_and_drill(self):
        output = cli.metrics(self.root)
        self.assertIn('recovery_backup_last_success_timestamp_seconds 0', output)
        self.assertIn('recovery_restore_last_attempt_success 0', output)

    def test_atomic_report_replacement(self):
        path = self.root / 'report.json'
        cli.atomic_json(path, {'success': False})
        cli.atomic_json(path, {'success': True})
        self.assertEqual(json.loads(path.read_text()), {'success': True})
        self.assertEqual(list(self.root.glob('*.tmp-*')), [])


if __name__ == '__main__':
    unittest.main()
