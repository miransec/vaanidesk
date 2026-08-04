"""Database restore script — pg_restore wrapper.

Usage: python -m scripts.restore <backup-file>
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.restore <backup-file>", file=sys.stderr)
        sys.exit(1)

    backup_file = Path(sys.argv[1])
    if not backup_file.exists():
        print(f"ERROR: File not found: {backup_file}", file=sys.stderr)
        sys.exit(1)

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    parsed = urlparse(db_url.replace("+asyncpg", ""))
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    user = parsed.username or "vaanidesk"
    dbname = parsed.path.lstrip("/") or "vaanidesk"

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    cmd = [
        "pg_restore",
        "-h",
        host,
        "-p",
        port,
        "-U",
        user,
        "-d",
        dbname,
        "--clean",
        "--if-exists",
        str(backup_file),
    ]
    print(f"Running restore: {' '.join(cmd)}")
    print("WARNING: This will DROP and recreate tables in the target database.")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Restore completed with warnings/errors:\n{result.stderr}", file=sys.stderr)
    else:
        print("Restore OK")

    verify_cmd = [
        "psql",
        "-h",
        host,
        "-p",
        port,
        "-U",
        user,
        "-d",
        dbname,
        "-c",
        "SELECT count(*) FROM users;",
    ]
    verify = subprocess.run(verify_cmd, env=env, capture_output=True, text=True)
    if verify.returncode == 0:
        print(f"Verification: {verify.stdout.strip()}")
    else:
        print("Verification query failed (non-critical)")


if __name__ == "__main__":
    main()
