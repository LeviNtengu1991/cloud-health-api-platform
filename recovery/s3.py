"""Optional S3 transport. A manifest is the commit marker for a complete snapshot."""

import base64
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from recovery import cli

MAX_ARCHIVE = 5 * 1024**3  # Single PutObject; fail explicitly instead of partial multipart uploads.
MAX_MANIFEST = 64 * 1024


def settings():
    bucket = os.environ.get("S3_BUCKET", "")
    prefix = os.environ.get("S3_PREFIX", "recovery").strip("/")
    if not bucket or not prefix or any(p in (".", "..") for p in prefix.split("/")):
        raise ValueError("Set S3_BUCKET and a nonempty S3_PREFIX without dot segments")
    return bucket, prefix + "/"


def client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        config=Config(
            connect_timeout=5, read_timeout=60, retries={"mode": "standard", "max_attempts": 3}
        ),
    )


def upload(root, name="latest", storage=None):
    with cli.locked(root):
        attempt = {"success": False, "at": cli.now()}
        try:
            bucket, prefix = settings()
            storage = storage or client()
            folder, manifest = cli.select(root, name)
            cli.verify(folder, manifest)
            if manifest["dump_bytes"] > MAX_ARCHIVE:
                raise ValueError("Archive exceeds the 5 GiB single-upload lab limit")
            # Archive first, manifest last. Readers never select incomplete uploads.
            for filename in ("database.dump", "manifest.json"):
                path = folder / filename
                checksum = base64.b64encode(bytes.fromhex(cli.digest(path))).decode()
                with path.open("rb") as body:
                    storage.put_object(
                        Bucket=bucket,
                        Key=prefix + folder.name + "/" + filename,
                        Body=body,
                        ServerSideEncryption="AES256",
                        ChecksumSHA256=checksum,
                    )
            attempt.update(
                success=True, snapshot=folder.name, snapshot_created_at=manifest["created_at"]
            )
            cli.atomic_json(root / "s3-last-success.json", attempt)
            return attempt
        except Exception as exc:
            attempt["error_type"] = type(exc).__name__
            raise
        finally:
            cli.atomic_json(root / "s3-attempt.json", attempt)


def names(storage, bucket, prefix):
    found = []
    for page in storage.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            relative = item["Key"][len(prefix) :].split("/")
            if (
                len(relative) == 2
                and cli.NAME.fullmatch(relative[0])
                and relative[1] == "manifest.json"
            ):
                found.append(relative[0])
    return found


def manifest_from_s3(storage, bucket, key):
    response = storage.get_object(Bucket=bucket, Key=key)
    with response["Body"] as body:
        if response.get("ContentLength", 0) > MAX_MANIFEST:
            raise ValueError("Remote manifest too large")
        raw = body.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST:
        raise ValueError("Remote manifest too large")
    return json.loads(raw)


def download(root, name="latest", storage=None):
    bucket, prefix = settings()
    storage = storage or client()
    with cli.locked(root):
        if name == "latest":
            candidates = [
                (manifest_from_s3(storage, bucket, prefix + n + "/manifest.json"), n)
                for n in names(storage, bucket, prefix)
            ]
            if not candidates:
                raise ValueError("No completed S3 backups found")
            manifest, name = max(
                candidates, key=lambda pair: datetime.fromisoformat(pair[0]["created_at"])
            )
        else:
            if not cli.NAME.fullmatch(name):
                raise ValueError("Invalid snapshot name")
            manifest = manifest_from_s3(storage, bucket, prefix + name + "/manifest.json")
        destination = root / name
        if destination.exists() or destination.is_symlink():
            raise ValueError("Local snapshot already exists; use a fresh download directory")
        staging = Path(tempfile.mkdtemp(prefix=".s3-download-", dir=root))
        folder = staging / name
        folder.mkdir(mode=0o700)
        try:
            cli.atomic_json(folder / "manifest.json", manifest)
            manifest = cli.read_manifest(folder)
            size = manifest["dump_bytes"]
            if type(size) is not int or not 0 < size <= MAX_ARCHIVE:
                raise ValueError("Invalid or oversized remote archive")
            response = storage.get_object(Bucket=bucket, Key=prefix + name + "/database.dump")
            with response["Body"] as body, (folder / "database.dump").open("xb") as out:
                if response["ContentLength"] != size:
                    raise ValueError("Remote archive size mismatch")
                count = 0
                while chunk := body.read(1024 * 1024):
                    count += len(chunk)
                    if count > size:
                        raise ValueError("Remote archive exceeds manifest size")
                    out.write(chunk)
            cli.verify(folder, manifest)
            folder.rename(destination)
            return manifest
        finally:
            shutil.rmtree(staging)


def drill(root, name="latest", max_age=7200, max_seconds=120, storage=None):
    # Fresh temporary storage proves the drill used S3 bytes, never a cached local dump.
    with cli.locked(root), tempfile.TemporaryDirectory(prefix="s3-drill-") as temporary:
        scratch = Path(temporary)
        result = {"success": False, "checked_at": cli.now(), "source": "s3"}
        try:
            manifest = download(scratch, name, storage)
            result = cli.drill(scratch, manifest["snapshot"], max_age, max_seconds)
            result["source"] = "s3"
            return result
        except Exception as exc:
            if (scratch / "restore-report.json").exists():
                result = cli.report(scratch)
            result.update(success=False, source="s3", error_type=type(exc).__name__)
            raise
        finally:
            cli.atomic_json(root / "s3-restore-report.json", result)
