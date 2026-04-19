"""Tests for build_resource."""

from __future__ import annotations

from hawkapi_otel._resource import build_resource


def test_resource_service_name() -> None:
    """Resource contains service.name."""
    r = build_resource("my-svc", "1.0", None)
    assert r.attributes["service.name"] == "my-svc"


def test_resource_service_version() -> None:
    """Resource contains service.version when provided."""
    r = build_resource("svc", "2.3.1", None)
    assert r.attributes["service.version"] == "2.3.1"


def test_resource_no_version() -> None:
    """Resource does not contain service.version when None."""
    r = build_resource("svc", None, None)
    assert "service.version" not in r.attributes


def test_resource_instance_id_present() -> None:
    """Resource always includes service.instance.id as a non-empty hex string."""
    r = build_resource("svc", "1.0", None)
    instance_id = r.attributes.get("service.instance.id")
    assert isinstance(instance_id, str)
    assert len(instance_id) == 32
    int(instance_id, 16)  # valid hex


def test_resource_instance_id_unique() -> None:
    """Each call produces a different service.instance.id."""
    r1 = build_resource("svc", "1.0", None)
    r2 = build_resource("svc", "1.0", None)
    assert r1.attributes["service.instance.id"] != r2.attributes["service.instance.id"]


def test_resource_extra_attributes() -> None:
    """Extra attributes (e.g. deployment.environment) appear in the resource."""
    r = build_resource("svc", "1.0", {"deployment.environment": "prod"})
    assert r.attributes["deployment.environment"] == "prod"


def test_resource_multiple_extra_attributes() -> None:
    """Multiple extra attributes are all present."""
    extras = {"deployment.environment": "staging", "region": "eu-west-1"}
    r = build_resource("svc", "1.0", extras)
    assert r.attributes["deployment.environment"] == "staging"
    assert r.attributes["region"] == "eu-west-1"
