"""Lazy OTLP exporter factories for traces, metrics, and logs."""

from __future__ import annotations

from typing import Any


def build_span_exporter(
    protocol: str,
    endpoint: str,
    insecure: bool,
    headers: dict[str, str] | None,
) -> Any:
    """Return an OTLP span exporter for the given protocol.

    Imports are deferred so unused transports are never loaded.
    """
    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(
            endpoint=endpoint,
            insecure=insecure,
            headers=headers,
        )
    if protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(
            endpoint=endpoint,
            headers=headers,
        )
    raise ValueError(f"Unknown OTLP protocol {protocol!r}. Use 'grpc' or 'http/protobuf'.")


def build_metric_exporter(
    protocol: str,
    endpoint: str,
    insecure: bool,
    headers: dict[str, str] | None,
) -> Any:
    """Return an OTLP metric exporter for the given protocol."""
    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (  # noqa: PLC0415
            OTLPMetricExporter,
        )

        return OTLPMetricExporter(
            endpoint=endpoint,
            insecure=insecure,
            headers=headers,
        )
    if protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (  # noqa: PLC0415
            OTLPMetricExporter,
        )

        return OTLPMetricExporter(
            endpoint=endpoint,
            headers=headers,
        )
    raise ValueError(f"Unknown OTLP protocol {protocol!r}. Use 'grpc' or 'http/protobuf'.")


def build_log_exporter(
    protocol: str,
    endpoint: str,
    insecure: bool,
    headers: dict[str, str] | None,
) -> Any:
    """Return an OTLP log exporter for the given protocol."""
    if protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (  # noqa: PLC0415
            OTLPLogExporter,
        )

        return OTLPLogExporter(
            endpoint=endpoint,
            insecure=insecure,
            headers=headers,
        )
    if protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (  # noqa: PLC0415
            OTLPLogExporter,
        )

        return OTLPLogExporter(
            endpoint=endpoint,
            headers=headers,
        )
    raise ValueError(f"Unknown OTLP protocol {protocol!r}. Use 'grpc' or 'http/protobuf'.")
