"""CLI evaluation runner — CI-friendly.

Usage:
    cd backend
    uv run python -m scripts.run_evaluations [--provider mock] [--seed 42]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


async def main(args: argparse.Namespace) -> int:
    import os

    os.environ.setdefault("LLM_PROVIDER", "mock")
    os.environ.setdefault("EMBEDDING_PROVIDER", "mock")

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.database.session import SessionLocal
    from app.evals.runner import (
        export_run_json,
        export_run_markdown,
        run_evaluation,
        seed_dataset,
    )

    async with SessionLocal() as db:
        print("Seeding evaluation dataset...")
        dataset = await seed_dataset(db)
        print(f"Dataset '{dataset.name}' — {dataset.case_count} cases")

        print(f"Starting evaluation run (provider={args.provider}, seed={args.seed})...")
        run = await run_evaluation(
            db,
            dataset_name=dataset.name,
            provider=args.provider,
            seed=args.seed,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout,
            compare_with_previous=True,
        )

        from app.evals.runner import export_run_json, export_run_markdown
        from app.models.evaluations import EvaluationResult
        from sqlalchemy import select

        results = list(
            (await db.execute(select(EvaluationResult).where(EvaluationResult.run_id == run.id)))
            .scalars()
            .all()
        )

        print(f"\n{'=' * 60}")
        print(f"Run: {run.run_name}")
        print(f"Status: {run.status.value}")
        print(
            f"Total: {run.total_cases} | Pass: {run.passed}"
            f" | Fail: {run.failed} | Error: {run.errors}"
        )
        print(f"Pass Rate: {run.pass_rate:.1f}%")
        print(f"Security Failures: {run.security_failures}")
        print(f"Avg Latency: {run.avg_latency_ms:.1f}ms")
        print(f"Regression: {'YES' if run.regression_detected else 'No'}")
        print(f"{'=' * 60}\n")

        if args.output_dir:
            out_dir = Path(args.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            json_path = out_dir / f"{run.run_name}.json"
            json_path.write_text(export_run_json(run, results))
            print(f"JSON export: {json_path}")

            md_path = out_dir / f"{run.run_name}.md"
            md_path.write_text(export_run_markdown(run, results))
            print(f"Markdown export: {md_path}")

        if run.security_failures > 0:
            print("\nFAILED: Security-critical failures detected")
            return 1

        print("\nPASSED: All evaluations completed successfully")
        return 0


def cli() -> None:
    parser = argparse.ArgumentParser(description="VaaniDesk Evaluation Runner")
    parser.add_argument("--provider", default="mock", help="Provider (mock/openai/anthropic)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrency level")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per case (seconds)")
    parser.add_argument("--output-dir", default=None, help="Directory for JSON/MD exports")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args)))


if __name__ == "__main__":
    cli()
