"""
All custom metric definitions live here so the rest of the codebase has
exactly one import path for instrumentation. Define metrics at module
scope: OTel deduplicates by name, but creating them once is clearer.
"""
from opentelemetry import metrics

_meter = metrics.get_meter(__name__)

# Counter: increments only. Use for rates ("how many logins per second").
login_attempts = _meter.create_counter(
    name="auth_login_attempts_total",
    description="Total login attempts, labeled by outcome.",
    unit="1",
)

# Histogram: distribution. Use for latencies, payload sizes, queue depths
# at sample time, etc. Buckets are auto-chosen by the SDK; you can
# override them via Views if needed.
rate_limit_check_duration = _meter.create_histogram(
    name="rate_limit_check_duration_seconds",
    description="Latency of the Redis token-bucket rate-limit check.",
    unit="s",
)

# Counter for rate-limit decisions — rejection rate is a top-line SLO metric.
rate_limit_decisions = _meter.create_counter(
    name="rate_limit_decisions_total",
    description="Rate limit decisions, labeled by outcome (allowed|rejected).",
    unit="1",
)
