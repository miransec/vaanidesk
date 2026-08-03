"""Idempotent knowledge corpus seed for Phase 3."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.database.session import SessionLocal, get_engine  # noqa: E402
from app.models import DocumentAccessLevel, KnowledgeChunk, KnowledgeDocument  # noqa: E402
from app.rag.ingestion import ingest_document  # noqa: E402
from app.rag.seed_paths import resolve_knowledge_seed_dir  # noqa: E402


async def seed_knowledge(*, force: bool = False) -> dict[str, int | str]:
    settings = get_settings()
    seed_dir = resolve_knowledge_seed_dir(
        settings.knowledge_seed_dir,
        backend_root=ROOT,
    )
    manifest_path = seed_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    docs = manifest["documents"] if isinstance(manifest, dict) else manifest

    async with SessionLocal() as db:
        existing = (
            await db.execute(select(func.count()).select_from(KnowledgeDocument))
        ).scalar_one()
        if existing and not force:
            chunks = (
                await db.execute(select(func.count()).select_from(KnowledgeChunk))
            ).scalar_one()
            return {
                "documents": int(existing),
                "chunks": int(chunks),
                "mode": "already_present",
                "seed_dir": str(seed_dir),
            }

        if force and existing:
            from sqlalchemy import text

            await db.execute(
                text(
                    "TRUNCATE retrieval_traces, ingestion_jobs, knowledge_chunks, "
                    "knowledge_document_versions, knowledge_documents CASCADE"
                )
            )
            await db.commit()

        created = 0
        versions = 0
        for entry in docs:
            path = seed_dir / entry["filename"]
            if not path.is_file():
                raise FileNotFoundError(
                    f"Seed document missing: {path} (listed in {manifest_path})"
                )
            raw = path.read_bytes()
            level = DocumentAccessLevel(entry.get("access_level", "authenticated"))
            allow = entry.get("access_allowlist") or entry.get("allowlist")
            mime = "text/markdown" if path.suffix.lower() == ".md" else "text/plain"
            result = await ingest_document(
                db=db,
                title=entry["title"],
                raw=raw,
                mime_type=mime,
                filename=entry["filename"],
                language=entry.get("language", "en"),
                access_level=level,
                access_allowlist=allow,
                activate=True,
            )
            created += 1
            versions += 1
            doc_id = result["document_id"]
            v2 = entry.get("v2_filename")
            if v2:
                v2_path = seed_dir / v2
                if not v2_path.is_file():
                    raise FileNotFoundError(
                        f"Seed document missing: {v2_path} (listed in {manifest_path})"
                    )
                await ingest_document(
                    db=db,
                    title=entry["title"],
                    raw=v2_path.read_bytes(),
                    mime_type=mime,
                    filename=v2,
                    language=entry.get("language", "en"),
                    access_level=level,
                    access_allowlist=allow,
                    document_id=UUID(doc_id),
                    activate=True,
                )
                versions += 1

        await db.commit()
        chunks = (await db.execute(select(func.count()).select_from(KnowledgeChunk))).scalar_one()
        docs_count = (
            await db.execute(select(func.count()).select_from(KnowledgeDocument))
        ).scalar_one()
        return {
            "documents": int(docs_count),
            "versions_ingested": versions,
            "chunks": int(chunks),
            "mode": "applied",
            "created_docs": created,
            "seed_dir": str(seed_dir),
        }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = await seed_knowledge(force=args.force)
    print(json.dumps(result, indent=2))
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
