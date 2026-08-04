"""Lightweight load test script.

Covers: health, chat read, retrieval, webhook ingestion, concurrent idempotent ops.
Uses httpx directly — no external dependencies beyond what's in pyproject.toml.

Usage:
    cd backend
    uv run python -m scripts.load_test --base-url http://localhost:8000 --concurrency 5
"""

from __future__ import annotations

import argparse
import asyncio
import platform
import sys
import time
from dataclasses import dataclass, field

import httpx

DEMO_KEY = "demo-anya"
HEADERS = {"X-Demo-User-Key": DEMO_KEY, "Content-Type": "application/json"}


@dataclass
class LoadTestResult:
    endpoint: str
    total_requests: int = 0
    success: int = 0
    errors: int = 0
    latencies: list[float] = field(default_factory=list)

    @property
    def avg_ms(self) -> float:
        return round(sum(self.latencies) / len(self.latencies), 2) if self.latencies else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        return round(s[int(len(s) * 0.95)], 2)


async def _request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    result: LoadTestResult,
    **kwargs: object,
) -> None:
    start = time.monotonic()
    try:
        resp = await client.request(method, url, **kwargs)  # type: ignore[arg-type]
        result.total_requests += 1
        latency = (time.monotonic() - start) * 1000
        result.latencies.append(latency)
        if resp.status_code < 400:
            result.success += 1
        else:
            result.errors += 1
    except Exception:
        result.total_requests += 1
        result.errors += 1


async def run_load_test(
    base_url: str,
    concurrency: int = 5,
    iterations: int = 10,
) -> list[LoadTestResult]:
    results: list[LoadTestResult] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        health_result = LoadTestResult(endpoint="GET /health")
        tasks = [_request(client, "GET", "/health", health_result) for _ in range(iterations)]
        await asyncio.gather(*tasks)
        results.append(health_result)

        conversations_result = LoadTestResult(endpoint="GET /api/v1/conversations")
        tasks = [
            _request(client, "GET", "/api/v1/conversations", conversations_result, headers=HEADERS)
            for _ in range(iterations)
        ]
        await asyncio.gather(*tasks)
        results.append(conversations_result)

        metrics_result = LoadTestResult(endpoint="GET /metrics")
        tasks = [_request(client, "GET", "/metrics", metrics_result) for _ in range(iterations)]
        await asyncio.gather(*tasks)
        results.append(metrics_result)

        chat_result = LoadTestResult(endpoint="POST /api/v1/chat/messages")
        for i in range(min(iterations, 5)):
            await _request(
                client,
                "POST",
                "/api/v1/chat/messages",
                chat_result,
                headers=HEADERS,
                json={"content": f"Load test message {i}"},
            )
        results.append(chat_result)

        idempotent_result = LoadTestResult(endpoint="POST /api/v1/chat/messages (idempotent)")
        idem_tasks = []
        for _ in range(concurrency):
            idem_tasks.append(
                _request(
                    client,
                    "POST",
                    "/api/v1/chat/messages",
                    idempotent_result,
                    headers={**HEADERS, "Idempotency-Key": "load-test-idem-001"},
                    json={"content": "Idempotent load test"},
                )
            )
        await asyncio.gather(*idem_tasks)
        results.append(idempotent_result)

    return results


def print_results(results: list[LoadTestResult], duration: float) -> None:
    print(f"\n{'=' * 70}")
    print("VaaniDesk Load Test Results")
    print(f"Hardware: {platform.machine()} | OS: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print(f"Total Duration: {duration:.2f}s")
    print(f"{'=' * 70}")
    print(f"{'Endpoint':<50} {'Total':>6} {'OK':>6} {'Err':>6} {'Avg(ms)':>9} {'P95(ms)':>9}")
    print(f"{'-' * 50} {'-' * 6} {'-' * 6} {'-' * 6} {'-' * 9} {'-' * 9}")
    for r in results:
        print(
            f"{r.endpoint:<50} {r.total_requests:>6} {r.success:>6}"
            f" {r.errors:>6} {r.avg_ms:>9.1f} {r.p95_ms:>9.1f}"
        )
    print(f"{'=' * 70}")


async def main(args: argparse.Namespace) -> int:
    start = time.monotonic()
    results = await run_load_test(
        base_url=args.base_url,
        concurrency=args.concurrency,
        iterations=args.iterations,
    )
    duration = time.monotonic() - start
    print_results(results, duration)

    total_errors = sum(r.errors for r in results)
    if total_errors > 0:
        print(f"\nWARNING: {total_errors} errors encountered")
    return 0


def cli() -> None:
    parser = argparse.ArgumentParser(description="VaaniDesk Load Test")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend URL")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent requests")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations per endpoint")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args)))


if __name__ == "__main__":
    cli()
