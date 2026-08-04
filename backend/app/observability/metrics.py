"""Prometheus-compatible /metrics endpoint + in-memory counters.

Avoids high-cardinality labels — no raw user IDs, no full paths.
Provides both Prometheus text format and JSON for admin pages.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import RLock


class MetricsCollector:
    """Thread-safe in-memory metrics collector."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._start_time = time.monotonic()
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._max_latency_samples = 1000

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def record_latency(self, name: str, ms: float) -> None:
        with self._lock:
            buf = self._latencies[name]
            buf.append(ms)
            if len(buf) > self._max_latency_samples:
                buf[:] = buf[-self._max_latency_samples :]

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def get_latency_stats(self, name: str) -> dict[str, float]:
        with self._lock:
            buf = self._latencies.get(name, [])
            if not buf:
                return {"avg": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
            sorted_buf = sorted(buf)
            n = len(sorted_buf)
            return {
                "avg": round(sum(sorted_buf) / n, 2),
                "p95": round(sorted_buf[int(n * 0.95)] if n > 1 else sorted_buf[0], 2),
                "p99": round(sorted_buf[int(n * 0.99)] if n > 1 else sorted_buf[0], 2),
                "count": n,
            }

    def uptime_seconds(self) -> float:
        return round(time.monotonic() - self._start_time, 2)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "uptime_seconds": self.uptime_seconds(),
                "latency_stats": {k: self.get_latency_stats(k) for k in self._latencies},
            }

    def prometheus_text(self) -> str:
        lines: list[str] = []
        lines.append("# HELP vaanidesk_uptime_seconds Backend uptime in seconds")
        lines.append("# TYPE vaanidesk_uptime_seconds gauge")
        lines.append(f"vaanidesk_uptime_seconds {self.uptime_seconds()}")
        with self._lock:
            for name, value in sorted(self._counters.items()):
                safe_name = name.replace(".", "_").replace("-", "_")
                lines.append(f"# TYPE vaanidesk_{safe_name}_total counter")
                lines.append(f"vaanidesk_{safe_name}_total {value}")
            for name in sorted(self._latencies):
                stats = self.get_latency_stats(name)
                safe_name = name.replace(".", "_").replace("-", "_")
                lines.append(f"# TYPE vaanidesk_{safe_name}_latency_ms summary")
                lines.append(f'vaanidesk_{safe_name}_latency_ms{{quantile="0.95"}} {stats["p95"]}')
                lines.append(f'vaanidesk_{safe_name}_latency_ms{{quantile="0.99"}} {stats["p99"]}')
                lines.append(f"vaanidesk_{safe_name}_latency_ms_avg {stats['avg']}")
        lines.append("")
        return "\n".join(lines)

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._latencies.clear()
            self._start_time = time.monotonic()


collector = MetricsCollector()
