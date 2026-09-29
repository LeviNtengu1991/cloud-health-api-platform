import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import boto3
from botocore.exceptions import ClientError
from moto import mock_aws

from recovery import cli, s3


@mock_aws
class S3Tests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "S3_BUCKET": "recovery-test",
                "S3_PREFIX": "recovery",
                "AWS_DEFAULT_REGION": "us-east-1",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.storage = boto3.client("s3", region_name="us-east-1")
        self.storage.create_bucket(Bucket="recovery-test")
        self.name = "snapshot_" + "a" * 32
        self.folder = self.root / self.name
        self.folder.mkdir()
        (self.folder / "database.dump").write_bytes(b"PGDMP-test-archive")
        self.manifest = {
            "format": 1,
            "snapshot": self.name,
            "created_at": cli.now(),
            "dump_bytes": 18,
            "dump_sha256": cli.digest(self.folder / "database.dump"),
            "data": {"rows": 0, "sha256": "0" * 64},
        }
        self.manifest["dump_bytes"] = (self.folder / "database.dump").stat().st_size
        cli.atomic_json(self.folder / "manifest.json", self.manifest)

    def upload(self):
        return s3.upload(self.root, storage=self.storage)

    def test_roundtrip_is_encrypted_and_verified(self):
        self.upload()
        head = self.storage.head_object(
            Bucket="recovery-test", Key="recovery/" + self.name + "/database.dump"
        )
        self.assertEqual(head["ServerSideEncryption"], "AES256")
        with tempfile.TemporaryDirectory() as target:
            restored = s3.download(Path(target), storage=self.storage)
            self.assertEqual(restored, self.manifest)
            self.assertEqual(
                (Path(target) / self.name / "database.dump").read_bytes(), b"PGDMP-test-archive"
            )

    def test_failed_archive_upload_does_not_publish_manifest(self):
        with patch.object(self.storage, "put_object", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                self.upload()
        self.assertEqual(s3.names(self.storage, "recovery-test", "recovery/"), [])
        self.assertFalse(json.loads((self.root / "s3-attempt.json").read_text())["success"])

    def test_failed_manifest_upload_is_not_discoverable(self):
        original = self.storage.put_object

        def put(**kwargs):
            if kwargs["Key"].endswith("manifest.json"):
                raise RuntimeError("interrupted")
            return original(**kwargs)

        with patch.object(self.storage, "put_object", side_effect=put):
            with self.assertRaises(RuntimeError):
                self.upload()
        self.assertEqual(s3.names(self.storage, "recovery-test", "recovery/"), [])
        self.upload()  # Retrying the same verified snapshot safely completes it.
        self.assertEqual(s3.names(self.storage, "recovery-test", "recovery/"), [self.name])

    def test_corrupt_download_never_publishes_local_snapshot(self):
        self.upload()
        self.storage.put_object(
            Bucket="recovery-test",
            Key="recovery/" + self.name + "/database.dump",
            Body=b"x" * self.manifest["dump_bytes"],
        )
        with tempfile.TemporaryDirectory() as target:
            with self.assertRaisesRegex(ValueError, "checksum"):
                s3.download(Path(target), storage=self.storage)
            self.assertEqual([p.name for p in Path(target).iterdir()], [".lock"])

    def test_rejects_path_traversal(self):
        with self.assertRaisesRegex(ValueError, "Invalid snapshot"):
            s3.download(self.root, "../escape", self.storage)

    def test_download_refuses_existing_local_data(self):
        self.upload()
        with self.assertRaisesRegex(ValueError, "already exists"):
            s3.download(self.root, self.name, self.storage)
        cli.verify(self.folder, self.manifest)

    def test_missing_archive_is_not_published(self):
        self.upload()
        self.storage.delete_object(
            Bucket="recovery-test", Key="recovery/" + self.name + "/database.dump"
        )
        with tempfile.TemporaryDirectory() as target:
            with self.assertRaises(ClientError):
                s3.download(Path(target), storage=self.storage)
            self.assertFalse((Path(target) / self.name).exists())

    def test_s3_drill_uses_downloaded_bytes_and_separate_report(self):
        self.upload()
        (self.folder / "database.dump").write_bytes(b"bad local cache")

        def restore(root, name, *args):
            self.assertNotEqual(root, self.root)
            self.assertEqual((root / name / "database.dump").read_bytes(), b"PGDMP-test-archive")
            return {"success": True, "checked_at": cli.now(), "restore_seconds": 1}

        with patch.object(cli, "drill", side_effect=restore):
            result = s3.drill(self.root, storage=self.storage)
        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "s3")
        self.assertTrue((self.root / "s3-restore-report.json").exists())
        self.assertFalse((self.root / "restore-report.json").exists())

    def test_download_failure_records_failed_s3_drill(self):
        with self.assertRaises(ValueError):
            s3.drill(self.root, storage=self.storage)
        self.assertFalse(json.loads((self.root / "s3-restore-report.json").read_text())["success"])

    def test_metrics_preserve_snapshot_age_after_failed_upload(self):
        self.upload()
        with patch.object(self.storage, "put_object", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.upload()
        metrics = cli.metrics(self.root)
        self.assertIn("recovery_s3_last_attempt_success 0", metrics)
        stamp = (
            __import__("datetime").datetime.fromisoformat(self.manifest["created_at"]).timestamp()
        )
        self.assertIn(f"recovery_s3_snapshot_timestamp_seconds {stamp}", metrics)

    def test_oversized_upload_rejected(self):
        with (
            patch.object(cli, "verify"),
            patch.object(
                cli,
                "select",
                return_value=(self.folder, {**self.manifest, "dump_bytes": s3.MAX_ARCHIVE + 1}),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "5 GiB"):
                self.upload()

    def test_failed_upload_skips_local_pruning(self):
        with (
            patch.object(cli, "backup", return_value=self.manifest),
            patch.object(s3, "upload", side_effect=RuntimeError),
            patch.object(cli, "prune") as prune,
        ):
            with self.assertRaises(RuntimeError):
                cli.backup_cycle(self.root, 1)
            prune.assert_not_called()

    def test_disabled_s3_cycle_stays_local(self):
        with (
            patch.dict(os.environ, {"S3_BUCKET": ""}),
            patch.object(cli, "backup", return_value=self.manifest),
            patch.object(s3, "upload") as upload,
            patch.object(cli, "prune", return_value={}) as prune,
        ):
            cli.backup_cycle(self.root, 2)
            upload.assert_not_called()
            prune.assert_called_once_with(self.root, 2)

    def test_invalid_configuration_records_failure(self):
        with patch.dict(os.environ, {"S3_BUCKET": ""}):
            with self.assertRaises(ValueError):
                self.upload()
        self.assertFalse(json.loads((self.root / "s3-attempt.json").read_text())["success"])

    def test_mismatched_manifest_rejected(self):
        self.upload()
        bad = {**self.manifest, "snapshot": "snapshot_" + "b" * 32}
        self.storage.put_object(
            Bucket="recovery-test",
            Key="recovery/" + self.name + "/manifest.json",
            Body=json.dumps(bad).encode(),
        )
        with tempfile.TemporaryDirectory() as target:
            with self.assertRaisesRegex(ValueError, "mismatched"):
                s3.download(Path(target), self.name, self.storage)


if __name__ == "__main__":
    unittest.main()
