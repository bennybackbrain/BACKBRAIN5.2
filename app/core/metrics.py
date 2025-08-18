from __future__ import annotations
"""Prometheus metrics registry and metric objects.

Legacy helper functions (inc, observe, etc.) kept as no-ops for backward compatibility.
New code should import concrete metric objects and use .labels(...).inc()/observe().
"""
from prometheus_client import Counter, Histogram, CollectorRegistry, generate_latest
from typing import Any

registry = CollectorRegistry()

http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    labelnames=("method", "path", "status"),
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    registry=registry,
)

rate_limit_drops_total = Counter(
    "rate_limit_drops_total",
    "Requests blocked by rate limiting",
    labelnames=("path",),
    registry=registry,
)

write_file_total = Counter(
    "write_file_total",
    "Total write-file attempts",
    registry=registry,
)

write_file_errors_total = Counter(
    "write_file_errors_total",
    "Total write-file failures",
    registry=registry,
)

# Auto summary metrics (centralized so /metrics output includes them)
auto_summary_total = Counter(
    "bb_auto_summary_total",
    "Auto summary attempts",
    labelnames=("status", "storage"),  # status=ok|error
    registry=registry,
)
auto_summary_duration_seconds = Histogram(
    "bb_auto_summary_duration_seconds",
    "Duration of auto summary generation",
    registry=registry,
)

# Auto ingest metrics
auto_ingest_scan_total = Counter(
    "bb_auto_ingest_scan_total",
    "Auto-ingest scan cycles",
    labelnames=("result",),  # result=ok|error
    registry=registry,
)
auto_ingest_files_total = Counter(
    "bb_auto_ingest_files_total",
    "Files considered by auto-ingest",
    labelnames=("action",),  # action=skipped|ingested|error
    registry=registry,
)

# Legacy compatibility wrappers (no-op / passthrough)
def inc(name: str, value: float = 1.0):  # pragma: no cover
    # deprecated – prefer explicit counters
    pass

def set_gauge(name: str, value: float):  # pragma: no cover
    pass

def snapshot() -> tuple[dict[str, float], dict[str, float]]:  # pragma: no cover
    return {}, {}

def render_prometheus() -> str:
    return generate_latest(registry).decode("utf-8")

from typing import Iterable
def observe(name: str, value: float, buckets: Iterable[float] | None = None):  # pragma: no cover
    # use specific histograms instead
    pass

def inc_labeled(base: str, **labels: Any):  # pragma: no cover
    # retained for old code paths; map selective known metrics if needed
    pass

__all__ = [
    "http_requests_total",
    "http_request_duration_seconds",
    "rate_limit_drops_total",
    "write_file_total",
    "write_file_errors_total",
    "auto_summary_total",
    "auto_summary_duration_seconds",
    "render_prometheus",
]
