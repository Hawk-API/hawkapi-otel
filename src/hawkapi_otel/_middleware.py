"""OTelMiddleware — per-request OpenTelemetry server span."""

from __future__ import annotations

from typing import Any

from hawkapi.middleware.base import Middleware
from hawkapi.requests.request import Request
from hawkapi.responses.json_response import JSONResponse
from hawkapi.responses.response import Response
from opentelemetry import context as otel_context
from opentelemetry import propagate, trace
from opentelemetry.trace import NonRecordingSpan, SpanKind, Status, StatusCode, set_span_in_context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_PROPAGATOR = TraceContextTextMapPropagator()


class OTelMiddleware(Middleware):
    """Starts an OTel server span for every HTTP request."""

    async def before_request(self, request: Request) -> Request | Response | JSONResponse | None:
        """Extract incoming trace context, start a server span, set HTTP attributes."""
        # Build a carrier from request headers for W3C propagation
        carrier: dict[str, str] = {}
        for key, value in request.headers:
            carrier[key.lower()] = value

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
            span.set_attribute("url.query", qs)

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
