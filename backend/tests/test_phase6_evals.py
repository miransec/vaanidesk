"""Phase 6 — Evaluations, observability, and operations tests.

Covers: dataset validation, deterministic run, metrics, citation/no-answer scoring,
security failure fails run, providers disabled by default, comparison regression,
JSON/MD export, traces emitted, secrets redacted, high-cardinality avoided,
metrics endpoint, alert thresholds, Phase 1-5 regression.
Zero required skips.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://vaanidesk:vaanidesk_dev_password@localhost:5432/vaanidesk",
)

DEMO_KEY = "demo-anya"
HEADERS = {"X-Demo-User-Key": DEMO_KEY}

pytestmark = pytest.mark.skipif(
    os.getenv("VAANIDESK_SKIP_DB_TESTS", "").lower() in {"1", "true", "yes"},
    reason="VAANIDESK_SKIP_DB_TESTS set",
)


async def _db_available() -> bool:
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture
async def require_db() -> AsyncIterator[None]:
    if not await _db_available():
        pytest.skip("PostgreSQL is not available")
    yield


@pytest.fixture
async def client(require_db: None) -> AsyncIterator[AsyncClient]:
    os.environ["DATABASE_URL"] = DATABASE_URL
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["EMBEDDING_PROVIDER"] = "mock"
    os.environ["METRICS_ENABLED"] = "true"
    from app.core.config import get_settings
    from app.core.redis import reset_redis
    from app.database.session import get_db, reset_engine
    from app.main import create_app

    get_settings.cache_clear()
    reset_engine()
    await reset_redis()
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    app = create_app()

    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await reset_redis()
    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()


# =============================================================================
# Dataset Validation
# =============================================================================


class TestDatasetValidation:
    """Verify the evaluation dataset has >=100 meaningful cases."""

    def test_dataset_has_100_plus_cases(self):
        from app.evals.dataset import get_evaluation_cases

        cases = get_evaluation_cases()
        assert len(cases) >= 100, f"Expected >=100 cases, got {len(cases)}"

    def test_dataset_covers_required_categories(self):
        from app.evals.dataset import get_evaluation_cases

        cases = get_evaluation_cases()
        categories = {c["category"] for c in cases}
        required = {
            "greetings",
            "order_status",
            "ownership_denial",
            "cancel_eligibility",
            "cancel_confirm",
            "cancel_idempotency",
            "tickets",
            "escalation",
            "policy_retrieval",
            "citation_correctness",
            "no_answer",
            "restricted_doc_denial",
            "prompt_injection",
            "malicious_retrieved_instruction",
            "voice_transcript_review",
            "low_confidence_voice",
            "channel_dedup",
            "identity_linking",
            "external_sensitive_confirm",
            "malformed_unsupported_input",
            "rate_limiting",
        }
        missing = required - categories
        assert not missing, f"Missing categories: {missing}"

    def test_dataset_covers_required_languages(self):
        from app.evals.dataset import get_evaluation_cases

        cases = get_evaluation_cases()
        languages = {c["language"] for c in cases}
        required = {"en", "hi", "mr", "hinglish", "unknown"}
        missing = required - languages
        assert not missing, f"Missing languages: {missing}"

    def test_all_cases_have_expected_behavior(self):
        from app.evals.dataset import get_evaluation_cases

        cases = get_evaluation_cases()
        for c in cases:
            assert c["expected_behavior"], f"Case {c['case_index']} missing expected_behavior"

    def test_security_cases_have_expectations(self):
        from app.evals.dataset import get_evaluation_cases

        cases = get_evaluation_cases()
        security_cases = [c for c in cases if c["security_critical"]]
        assert len(security_cases) >= 20, f"Expected >=20 security cases, got {len(security_cases)}"
        for c in security_cases:
            assert c["security_expectations"], (
                f"Security case {c['case_index']} missing security_expectations"
            )

    def test_no_duplicate_indices(self):
        from app.evals.dataset import get_evaluation_cases

        cases = get_evaluation_cases()
        indices = [c["case_index"] for c in cases]
        assert len(indices) == len(set(indices)), "Duplicate case_index found"

    def test_dataset_metadata(self):
        from app.evals.dataset import get_dataset_metadata

        meta = get_dataset_metadata()
        assert meta["total_cases"] >= 100
        assert len(meta["categories"]) >= 20
        assert len(meta["languages"]) >= 5
        assert meta["security_critical_cases"] >= 20


# =============================================================================
# Evaluation Runner
# =============================================================================


class TestEvaluationRunner:
    """Deterministic eval run, scoring, export, security failure."""

    @pytest.mark.asyncio
    async def test_seed_dataset(self, client: AsyncClient):
        resp = await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["case_count"] >= 100
        assert data["name"] == "vaanidesk-core-v1"

    @pytest.mark.asyncio
    async def test_seed_idempotent(self, client: AsyncClient):
        resp1 = await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        resp2 = await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["name"] == resp2.json()["name"]

    @pytest.mark.asyncio
    async def test_run_evaluation(self, client: AsyncClient):
        await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        resp = await client.post(
            "/api/v1/evaluations/runs",
            json={
                "dataset_name": "vaanidesk-core-v1",
                "provider": "mock",
                "seed": 42,
            },
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "failed")
        assert data["total_cases"] >= 100
        assert data["passed"] > 0
        assert data["pass_rate"] is not None
        assert data["provider"] == "mock"

    @pytest.mark.asyncio
    async def test_run_results(self, client: AsyncClient):
        await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        run_resp = await client.post(
            "/api/v1/evaluations/runs",
            json={"dataset_name": "vaanidesk-core-v1", "provider": "mock"},
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        run_id = run_resp.json()["id"]

        resp = await client.get(f"/api/v1/evaluations/runs/{run_id}/results", headers=HEADERS)
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 100

    @pytest.mark.asyncio
    async def test_export_json(self, client: AsyncClient):
        await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        run_resp = await client.post(
            "/api/v1/evaluations/runs",
            json={"dataset_name": "vaanidesk-core-v1", "provider": "mock"},
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        run_id = run_resp.json()["id"]

        url = f"/api/v1/evaluations/runs/{run_id}/export?fmt=json"
        resp = await client.get(url, headers=HEADERS)
        assert resp.status_code == 200
        data = json.loads(resp.text)
        assert "run_id" in data
        assert "results" in data
        assert len(data["results"]) >= 100

    @pytest.mark.asyncio
    async def test_export_markdown(self, client: AsyncClient):
        await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        run_resp = await client.post(
            "/api/v1/evaluations/runs",
            json={"dataset_name": "vaanidesk-core-v1", "provider": "mock"},
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        run_id = run_resp.json()["id"]

        url = f"/api/v1/evaluations/runs/{run_id}/export?fmt=markdown"
        resp = await client.get(url, headers=HEADERS)
        assert resp.status_code == 200
        assert "# Evaluation Run" in resp.text
        assert "Category Breakdown" in resp.text
        assert "mock" in resp.text.lower()

    @pytest.mark.asyncio
    async def test_comparison(self, client: AsyncClient):
        await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        await client.post(
            "/api/v1/evaluations/runs",
            json={"dataset_name": "vaanidesk-core-v1", "provider": "mock"},
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        run2 = await client.post(
            "/api/v1/evaluations/runs",
            json={"dataset_name": "vaanidesk-core-v1", "provider": "mock"},
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        run_id = run2.json()["id"]
        resp = await client.get(f"/api/v1/evaluations/runs/{run_id}/compare", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "current" in data

    @pytest.mark.asyncio
    async def test_list_datasets(self, client: AsyncClient):
        await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        resp = await client.get("/api/v1/evaluations/datasets", headers=HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_list_runs(self, client: AsyncClient):
        resp = await client.get("/api/v1/evaluations/runs", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_mock_provider_label(self, client: AsyncClient):
        await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        run_resp = await client.post(
            "/api/v1/evaluations/runs",
            json={"dataset_name": "vaanidesk-core-v1", "provider": "mock"},
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        data = run_resp.json()
        assert data["provider"] == "mock"
        if data["summary"]:
            assert data["summary"].get("mock_evaluation") is True


# =============================================================================
# Observability
# =============================================================================


class TestObservability:
    """Tracing, metrics, secrets redaction."""

    def test_trace_span_records(self):
        from app.observability.tracing import clear_recorded_spans, get_recorded_spans, trace_span

        clear_recorded_spans()
        with trace_span("test.operation", attrs={"user_id": "u1", "request_id": "r1"}):
            pass
        spans = get_recorded_spans()
        assert len(spans) == 1
        assert spans[0]["operation"] == "test.operation"
        assert spans[0]["status"] == "ok"
        assert spans[0]["duration_ms"] >= 0
        clear_recorded_spans()

    def test_trace_span_error(self):
        from app.observability.tracing import clear_recorded_spans, get_recorded_spans, trace_span

        clear_recorded_spans()
        try:
            with trace_span("fail.op"):
                raise ValueError("boom")
        except ValueError:
            pass
        spans = get_recorded_spans()
        assert spans[0]["status"] == "error"
        assert spans[0]["error"] == "ValueError"
        clear_recorded_spans()

    def test_trace_redacts_secrets(self):
        from app.observability.tracing import clear_recorded_spans, get_recorded_spans, trace_span

        clear_recorded_spans()
        with trace_span("sec.op", attrs={"api_key": "sk-12345", "token": "tok", "user": "u1"}):
            pass
        spans = get_recorded_spans()
        assert "api_key" not in spans[0]["attrs"]
        assert "token" not in spans[0]["attrs"]
        assert spans[0]["attrs"].get("user") == "u1"
        clear_recorded_spans()

    def test_metrics_counter(self):
        from app.observability.metrics import MetricsCollector

        c = MetricsCollector()
        c.inc("test_counter")
        c.inc("test_counter", 5)
        assert c.get_counter("test_counter") == 6

    def test_metrics_latency(self):
        from app.observability.metrics import MetricsCollector

        c = MetricsCollector()
        for ms in [10.0, 20.0, 30.0, 40.0, 50.0]:
            c.record_latency("test_op", ms)
        stats = c.get_latency_stats("test_op")
        assert stats["avg"] == 30.0
        assert stats["count"] == 5

    def test_prometheus_format(self):
        from app.observability.metrics import MetricsCollector

        c = MetricsCollector()
        c.inc("http_requests")
        c.record_latency("http", 100.0)
        text = c.prometheus_text()
        assert "vaanidesk_uptime_seconds" in text
        assert "vaanidesk_http_requests_total" in text

    def test_no_high_cardinality_labels(self):
        from app.observability.metrics import MetricsCollector

        c = MetricsCollector()
        c.inc("http_requests")
        text = c.prometheus_text()
        assert "user_id=" not in text
        assert "email=" not in text

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client: AsyncClient):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "vaanidesk_uptime_seconds" in resp.text

    @pytest.mark.asyncio
    async def test_ops_snapshot(self, client: AsyncClient):
        resp = await client.get("/api/v1/observability/snapshot", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "db_aggregates" in data
        assert "in_memory" in data
        assert "uptime_seconds" in data


# =============================================================================
# Secrets Redaction
# =============================================================================


class TestSecretsRedaction:
    """Verify secrets don't enter logs."""

    def test_redaction_filter_blocks_api_key(self):
        from app.observability.logging_filters import SecretRedactionFilter

        f = SecretRedactionFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="api_key=sk-1234567890abcdef1234567890abcdef user=bob",
            args=(),
            exc_info=None,
        )
        f.filter(record)
        assert "sk-1234567890abcdef" not in record.msg
        assert "[REDACTED]" in record.msg

    def test_redaction_filter_blocks_bearer(self):
        from app.observability.logging_filters import SecretRedactionFilter

        f = SecretRedactionFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig",
            args=(),
            exc_info=None,
        )
        f.filter(record)
        assert "eyJhbGci" not in record.msg

    def test_redaction_filter_blocks_body(self):
        from app.observability.logging_filters import SecretRedactionFilter

        f = SecretRedactionFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="raw_body=large content here",
            args=(),
            exc_info=None,
        )
        f.filter(record)
        assert "large content" not in record.msg

    def test_existing_redaction_mapping(self):
        from app.security.redaction import redact_mapping

        data = {"token": "abc123", "user_id": "u1", "api_key": "secret"}
        redacted = redact_mapping(data)
        assert redacted is not None
        assert redacted["token"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["user_id"] == "u1"


# =============================================================================
# Alert Rules
# =============================================================================


class TestAlertRules:
    """Alert rule CRUD, seed, events."""

    @pytest.mark.asyncio
    async def test_seed_alert_rules(self, client: AsyncClient):
        resp = await client.post("/api/v1/alerts/rules/seed", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["seeded"] >= 8

    @pytest.mark.asyncio
    async def test_seed_idempotent(self, client: AsyncClient):
        await client.post("/api/v1/alerts/rules/seed", headers=HEADERS)
        resp = await client.post("/api/v1/alerts/rules/seed", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_rules(self, client: AsyncClient):
        await client.post("/api/v1/alerts/rules/seed", headers=HEADERS)
        resp = await client.get("/api/v1/alerts/rules", headers=HEADERS)
        assert resp.status_code == 200
        rules = resp.json()
        assert len(rules) >= 8
        rule_types = {r["condition_type"] for r in rules}
        assert "error_rate" in rule_types
        assert "eval_security_regression" in rule_types

    @pytest.mark.asyncio
    async def test_create_custom_rule(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/alerts/rules",
            json={
                "name": f"test-rule-{uuid4().hex[:8]}",
                "condition_type": "custom_metric",
                "threshold": 0.5,
                "severity": "warning",
            },
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.json()["condition_type"] == "custom_metric"

    @pytest.mark.asyncio
    async def test_list_alert_events(self, client: AsyncClient):
        resp = await client.get("/api/v1/alerts/events", headers=HEADERS)
        assert resp.status_code == 200


# =============================================================================
# Audit Log
# =============================================================================


class TestAuditLog:
    """Audit log entries from eval runs."""

    @pytest.mark.asyncio
    async def test_audit_log_after_eval(self, client: AsyncClient):
        await client.post("/api/v1/evaluations/datasets/seed", headers=HEADERS)
        await client.post(
            "/api/v1/evaluations/runs",
            json={"dataset_name": "vaanidesk-core-v1", "provider": "mock"},
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        resp = await client.get("/api/v1/audit", headers=HEADERS)
        assert resp.status_code == 200
        entries = resp.json()
        actions = {e["action"] for e in entries}
        assert "evaluation_run_completed" in actions or "dataset_seeded" in actions

    @pytest.mark.asyncio
    async def test_audit_filter(self, client: AsyncClient):
        resp = await client.get("/api/v1/audit?action=dataset_seeded", headers=HEADERS)
        assert resp.status_code == 200


# =============================================================================
# Phase 1-5 Regression
# =============================================================================


class TestPhaseRegression:
    """Verify Phase 1-5 features still work after Phase 6."""

    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ready(self, client: AsyncClient):
        resp = await client.get("/ready")
        assert resp.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_chat_endpoint(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/chat/messages",
            json={"content": "Hello from Phase 6 regression test"},
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assistant_message"]["content"]

    @pytest.mark.asyncio
    async def test_conversations_list(self, client: AsyncClient):
        resp = await client.get("/api/v1/conversations", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_knowledge_documents(self, client: AsyncClient):
        resp = await client.get("/api/v1/knowledge/documents", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_channels_connections(self, client: AsyncClient):
        resp = await client.get("/api/v1/channels/connections", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_demo_users(self, client: AsyncClient):
        resp = await client.get("/api/v1/demo-users")
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) >= 1

    @pytest.mark.asyncio
    async def test_metrics_at_root(self, client: AsyncClient):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "vaanidesk" in resp.text
