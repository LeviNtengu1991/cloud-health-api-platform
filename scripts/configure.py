#!/usr/bin/env python3
"""Create local-only credentials without overwriting an existing configuration."""
import os
import secrets
from pathlib import Path
path = Path('.env')
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit('.env already exists; keeping your existing configuration')
with os.fdopen(fd, 'w') as out:
    for name in ('POSTGRES_PASSWORD', 'APP_DB_PASSWORD', 'RESTORE_PASSWORD', 'API_TOKEN'):
        out.write(f'{name}={secrets.token_hex(24)}\n')
print('Created .env with separate local credentials. Keep it out of Git.')
