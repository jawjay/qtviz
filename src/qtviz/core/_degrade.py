"""Honor-or-warn degradation for *recommended* options (spec §3.4, [D51]).

The contract qtviz declared in 0.1 but never enforced: a backend honors what it
can and **warns** (never silently drops) for a recommended option it does not
support. Each backend declares, per element type, the recommended options it
honors; `check_recommended` warns **once** per `(backend, element_type, option)`
for any recommended option set to a *non-default* value the backend doesn't
honor. It never raises — rendering proceeds (the honor-or-warn policy, over
fail-fast).

This is the seam the per-backend `HONORED` tables + the conformance test
(`test_backend_conformance.py`) keep honest, so "never silent" is enforced by a
test rather than convention (root cause R4 in `weakness-root-causes.md`).
"""

from __future__ import annotations

import inspect
import warnings
from functools import cache

from ..errors import QtvizWarning

# Warn-once registry, keyed (backend_name, element_type_name, option). Process-
# lifetime; `reset()` clears it (tests, or a fresh interpreter otherwise).
_warned: set[tuple[str, str, str]] = set()


@cache
def _defaults(cls: type) -> dict:
    """`{param: default}` for an element's __init__ — the baseline a field must
    differ from to count as user-set. Cached per class (hot path: every render)."""
    try:
        params = inspect.signature(cls.__init__).parameters  # type: ignore[misc]  # deliberate introspection
    except (ValueError, TypeError):  # pragma: no cover - exotic __init__
        return {}
    return {n: p.default for n, p in params.items() if p.default is not inspect.Parameter.empty}


def _overridden(element, opt: str) -> bool:
    """Did the user set `opt` to something other than its constructor default?
    A default-valued recommended option never warns (so `Scatter()` is silent)."""
    defaults = _defaults(type(element))  # type: ignore[arg-type]  # a class is hashable
    if opt not in defaults:  # no known default → treat as explicitly set
        return True
    current = getattr(element, opt, defaults[opt])
    try:
        return bool(current != defaults[opt])
    except Exception:  # pragma: no cover - non-comparable value
        return current is not defaults[opt]


def check_recommended(element, *, backend_name: str, honored) -> None:
    """Warn once per `(backend, element_type, option)` for each recommended option
    set to a non-default value that `backend_name` does not honor. `honored` is a
    set/frozenset of option names this backend honors for `type(element)`."""
    et = type(element)
    for opt in getattr(et, "RECOMMENDED_OPTIONS", ()):
        if opt in honored or not _overridden(element, opt):
            continue
        key = (backend_name, et.__name__, opt)
        if key in _warned:
            continue
        _warned.add(key)
        warnings.warn(
            f"{backend_name}: '{opt}' on {et.__name__} is not honored by this "
            f"backend and was ignored. (spec §3.4 honor-or-warn)",
            QtvizWarning,
            stacklevel=3,
        )


def reset() -> None:
    """Clear the warn-once registry. For tests that assert the warning fires; in
    normal use the once-per-process semantics are the point."""
    _warned.clear()


# ── surface / layout option honesty ([D109]) ─────────────────────────────────
# Honor-or-warn covered *element* options only; surface-level silent no-ops
# kept slipping through (LayoutOptions.rows/spacing/title, pre-[D86]
# tick_format). Consumers declare what they honor; anything set non-default
# and unhonored warns once per (consumer, option).

_AXIS_FIELDS = ("label", "scale", "lim", "invert", "tick_format")
_SURFACE_FIELDS = ("title", "aspect", "legend", "legend_position", "background", "grid")
_LAYOUT_FIELDS = ("rows", "cols", "spacing", "link_x", "link_y",
                  "tab_labels", "dock_areas", "title")


def surface_overrides(surf) -> list[str]:
    """The `OverlayOptions` fields set to non-default values, axis fields
    prefixed (`x.lim`, `y.scale`, …); `y2` reported as one option."""
    from .options import AxisSpec, OverlayOptions  # noqa: PLC0415

    default = OverlayOptions()
    daxis = AxisSpec()
    out = [name for name in _SURFACE_FIELDS
           if getattr(surf, name) != getattr(default, name)]
    for ax_name in ("x", "y"):
        spec = getattr(surf, ax_name)
        out += [f"{ax_name}.{f}" for f in _AXIS_FIELDS
                if getattr(spec, f) != getattr(daxis, f)]
    if surf.y2 is not None:
        out.append("y2")
    return out


def _check_options(overrides, *, consumer: str, honored, kind: str) -> None:
    for opt in overrides:
        if opt in honored:
            continue
        key = (consumer, kind, opt)
        if key in _warned:
            continue
        _warned.add(key)
        warnings.warn(
            f"{consumer}: {kind} option '{opt}' is not honored here and was "
            f"ignored. ([D109] surface honor-or-warn)",
            QtvizWarning,
            stacklevel=3,
        )


def check_surface(surf, *, consumer: str, honored) -> None:
    """Warn once per set-but-unhonored `OverlayOptions`/`AxisSpec` field."""
    _check_options(surface_overrides(surf), consumer=consumer, honored=honored,
                   kind="surface")


def check_layout(opts, *, consumer: str, honored) -> None:
    """Warn once per set-but-unhonored `LayoutOptions` field."""
    from .options import LayoutOptions  # noqa: PLC0415

    default = LayoutOptions()
    overrides = [name for name in _LAYOUT_FIELDS
                 if getattr(opts, name) != getattr(default, name)]
    _check_options(overrides, consumer=consumer, honored=honored, kind="layout")


# Every OverlayOptions/AxisSpec field the three built-in backends honor today
# (the parity program wired them all); a third-party backend declares its own.
FULL_SURFACE = frozenset(
    {*_SURFACE_FIELDS, "y2",
     *(f"x.{f}" for f in _AXIS_FIELDS), *(f"y.{f}" for f in _AXIS_FIELDS)}
)
