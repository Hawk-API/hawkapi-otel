"""Regression tests for 0.2.0 hardening fixes."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from hawkapi_otel._middleware import OTelMiddleware, _redact_query


class _FakeHeaders:
    def __init__(self, data: dict[str, str] | None = None) -> None:
        self._data = data or {}

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._data.get(key.lower(), default)

    def __iter__(self):  # type: ignore[override]
        return iter(self._data.items())


class _FakeState:
    pass


class _FakeRequest:
    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        query_string: bytes = b"",
        scope_extra: dict[str, Any] | None = None,
    ) -> None:
        self.method = "POST"
        self.path = "/x"
        self.url_scheme = "http"
        self.query_string = query_string
        self.headers = _FakeHeaders(headers or {})
        self.client = ("127.0.0.1", 12345)
        self._scope: dict[str, Any] = {"type": "http"}
        if scope_extra:
            self._scope.update(scope_extra)
        self.state = _FakeState()

    @property
    def scope(self) -> dict[str, Any]:
        return self._scope


@pytest.fixture
def mem_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


@pytest.mark.asyncio
async def test_propagation_headers_only() -> None:
    """Only traceparent / tracestate / baggage must reach the OTel extractor."""
    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest(
        headers={
            "Authorization": "Bearer secret-token",
            "Cookie": "session=abc",
            "traceparent": "00-0123456789abcdef0123456789abcdef-aabbccddeeff0011-01",
        }
    )

    captured: dict[str, Any] = {}

    def _spy(carrier: dict[str, str]) -> Any:
        captured["carrier"] = carrier
        return MagicMock()

    with patch("hawkapi_otel._middleware.propagate.extract", side_effect=_spy):
        await mw.before_request(req)  # type: ignore[arg-type]

    assert "carrier" in captured
    carrier_keys = set(captured["carrier"].keys())
    assert "traceparent" in carrier_keys
    assert "authorization" not in carrier_keys
    assert "cookie" not in carrier_keys


@pytest.mark.asyncio
async def test_sensitive_query_param_redacted_in_span(
    mem_exporter: InMemorySpanExporter,
) -> None:
    """``url.query`` attribute must mask token-like parameters."""

    # Plugin-like object that exposes ``sensitive_query_params`` via the
    # ``_plugin_for`` lookup; we shortcut by patching that helper.
    class _FakePlugin:
        sensitive_query_params: frozenset[str] | None = None

    fake_plugin = _FakePlugin()

    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest(query_string=b"token=abc&page=2")
    with patch("hawkapi_otel._middleware._plugin_for", return_value=fake_plugin):
        await mw.before_request(req)  # type: ignore[arg-type]

    span = req.state._otel_span  # type: ignore[attr-defined]
    span.end()
    finished = mem_exporter.get_finished_spans()
    url_query = next((s.attributes.get("url.query") for s in finished if s.attributes), None)
    assert url_query is not None
    assert "abc" not in url_query
    assert "token=***" in url_query
    assert "page=2" in url_query


def test_redact_query_handles_empty() -> None:
    assert _redact_query("", None) == ""
