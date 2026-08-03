"""Unit tests for knowledge seed path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.rag.seed_paths import resolve_knowledge_seed_dir

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
HOST_POLICIES = REPO_ROOT / "sample_data" / "policies"


def test_configured_seed_directory(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"documents": []}', encoding="utf-8")
    resolved = resolve_knowledge_seed_dir(str(tmp_path), backend_root=BACKEND_ROOT)
    assert resolved == tmp_path.resolve()
    assert (resolved / "manifest.json").is_file()


def test_host_fallback_uses_repository_sample_data() -> None:
    resolved = resolve_knowledge_seed_dir(None, backend_root=BACKEND_ROOT)
    assert resolved == HOST_POLICIES.resolve()
    assert (resolved / "manifest.json").is_file()


def test_empty_configured_falls_back_to_host() -> None:
    resolved = resolve_knowledge_seed_dir("   ", backend_root=BACKEND_ROOT)
    assert resolved == HOST_POLICIES.resolve()


def test_missing_manifest_error_is_actionable(tmp_path: Path) -> None:
    empty = tmp_path / "empty_policies"
    empty.mkdir()
    with pytest.raises(FileNotFoundError) as exc:
        resolve_knowledge_seed_dir(str(empty), backend_root=BACKEND_ROOT)
    message = str(exc.value)
    assert "manifest.json" in message
    assert "KNOWLEDGE_SEED_DIR" in message
    assert str(empty.resolve() / "manifest.json") in message
