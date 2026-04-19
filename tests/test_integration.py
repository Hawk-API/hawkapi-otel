"""Integration test: OTelPlugin + OTelMiddleware with a real HawkAPI app."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from hawkapi_otel import OTelMiddleware, OTelPlugin


@pytest.mark.asyncio
async def test_full_app_span_exported_with_correct_attributes() -> None:
    """End-to-end: request through HawkAPI app produces a span with HTTP attributes."""
    from hawkapi import HawkAPI  # noqa: PLC0415

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    app = HawkAPI(title="test-app")

    with patch("hawkapi_otel._plugin.build_span_exporter", return_value=MagicMock()):
        plugin = OTelPlugin(
            service_name="integration-svc",
            enable_metrics=False,
            enable_logs=False,
        )
        app.add_plugin(plugin)
        plugin.on_startup()

    app.add_middleware(OTelMiddleware)

    @app.get("/ping")
    async def _ping() -> dict[str, str]:
        return {"status": "ok"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/ping")

    assert resp.status_code == 200

    spans = exporter.get_finished_spans()
    assert len(spans) >= 1

    span = spans[0]
    assert span.attributes.get("http.request.method") == "GET"
    assert span.attributes.get("url.path") == "/ping"
    assert span.attributes.get("http.response.status_code") == 200
