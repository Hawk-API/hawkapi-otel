# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-19

### Added

- `OTelPlugin` — HawkAPI `Plugin` subclass that initialises OpenTelemetry on startup,
  flushes all providers on shutdown, and records exceptions on the current span via
  `on_exception`.
- `OTelMiddleware` — HawkAPI `Middleware` subclass that starts a server span per request,
  propagates W3C `traceparent`/`tracestate`/`baggage` context from incoming headers, and
  injects `traceparent` into outgoing response headers.
- `OTelPlugin` parameters: `service_name`, `service_version`, `endpoint`, `protocol`
  (`"grpc"` or `"http/protobuf"`), `insecure`, `headers`, `resource_attributes`,
  `traces_sampler`, `traces_sampler_arg`, `enable_metrics`, `enable_logs`,
  `console_exporter`, `record_exceptions`.
- Sampler string resolution: `always_on`, `always_off`, `traceidratio`,
  `parentbased_always_on` (default), `parentbased_always_off`,
  `parentbased_traceidratio`.
- Resource building: `service.name`, `service.version`, `service.instance.id` (uuid4),
  plus arbitrary user-supplied attributes.
- Lazy OTLP exporter imports — gRPC or HTTP/protobuf selected at runtime based on
  `protocol`.
- Optional metrics pipeline: `MeterProvider` + `PeriodicExportingMetricReader`.
- Optional logs pipeline: `LoggerProvider` + `BatchLogRecordProcessor` +
  `LoggingHandler` attached to the root logger.
- OTel HTTP semantic conventions (stable v1.x): `http.request.method`, `url.path`,
  `url.scheme`, `url.query`, `network.protocol.name`, `user_agent.original`,
  `client.address`, `server.address`, `http.response.status_code`, `http.route`.
- Span status: `ERROR` for 5xx responses; unset otherwise (per OTel HTTP semconv).
- Full test suite (25 tests) covering sampler parsing, resource building, plugin
  lifecycle, middleware span attributes, context propagation, status mapping, and
  an end-to-end integration test with a real HawkAPI app via `httpx.AsyncClient`.
- CI workflow: lint (`ruff`), typecheck (`pyright` strict), test matrix (Python 3.12 + 3.13).
- Release workflow: build with `uv build`, publish via PyPI trusted publishing.

[Unreleased]: https://github.com/ashimov/hawkapi-otel/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ashimov/hawkapi-otel/releases/tag/v0.1.0
