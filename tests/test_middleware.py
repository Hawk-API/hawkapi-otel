"""Tests for OTelMiddleware span behaviour."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from hawkapi_otel._middleware import OTelMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
        method: str = "GET",
        path: str = "/items",
        scheme: str = "http",
        query_string: bytes = b"",
        headers: dict[str, str] | None = None,
        client_host: str | None = "127.0.0.1",
        scope_extra: dict[str, Any] | None = None,
    ) -> None:
        self.method = method
        self.path = path
        self.url_scheme = scheme
        self.query_string = query_string
        self.headers = _FakeHeaders(headers or {})
        self.client = (client_host, 12345) if client_host else None
        self._scope: dict[str, Any] = {"type": "http", "method": method, "path": path}
        if scope_extra:
            self._scope.update(scope_extra)
        self.state = _FakeState()

    @property
    def scope(self) -> dict[str, Any]:
        return self._scope


class _FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_before_request_starts_span(mem_exporter: InMemorySpanExporter) -> None:
    """before_request stores a span on request.state._otel_span."""
    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest()
    await mw.before_request(req)  # type: ignore[arg-type]
    assert getattr(req.state, "_otel_span", None) is not None


@pytest.mark.asyncio
async def test_span_has_http_method(mem_exporter: InMemorySpanExporter) -> None:
    """Span carries http.request.method attribute."""
    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest(method="POST")
    await mw.before_request(req)  # type: ignore[arg-type]
    await mw.after_response(req, _FakeResponse(200))  # type: ignore[arg-type]

    spans = mem_exporter.get_finished_spans()
    assert spans[0].attributes.get("http.request.method") == "POST"


@pytest.mark.asyncio
async def test_span_has_url_path(mem_exporter: InMemorySpanExporter) -> None:
    """Span carries url.path attribute."""
    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest(path="/users/42")
    await mw.before_request(req)  # type: ignore[arg-type]
    await mw.after_response(req, _FakeResponse(200))  # type: ignore[arg-type]

    spans = mem_exporter.get_finished_spans()
    assert spans[0].attributes.get("url.path") == "/users/42"


@pytest.mark.asyncio
async def test_500_sets_error_status(mem_exporter: InMemorySpanExporter) -> None:
    """after_response sets ERROR status for 5xx responses."""
    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest()
    await mw.before_request(req)  # type: ignore[arg-type]
    await mw.after_response(req, _FakeResponse(500))  # type: ignore[arg-type]

    spans = mem_exporter.get_finished_spans()
    assert spans[0].status.status_code == StatusCode.ERROR


@pytest.mark.asyncio
async def test_200_leaves_status_unset(mem_exporter: InMemorySpanExporter) -> None:
    """after_response does not set ERROR status for 2xx responses."""
    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest()
    await mw.before_request(req)  # type: ignore[arg-type]
    await mw.after_response(req, _FakeResponse(200))  # type: ignore[arg-type]

    spans = mem_exporter.get_finished_spans()
    assert spans[0].status.status_code != StatusCode.ERROR


@pytest.mark.asyncio
async def test_traceparent_header_creates_child_span(mem_exporter: InMemorySpanExporter) -> None:
    """Incoming traceparent makes the new span a child of the remote trace."""
    traceparent = "00-4bf92f3577b16e0714f34b92bd2fa926-00f067aa0ba902b7-01"
    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest(headers={"traceparent": traceparent})
    await mw.before_request(req)  # type: ignore[arg-type]
    await mw.after_response(req, _FakeResponse(200))  # type: ignore[arg-type]

    spans = mem_exporter.get_finished_spans()
    assert len(spans) == 1
    assert format(spans[0].context.trace_id, "032x") == "4bf92f3577b16e0714f34b92bd2fa926"


@pytest.mark.asyncio
async def test_traceparent_injected_into_response(mem_exporter: InMemorySpanExporter) -> None:
    """after_response injects traceparent into response headers."""
    from hawkapi.responses.response import Response as HawkResponse  # noqa: PLC0415

    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest()
    resp = HawkResponse(content=b"ok", status_code=200)
    await mw.before_request(req)  # type: ignore[arg-type]
    await mw.after_response(req, resp)  # type: ignore[arg-type]

    assert "traceparent" in resp.headers


@pytest.mark.asyncio
async def test_http_route_from_scope(mem_exporter: InMemorySpanExporter) -> None:
    """http.route attribute is set from request.scope['route'].path."""

    class _FakeRoute:
        path = "/users/{user_id}"

    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest(path="/users/99", scope_extra={"route": _FakeRoute()})
    await mw.before_request(req)  # type: ignore[arg-type]
    await mw.after_response(req, _FakeResponse(200))  # type: ignore[arg-type]

    spans = mem_exporter.get_finished_spans()
    assert spans[0].attributes.get("http.route") == "/users/{user_id}"
    assert spans[0].name == "GET /users/{user_id}"


@pytest.mark.asyncio
async def test_always_off_sampler_produces_no_spans() -> None:
    """With ALWAYS_OFF sampler no spans are exported."""
    from opentelemetry.sdk.trace.sampling import ALWAYS_OFF  # noqa: PLC0415

    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_OFF)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    mw = OTelMiddleware(app=MagicMock())  # type: ignore[arg-type]
    req = _FakeRequest()
    await mw.before_request(req)  # type: ignore[arg-type]
    await mw.after_response(req, _FakeResponse(200))  # type: ignore[arg-type]

    assert len(exporter.get_finished_spans()) == 0
