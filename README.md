# hawkapi-otel

[![PyPI](https://img.shields.io/pypi/v/hawkapi-otel)](https://pypi.org/project/hawkapi-otel/)
[![Python](https://img.shields.io/pypi/pyversions/hawkapi-otel)](https://pypi.org/project/hawkapi-otel/)
[![License](https://img.shields.io/pypi/l/hawkapi-otel)](LICENSE)
[![CI](https://github.com/ashimov/hawkapi-otel/actions/workflows/ci.yml/badge.svg)](https://github.com/ashimov/hawkapi-otel/actions/workflows/ci.yml)
[![Downloads](https://img.shields.io/pypi/dm/hawkapi-otel)](https://pypi.org/project/hawkapi-otel/)

OpenTelemetry integration for [HawkAPI](https://github.com/ashimov/HawkAPI) — a plugin that initialises the OTel SDK on startup and a middleware that creates a server span per request, with full W3C trace-context propagation.

Works out of the box with a local OTLP collector. One-liner configs for Honeycomb, Grafana Cloud, Datadog, and Jaeger are listed below.

---

## Quickstart

```bash
pip install hawkapi-otel
```

```python
from hawkapi import HawkAPI
from hawkapi_otel import OTelPlugin, OTelMiddleware

app = HawkAPI()

app.add_plugin(
    OTelPlugin(
        service_name="my-app",
        service_version="1.0.0",
        endpoint="http://localhost:4317",
        protocol="grpc",
        insecure=True,
    )
)
app.add_middleware(OTelMiddleware)
```

Every request gets a server span with HTTP semantic-convention attributes. Unhandled exceptions are recorded on the current span.

---

## `OTelPlugin` parameter reference

| Parameter | Type | Default | Description |
|---|---|---|---|
| `service_name` | `str` | `"unknown_service"` | `service.name` resource attribute. |
| `service_version` | `str \| None` | `None` | `service.version` resource attribute. |
| `endpoint` | `str` | `"http://localhost:4317"` | OTLP collector endpoint. |
| `protocol` | `str` | `"grpc"` | `"grpc"` or `"http/protobuf"`. |
| `insecure` | `bool` | `True` | Disable TLS (useful for local collectors). |
| `headers` | `dict[str, str] \| None` | `None` | Extra headers — API keys for Honeycomb, Grafana Cloud, etc. |
| `resource_attributes` | `dict[str, str] \| None` | `None` | Arbitrary extra resource attributes. |
| `traces_sampler` | `str` | `"parentbased_always_on"` | Sampler name. See sampler reference below. |
| `traces_sampler_arg` | `float \| None` | `None` | Ratio for `traceidratio` / `parentbased_traceidratio`. |
| `enable_metrics` | `bool` | `True` | Build a `MeterProvider` with OTLP metric export. |
| `enable_logs` | `bool` | `False` | Attach `LoggingHandler` to root logger + OTLP log export. |
| `console_exporter` | `bool` | `False` | Also add a `ConsoleSpanExporter` (debug). |
| `record_exceptions` | `bool` | `True` | Call `span.record_exception()` in `on_exception`. |

### Sampler reference

| `traces_sampler` value | Behaviour |
|---|---|
| `"always_on"` | Sample every trace. |
| `"always_off"` | Sample nothing. |
| `"traceidratio"` | Sample `traces_sampler_arg` fraction (e.g. `0.1` = 10%). |
| `"parentbased_always_on"` | Respect parent; default to always-on. **(default)** |
| `"parentbased_always_off"` | Respect parent; default to always-off. |
| `"parentbased_traceidratio"` | Respect parent; default to ratio sampling. |

---

## Vendor recipes

**Honeycomb**
```python
OTelPlugin(
    service_name="my-app",
    endpoint="https://api.honeycomb.io",
    protocol="http/protobuf",
    insecure=False,
    headers={"x-honeycomb-team": "YOUR_API_KEY"},
)
```

**Grafana Cloud**
```python
OTelPlugin(
    service_name="my-app",
    endpoint="https://otlp-gateway-prod-eu-west-0.grafana.net/otlp",
    protocol="http/protobuf",
    insecure=False,
    headers={"authorization": "Basic BASE64_ENCODED_INSTANCE_ID:TOKEN"},
)
```

**Datadog (OTLP intake)**
```python
OTelPlugin(
    service_name="my-app",
    endpoint="https://api.datadoghq.com",
    protocol="http/protobuf",
    insecure=False,
    headers={"dd-api-key": "YOUR_DD_API_KEY"},
)
```

**Jaeger (local)**
```python
OTelPlugin(
    service_name="my-app",
    endpoint="http://localhost:4317",
    protocol="grpc",
    insecure=True,
)
```

---

## Development

```bash
# Clone and install in editable mode with dev extras
git clone https://github.com/ashimov/hawkapi-otel.git
cd hawkapi-otel
uv sync --extra dev

# Run tests
uv run pytest tests/ -q

# Lint
uv run ruff check .
uv run ruff format .

# Type-check
uv run pyright src/
```

---

## License

[MIT](LICENSE) — Copyright (c) 2026 HawkAPI Contributors.
