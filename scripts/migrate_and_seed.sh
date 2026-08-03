#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
uv run alembic upgrade head
uv run python -m scripts.seed
