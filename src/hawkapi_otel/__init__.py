"""hawkapi-otel — OpenTelemetry integration for HawkAPI."""

from __future__ import annotations

from hawkapi_otel._middleware import OTelMiddleware
from hawkapi_otel._plugin import OTelPlugin

__version__ = "0.2.0"

__all__ = [
    "OTelMiddleware",
    "OTelPlugin",
    "__version__",
]
