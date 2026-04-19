"""Parse sampler name strings into OpenTelemetry Sampler instances."""

from __future__ import annotations

from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)

_RATIO_SAMPLERS = frozenset(["traceidratio", "parentbased_traceidratio"])

_VALID = frozenset(
    [
        "always_on",
        "always_off",
        "traceidratio",
        "parentbased_always_on",
        "parentbased_always_off",
        "parentbased_traceidratio",
    ]
)


def parse_sampler(name: str, arg: float | None = None) -> Sampler:
    """Translate a sampler name string to an OTel Sampler instance.

    Raises ValueError for unknown names or missing ratio argument.
    """
    if name not in _VALID:
        raise ValueError(
            f"Unknown traces_sampler {name!r}. Valid values: {', '.join(sorted(_VALID))}"
        )
    if name in _RATIO_SAMPLERS and arg is None:
        raise ValueError(f"traces_sampler {name!r} requires traces_sampler_arg (a float ratio).")

    if name == "always_on":
        return ALWAYS_ON
    if name == "always_off":
        return ALWAYS_OFF
    if name == "traceidratio":
        return TraceIdRatioBased(arg)  # type: ignore[arg-type]
    if name == "parentbased_always_on":
        return ParentBased(ALWAYS_ON)
    if name == "parentbased_always_off":
        return ParentBased(ALWAYS_OFF)
    # parentbased_traceidratio
    return ParentBased(TraceIdRatioBased(arg))  # type: ignore[arg-type]
