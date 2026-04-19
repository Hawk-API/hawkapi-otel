"""Build an OpenTelemetry Resource for hawkapi-otel."""

from __future__ import annotations

import uuid
from typing import Any

from opentelemetry.sdk.resources import Resource


def build_resource(
    service_name: str,
    service_version: str | None,
    extra_attributes: dict[str, str] | None,
) -> Resource:
    """Return a Resource with service.* attributes plus any user-supplied extras.

    Always includes:
      - service.name
      - service.instance.id  (uuid4 hex, unique per process start)

    Includes when provided:
      - service.version
      - Any keys in extra_attributes (e.g. deployment.environment)
    """
    attrs: dict[str, Any] = {
        "service.name": service_name,
        "service.instance.id": uuid.uuid4().hex,
    }
    if service_version is not None:
        attrs["service.version"] = service_version
    if extra_attributes:
        attrs.update(extra_attributes)
    return Resource(attributes=attrs)
