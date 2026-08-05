"""Backend registry (spec §3.6).

Backends are registered, never imported by core. Discovery is the [D125]
entry-point group `qtviz.backends` — the built-ins declare theirs in
pyproject, and a third-party backend registers with zero qtviz edits. One
INFO log per optional backend whose import fails; explicit `register()`
stays for tests/embedding. This module holds the process-global registry,
priority order, and default — the surface `negotiate` reads.
"""

from __future__ import annotations

from typing import Any

from ..errors import BackendNotAvailableError

_REGISTRY: dict[str, Any] = {}
_PRIORITY: list[str] = []
_DEFAULT: str | None = None


def register(backend: Any) -> None:
    _REGISTRY[backend.name] = backend
    if backend.name not in _PRIORITY:
        _PRIORITY.append(backend.name)


def unregister(name: str) -> None:
    _REGISTRY.pop(name, None)
    _PRIORITY[:] = [n for n in _PRIORITY if n in _REGISTRY]
    global _DEFAULT
    if name == _DEFAULT:
        _DEFAULT = None


def get(name: str) -> Any:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise BackendNotAvailableError(
            f"backend {name!r} not available; registered: {list(_REGISTRY)}"
        ) from None


def list_available() -> list[str]:
    return list(_REGISTRY)


def registered() -> list[Any]:
    return list(_REGISTRY.values())


def set_default_backend(name: str) -> None:
    """Set the backend used when a `View` is created with `backend="auto"` and no hint.

    Validated eagerly: an unregistered name raises here rather than surfacing
    later, deep inside negotiation, far from this call.
    """
    if name not in _REGISTRY:
        raise BackendNotAvailableError(
            f"cannot set default backend to {name!r}; registered: {list(_REGISTRY)}"
        )
    global _DEFAULT
    _DEFAULT = name


def set_backend_priority(names) -> None:
    """Set the preference order `auto_negotiate` tries when several backends qualify.

    Lenient by design: a name need not be registered (an optional backend may
    be installed later) — unregistered names simply sort last in `auto_negotiate`.
    """
    _PRIORITY[:] = list(names)


def global_default() -> str | None:
    if _DEFAULT:
        return _DEFAULT
    if _PRIORITY:
        return _PRIORITY[0]
    return next(iter(_REGISTRY), None)


def priority_index(name: str) -> int:
    return _PRIORITY.index(name) if name in _PRIORITY else len(_PRIORITY)


# canonical priority for the built-ins; third-party backends sort after, by name
_BUILTIN_ORDER = ("pyqtgraph", "matplotlib", "webengine")


def _autoregister() -> None:
    """[D125] entry-point discovery (group `qtviz.backends`). An optional
    backend whose import fails logs one INFO; anything else failing logs a
    warning. Falls back to the built-in list when no entry points are visible
    (a stale editable install) so a working checkout never loses backends."""
    import logging
    from importlib.metadata import entry_points

    log = logging.getLogger("qtviz")
    eps = list(entry_points(group="qtviz.backends"))
    if not eps:  # pragma: no cover — stale metadata; behave like the built-ins
        from importlib.metadata import EntryPoint  # noqa: PLC0415

        eps = [EntryPoint(name, value, "qtviz.backends") for name, value in (
            ("pyqtgraph", "qtviz.backends.pyqtgraph:backend"),
            ("matplotlib", "qtviz.backends.matplotlib:backend"),
            ("webengine", "qtviz.backends.webengine.render:backend"),
        )]
    def _order(ep):
        return (_BUILTIN_ORDER.index(ep.name) if ep.name in _BUILTIN_ORDER
                else len(_BUILTIN_ORDER)), ep.name
    for ep in sorted(eps, key=_order):
        try:
            register(ep.load())
        except ImportError:
            log.info('%s backend unavailable; install with: pip install "qtviz[%s]" '
                     '(uv: uv add "qtviz[%s]")', ep.name, ep.name, ep.name)
        except Exception as e:
            log.warning("%s backend failed to load: %s", ep.name, e)


_autoregister()

