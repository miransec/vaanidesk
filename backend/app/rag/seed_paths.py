"""Resolve the Phase 3 knowledge corpus directory (host + Docker)."""

from __future__ import annotations

from pathlib import Path


def resolve_knowledge_seed_dir(
    configured: str | None = None,
    *,
    backend_root: Path | None = None,
) -> Path:
    """Return the policies directory containing ``manifest.json``.

    Resolution order:
    1. Explicit ``configured`` / ``KNOWLEDGE_SEED_DIR`` (absolute or cwd-relative).
    2. Host fallback: ``<repository-root>/sample_data/policies`` where repository
       root is the parent of the backend package root.

    Raises ``FileNotFoundError`` with an actionable message when
    ``manifest.json`` is missing.
    """
    if configured is not None and configured.strip():
        seed_dir = Path(configured.strip()).expanduser()
        if not seed_dir.is_absolute():
            seed_dir = (Path.cwd() / seed_dir).resolve()
        else:
            seed_dir = seed_dir.resolve()
    else:
        # this file: backend/app/rag/seed_paths.py → parents[2] = backend/
        backend = (backend_root or Path(__file__).resolve().parents[2]).resolve()
        repo_root = backend.parent
        seed_dir = (repo_root / "sample_data" / "policies").resolve()

    manifest = seed_dir / "manifest.json"
    if not manifest.is_file():
        raise FileNotFoundError(
            "Knowledge seed manifest not found at "
            f"{manifest}. "
            "Set KNOWLEDGE_SEED_DIR to the directory that contains manifest.json "
            "(Compose default: /sample_data/policies with ./sample_data mounted at "
            "/sample_data:ro), or place the corpus at "
            "<repository-root>/sample_data/policies for host development."
        )
    return seed_dir
