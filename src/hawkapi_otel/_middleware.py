"""OTelMiddleware — per-request OpenTelemetry server span."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, quote

from hawkapi.middleware.base import Middleware
from hawkapi.requests.request import Request
from hawkapi.responses.json_response import JSONResponse
from hawkapi.responses.response import Response
from opentelemetry import context as otel_context
from opentelemetry import propagate, trace
from opentelemetry.trace import NonRecordingSpan, SpanKind, Status, StatusCode, set_span_in_context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_PROPAGATOR = TraceContextTextMapPropagator()

# Only these headers are forwarded into the OTel propagation extractor.
# Forwarding arbitrary request headers (e.g. ``Authorization``) into OTel's
# carrier dict can leak credentials into downstream propagation handling
# and trace logs (CWE-200).
PROPAGATION_HEADERS: frozenset[str] = frozenset(["traceparent", "tracestate", "baggage"])

_DEFAULT_SENSITIVE_QUERY_PARAMS: frozenset[str] = frozenset(
    {
        "token",
        "key",
        "api_key",
        "password",
        "secret",
        "access_token",
        "refresh_token",
    }
)
_REDACTED_VALUE = "***"


def _redact_query(qs: str, sensitive: frozenset[str] | None) -> str:
    if not qs:
        return qs
    targets = sensitive if sensitive is not None else _DEFAULT_SENSITIVE_QUERY_PARAMS
    targets = frozenset(t.lower() for t in targets)
    parts: list[str] = []
    for k, v in parse_qsl(qs, keep_blank_values=True):
        if k.lower() in targets:
            parts.append(f"{quote(k, safe='')}={_REDACTED_VALUE}")
        else:
            parts.append(f"{quote(k, safe='')}={quote(v, safe='')}")
    return "&".join(parts)


def _plugin_for(request: Request) -> Any:
    app = request.scope.get("app") if isinstance(request.scope, dict) else None
    if app is None:
        return None
    for attr in ("plugins", "_plugins"):
        plugins = getattr(app, attr, None)
        if plugins is None:
            continue
        for plugin in plugins:
            if plugin.__class__.__name__ == "OTelPlugin":
                return plugin
    return None


class OTelMiddleware(Middleware):
    """Starts an OTel server span for every HTTP request."""

    async def before_request(self, request: Request) -> Request | Response | JSONResponse | None:
        """Extract incoming trace context, start a server span, set HTTP attributes."""
        # Only forward W3C trace-context / baggage headers into the extractor.
        carrier: dict[str, str] = {
            k.lower(): v for k, v in request.headers if k.lower() in PROPAGATION_HEADERS
        }

        ctx = propagate.extract(carrier)
        token = otel_context.attach(ctx)
        request.state._otel_ctx_token = token  # type: ignore[attr-defined]

        method: str = request.method.upper()
        path: str = request.path
        span_name = f"{method} {path}"

        tracer = trace.get_tracer("hawkapi_otel")
        span = tracer.start_span(
            span_name,
            context=ctx,
            kind=SpanKind.SERVER,
        )

        # OTel HTTP semantic conventions (stable v1.x)
        span.set_attribute("http.request.method", method)
        span.set_attribute("url.path", path)
        span.set_attribute("url.scheme", request.url_scheme)
        span.set_attribute("network.protocol.name", "http")

        qs_raw = request.query_string
        qs: str = qs_raw.decode("latin-1") if qs_raw else ""
        if qs:
            plugin = _plugin_for(request)
            sensitive: frozenset[str] | None = (
                getattr(plugin, "sensitive_query_params", None) if plugin is not None else None
            )
            span.set_attribute("url.query", _redact_query(qs, sensitive))

        ua = request.headers.get("user-agent")
        if ua:
            span.set_attribute("user_agent.original", ua)

        client = request.client
        if client is not None:
            span.set_attribute("client.address", client[0])

        host = request.headers.get("host")
        if host:
            span.set_attribute("server.address", host)

        request.state._otel_span = span  # type: ignore[attr-defined]
        return None

    async def after_response(
        self, request: Request, response: Response | JSONResponse
    ) -> Response | JSONResponse | None:
        """Finish the span: set status, route, response code, inject traceparent."""
        span: Any = getattr(getattr(request, "state", None), "_otel_span", None)
        token: Any = getattr(getattr(request, "state", None), "_otel_ctx_token", None)

        if span is None or isinstance(span, NonRecordingSpan):
            return None

        status_code: int = response.status_code
        span.set_attribute("http.response.status_code", status_code)

        # Refine span name from route template if available
        route: Any = request.scope.get("route")  # type: ignore[union-attr]
        if route is not None:
            route_path: str | None = getattr(route, "path", None)
            if route_path:
                method = request.method.upper()
                span.update_name(f"{method} {route_path}")
                span.set_attribute("http.route", route_path)

        # OTel HTTP semconv: only ERROR for 5xx server spans
        if status_code >= 500:
            span.set_status(Status(StatusCode.ERROR, description="HTTP 5xx"))

        # Inject traceparent before ending the span so context is still valid
        carrier: dict[str, str] = {}
        span_ctx = set_span_in_context(span)
        propagate.inject(carrier, context=span_ctx)
        if isinstance(response, Response):
            for k, v in carrier.items():
                response.headers[k] = v

        span.end()

        if token is not None:
            otel_context.detach(token)

        return None
