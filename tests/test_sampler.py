"""Tests for parse_sampler."""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    TraceIdRatioBased,
)

from hawkapi_otel._sampler import parse_sampler


def test_always_on() -> None:
    """parse_sampler('always_on') returns ALWAYS_ON."""
    assert parse_sampler("always_on") is ALWAYS_ON


def test_always_off() -> None:
    """parse_sampler('always_off') returns ALWAYS_OFF."""
    assert parse_sampler("always_off") is ALWAYS_OFF


def test_traceidratio() -> None:
    """parse_sampler('traceidratio', 0.1) returns TraceIdRatioBased(0.1)."""
    sampler = parse_sampler("traceidratio", 0.1)
    assert isinstance(sampler, TraceIdRatioBased)


def test_parentbased_always_on() -> None:
    """parse_sampler('parentbased_always_on') returns ParentBased(ALWAYS_ON)."""
    sampler = parse_sampler("parentbased_always_on")
    assert isinstance(sampler, ParentBased)


def test_parentbased_always_off() -> None:
    """parse_sampler('parentbased_always_off') returns ParentBased(ALWAYS_OFF)."""
    sampler = parse_sampler("parentbased_always_off")
    assert isinstance(sampler, ParentBased)


def test_parentbased_traceidratio() -> None:
    """parse_sampler('parentbased_traceidratio', 0.5) wraps TraceIdRatioBased."""
    sampler = parse_sampler("parentbased_traceidratio", 0.5)
    assert isinstance(sampler, ParentBased)


def test_invalid_name_raises() -> None:
    """parse_sampler with an unknown name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown traces_sampler"):
        parse_sampler("invalid")


def test_traceidratio_missing_arg_raises() -> None:
    """parse_sampler('traceidratio', None) raises ValueError."""
    with pytest.raises(ValueError, match="requires traces_sampler_arg"):
        parse_sampler("traceidratio", None)


def test_parentbased_traceidratio_missing_arg_raises() -> None:
    """parse_sampler('parentbased_traceidratio') without arg raises ValueError."""
    with pytest.raises(ValueError, match="requires traces_sampler_arg"):
        parse_sampler("parentbased_traceidratio")
