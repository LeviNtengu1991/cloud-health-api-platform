#!/usr/bin/env python3
"""Use a local S3 emulator and real PostgreSQL; no AWS account or credentials."""

import json
import subprocess
from pathlib import Path

ENV = [
    "-e",
    "S3_BUCKET=recovery-ci",
    "-e",
    "S3_PREFIX=recovery",
    "-e",
    "AWS_ENDPOINT_URL_S3=http://s3-mock:5000",
    "-e",
    "AWS_DEFAULT_REGION=us-east-1",
    "-e",
    "AWS_ACCESS_KEY_ID=testing",
    "-e",
    "AWS_SECRET_ACCESS_KEY=testing",
    "-e",
    "AWS_SESSION_TOKEN=",
    "-e",
    "AWS_EC2_METADATA_DISABLED=true",
]


def run(*args, python=False, fail=False):
    command = ["docker", "compose", "run", "--rm", "--no-deps", *ENV]
    if python:
        command += ["--entrypoint", "python"]
    result = subprocess.run(command + ["ops", *args], capture_output=True, text=True, timeout=180)
    if fail:
        assert result.returncode != 0, "Expected operation to fail"
        return
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


run("-c", "import boto3; boto3.client('s3').create_bucket(Bucket='recovery-ci')", python=True)
snapshot = json.loads(run("backup"))["snapshot"]
assert json.loads(run("s3-upload", "--snapshot", snapshot))["success"]
report = json.loads(run("s3-drill", "--snapshot", snapshot))
assert report["success"] and report["source"] == "s3"
assert report["actual"] == report["expected"]
Path("artifacts").mkdir(exist_ok=True)
Path("artifacts/s3-restore-report.json").write_text(json.dumps(report, indent=2) + "\n")
key = "recovery/" + snapshot + "/database.dump"
run(
    "-c",
    "import boto3; boto3.client('s3').put_object(Bucket='recovery-ci', Key="
    + repr(key)
    + ", Body=b'corrupted')",
    python=True,
)
run("s3-drill", "--snapshot", snapshot, fail=True)
print(
    "S3 emulator: upload, download, real PostgreSQL restore, fingerprint verification, and corruption refusal passed."
)
