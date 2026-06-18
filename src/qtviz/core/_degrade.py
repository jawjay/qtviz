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
        params = inspect.signature(cls.__init__).parameters
    except (ValueError, TypeError):  # pragma: no cover - exotic __init__
        return {}
    return {n: p.default for n, p in params.items() if p.default is not inspect.Parameter.empty}


def _overridden(element, opt: str) -> bool:
    """Did the user set `opt` to something other than its constructor default?
    A default-valued recommended option never warns (so `Scatter()` is silent)."""
    defaults = _defaults(type(element))
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
