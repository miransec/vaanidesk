"""Database backup script — pg_dump wrapper with timestamp naming.

Usage: python -m scripts.backup [--output-dir ./backups]
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse


def main() -> None:
    raw = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--output-dir" else "./backups"
    output_dir = Path(raw)
    output_dir.mkdir(parents=True, exist_ok=True)

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    parsed = urlparse(db_url.replace("+asyncpg", ""))
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 5432)
    user = parsed.username or "vaanidesk"
    dbname = parsed.path.lstrip("/") or "vaanidesk"

    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dump_file = output_dir / f"vaanidesk_{ts}.sql.gz"

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    cmd = [
        "pg_dump",
        "-h",
        host,
        "-p",
        port,
        "-U",
        user,
        "-d",
        dbname,
        "--format=custom",
        f"--file={dump_file}",
    ]
    print(f"Running backup: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Backup FAILED: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    size = dump_file.stat().st_size
    print(f"Backup OK: {dump_file} ({size:,} bytes)")


if __name__ == "__main__":
    main()
