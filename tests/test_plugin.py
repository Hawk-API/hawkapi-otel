"""Tests for OTelPlugin lifecycle."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from hawkapi_otel._plugin import OTelPlugin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plugin(**kwargs: object) -> OTelPlugin:
    """Build an OTelPlugin with patched exporters (no real network)."""
    defaults: dict[str, object] = {
        "service_name": "test-svc",
        "protocol": "grpc",
        "endpoint": "http://localhost:4317",
        "insecure": True,
        "enable_metrics": False,
        "enable_logs": False,
    }
    defaults.update(kwargs)
    return OTelPlugin(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# on_startup — tracer provider
# ---------------------------------------------------------------------------


def test_on_startup_sets_tracer_provider() -> None:
    """on_startup registers a TracerProvider globally."""
    with patch("hawkapi_otel._plugin.build_span_exporter", return_value=MagicMock()):
        plugin = _make_plugin()
        plugin.on_startup()
    assert isinstance(trace.get_tracer_provider(), TracerProvider)


def test_on_startup_enable_metrics_sets_meter_provider() -> None:
    """enable_metrics=True registers a MeterProvider globally."""
    with (
        patch("hawkapi_otel._plugin.build_span_exporter", return_value=MagicMock()),
        patch("hawkapi_otel._plugin.build_metric_exporter", return_value=MagicMock()),
    ):
        plugin = _make_plugin(enable_metrics=True)
        plugin.on_startup()
    assert isinstance(metrics.get_meter_provider(), MeterProvider)


def test_on_startup_console_exporter_adds_processor() -> None:
    """console_exporter=True adds an extra BatchSpanProcessor."""
    with patch("hawkapi_otel._plugin.build_span_exporter", return_value=MagicMock()):
        plugin = _make_plugin(console_exporter=True)
        plugin.on_startup()
    assert plugin._tracer_provider is not None
    processors = plugin._tracer_provider._active_span_processor._span_processors  # type: ignore[attr-defined]
    assert len(processors) == 2


def test_on_startup_enable_logs_calls_setup_logs() -> None:
    """enable_logs=True calls _setup_logs."""
    with (
        patch("hawkapi_otel._plugin.build_span_exporter", return_value=MagicMock()),
        patch.object(OTelPlugin, "_setup_logs") as mock_setup,
    ):
        plugin = _make_plugin(enable_logs=True)
        plugin.on_startup()
    mock_setup.assert_called_once()


# ---------------------------------------------------------------------------
# on_shutdown
# ---------------------------------------------------------------------------


def test_on_shutdown_calls_force_flush_and_shutdown() -> None:
    """on_shutdown flushes and shuts down all providers."""
    plugin = _make_plugin()
    tp = MagicMock()
    mp = MagicMock()
    plugin._tracer_provider = tp
    plugin._meter_provider = mp

    plugin.on_shutdown()

    tp.force_flush.assert_called_once_with(timeout_millis=2000)
    tp.shutdown.assert_called_once()
    mp.force_flush.assert_called_once_with(timeout_millis=2000)
    mp.shutdown.assert_called_once()


def test_on_shutdown_noop_when_no_providers() -> None:
    """on_shutdown does not raise when providers were never set."""
    plugin = _make_plugin()
    plugin.on_shutdown()  # must not raise


# ---------------------------------------------------------------------------
# on_exception
# ---------------------------------------------------------------------------


def test_on_exception_records_on_current_span() -> None:
    """on_exception records the exception on the active span and sets ERROR status."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer("test")
    plugin = _make_plugin(record_exceptions=True)

    with tracer.start_as_current_span("test-span"):
        plugin.on_exception(MagicMock(), ValueError("boom"))

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    assert any(e.name == "exception" for e in finished[0].events)
    assert finished[0].status.status_code == StatusCode.ERROR


def test_on_exception_noop_when_record_exceptions_false() -> None:
    """on_exception does nothing when record_exceptions=False."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer("test")
    plugin = _make_plugin(record_exceptions=False)

    with tracer.start_as_current_span("test-span"):
        plugin.on_exception(MagicMock(), ValueError("ignored"))

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    assert finished[0].status.status_code != StatusCode.ERROR


# ---------------------------------------------------------------------------
# headers forwarded to exporter
# ---------------------------------------------------------------------------


def test_headers_forwarded_to_span_exporter() -> None:
    """headers dict is passed through to build_span_exporter."""
    hdrs = {"x-honeycomb-team": "secret"}
    captured: dict[str, object] = {}

    def fake_build(protocol: str, endpoint: str, insecure: bool, headers: object) -> MagicMock:
        captured["headers"] = headers
        return MagicMock()

    with patch("hawkapi_otel._plugin.build_span_exporter", side_effect=fake_build):
        plugin = _make_plugin(headers=hdrs)
        plugin.on_startup()

    assert captured["headers"] == hdrs


# ---------------------------------------------------------------------------
# protocol selection
# ---------------------------------------------------------------------------


def test_http_protobuf_protocol_passed_to_exporter(monkeypatch: pytest.MonkeyPatch) -> None:
    """protocol='http/protobuf' is forwarded to build_span_exporter."""
    called_with: list[str] = []

    def fake_build(protocol: str, endpoint: str, insecure: bool, headers: object) -> MagicMock:
        called_with.append(protocol)
        return MagicMock()

    monkeypatch.setattr("hawkapi_otel._plugin.build_span_exporter", fake_build)
    plugin = _make_plugin(protocol="http/protobuf")
    plugin.on_startup()

    assert called_with == ["http/protobuf"]
