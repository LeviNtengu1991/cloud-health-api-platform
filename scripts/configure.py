#!/usr/bin/env python3
"""Generate local credentials; never replace existing values."""

import argparse
import os
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument(
    "--grafana", action="store_true", help="Add a Grafana password to an existing .env"
)
args = parser.parse_args()
path = Path(".env")
if args.grafana:
    if not path.exists():
        raise SystemExit("Run scripts/configure.py first")
    existing = path.read_text()
    if any(line.startswith("GRAFANA_ADMIN_PASSWORD=") for line in existing.splitlines()):
        raise SystemExit("Grafana password already configured; keeping it")
    with path.open("a") as out:
        out.write(
            ("" if existing.endswith("\n") else "\n")
            + "GRAFANA_ADMIN_PASSWORD="
            + secrets.token_hex(24)
            + "\n"
        )
    path.chmod(0o600)
else:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise SystemExit(".env already exists; keeping your existing configuration") from None
    with os.fdopen(fd, "w") as out:
        for name in (
            "POSTGRES_PASSWORD",
            "APP_DB_PASSWORD",
            "RESTORE_PASSWORD",
            "API_TOKEN",
            "GRAFANA_ADMIN_PASSWORD",
        ):
            out.write(f"{name}={secrets.token_hex(24)}\n")
print("Local credentials configured in .env. Keep it out of Git.")
