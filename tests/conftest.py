"""Shared pytest fixtures for hawkapi-otel tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import opentelemetry.metrics._internal as _metrics_internal
import opentelemetry.trace as _trace_module
import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


def _reset_tracer_provider() -> None:
    """Force-reset the global OTel tracer provider to allow re-setting in tests."""
    _trace_module._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]
    _trace_module._TRACER_PROVIDER = None  # type: ignore[attr-defined]


def _reset_meter_provider() -> None:
    """Force-reset the global OTel meter provider to allow re-setting in tests."""
    _metrics_internal._METER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]
    _metrics_internal._METER_PROVIDER = None  # type: ignore[attr-defined]


@pytest.fixture()
def in_memory_exporter() -> InMemorySpanExporter:
    """Return a fresh InMemorySpanExporter."""
    return InMemorySpanExporter()


@pytest.fixture()
def tracer_provider(in_memory_exporter: InMemorySpanExporter) -> TracerProvider:
    """Return a TracerProvider wired to the in-memory exporter."""
    resource = Resource(attributes={"service.name": "test-service"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(in_memory_exporter))
    return provider


@pytest.fixture(autouse=True)
def reset_otel_providers() -> Generator[None, None, None]:
    """Isolate each test: reset global tracer and meter providers before and after."""
    _reset_tracer_provider()
    _reset_meter_provider()
    yield
    _reset_tracer_provider()
    _reset_meter_provider()


def make_tracer_provider(exporter: InMemorySpanExporter) -> TracerProvider:
    """Helper: build a TracerProvider backed by the given in-memory exporter."""
    provider = TracerProvider(resource=Resource(attributes={"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider


def make_metric_reader() -> tuple[MeterProvider, InMemoryMetricReader]:
    """Helper: build a MeterProvider with an InMemoryMetricReader."""
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return provider, reader


__all__: list[Any] = []
