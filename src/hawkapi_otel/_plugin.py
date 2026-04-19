"""OTelPlugin — HawkAPI Plugin that initialises the OpenTelemetry SDK."""

from __future__ import annotations

import logging
from typing import Any

from hawkapi.plugins import Plugin
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

from hawkapi_otel._exporters import build_log_exporter, build_metric_exporter, build_span_exporter
from hawkapi_otel._resource import build_resource
from hawkapi_otel._sampler import parse_sampler

logger = logging.getLogger("hawkapi_otel")


class OTelPlugin(Plugin):
    """HawkAPI plugin that wires OpenTelemetry tracing, metrics, and logs."""

    def __init__(
        self,
        *,
        service_name: str = "unknown_service",
        service_version: str | None = None,
        endpoint: str = "http://localhost:4317",
        protocol: str = "grpc",
        insecure: bool = True,
        headers: dict[str, str] | None = None,
        resource_attributes: dict[str, str] | None = None,
        traces_sampler: str = "parentbased_always_on",
        traces_sampler_arg: float | None = None,
        enable_metrics: bool = True,
        enable_logs: bool = False,
        console_exporter: bool = False,
        record_exceptions: bool = True,
    ) -> None:
        self._service_name = service_name
        self._service_version = service_version
        self._endpoint = endpoint
        self._protocol = protocol
        self._insecure = insecure
        self._headers = headers
        self._resource_attributes = resource_attributes
        self._traces_sampler = traces_sampler
        self._traces_sampler_arg = traces_sampler_arg
        self._enable_metrics = enable_metrics
        self._enable_logs = enable_logs
        self._console_exporter = console_exporter
        self._record_exceptions = record_exceptions

        self._tracer_provider: TracerProvider | None = None
        self._meter_provider: MeterProvider | None = None
        self._logger_provider: Any = None

    # ------------------------------------------------------------------
    # Plugin hooks
    # ------------------------------------------------------------------

    def on_startup(self) -> None:
        """Initialise OTel SDK providers and register them globally."""
        resource = build_resource(
            self._service_name,
            self._service_version,
            self._resource_attributes,
        )
        sampler = parse_sampler(self._traces_sampler, self._traces_sampler_arg)

        # Traces
        span_exporter = build_span_exporter(
            self._protocol, self._endpoint, self._insecure, self._headers
        )
        tracer_provider = TracerProvider(resource=resource, sampler=sampler)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        if self._console_exporter:
            tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(tracer_provider)
        self._tracer_provider = tracer_provider

        # Metrics
        if self._enable_metrics:
            metric_exporter = build_metric_exporter(
                self._protocol, self._endpoint, self._insecure, self._headers
            )
            reader = PeriodicExportingMetricReader(metric_exporter)
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(meter_provider)
            self._meter_provider = meter_provider

        # Logs
        if self._enable_logs:
            self._setup_logs(resource)

        logger.info(
            "hawkapi_otel: OpenTelemetry initialised "
            "(service=%s, protocol=%s, metrics=%s, logs=%s)",
            self._service_name,
            self._protocol,
            self._enable_metrics,
            self._enable_logs,
        )

    def on_shutdown(self) -> None:
        """Flush and shut down all OTel providers."""
        if self._tracer_provider is not None:
            self._tracer_provider.force_flush(timeout_millis=2000)
            self._tracer_provider.shutdown()
        if self._meter_provider is not None:
            self._meter_provider.force_flush(timeout_millis=2000)
            self._meter_provider.shutdown()
        if self._logger_provider is not None:
            self._logger_provider.force_flush(timeout_millis=2000)
            self._logger_provider.shutdown()

    def on_exception(self, request: Any, exc: Exception) -> None:
        """Record the exception on the current span when record_exceptions=True."""
        if not self._record_exceptions:
            return
        span = trace.get_current_span()
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _setup_logs(self, resource: Any) -> None:
        """Wire OTLP log export and attach a LoggingHandler to the root logger."""
        from opentelemetry._logs import set_logger_provider  # noqa: PLC0415
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler  # noqa: PLC0415
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor  # noqa: PLC0415

        log_exporter = build_log_exporter(
            self._protocol, self._endpoint, self._insecure, self._headers
        )
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        set_logger_provider(logger_provider)
        self._logger_provider = logger_provider

        handler = LoggingHandler(logger_provider=logger_provider)
        logging.getLogger().addHandler(handler)
