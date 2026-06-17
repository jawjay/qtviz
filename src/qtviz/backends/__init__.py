"""Backend registry (spec §3.6).

Backends are registered, never imported by core. Optional backends auto-detect
at import in a try/except (added as each backend lands). This module holds the
process-global registry, priority order, and default — the surface `negotiate`
reads.
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


def _autoregister() -> None:
    """Register the always-available pyqtgraph backend (hard dep), and any
    optional backends that import cleanly. One INFO log per missing optional."""
    import logging

    log = logging.getLogger("qtviz")
    try:
        from .pyqtgraph import backend as _pg  # noqa: PLC0415

        register(_pg)
    except Exception as e:  # pragma: no cover - pyqtgraph is a hard dep
        log.warning("pyqtgraph backend failed to load: %s", e)

    try:
        from .matplotlib import backend as _mpl  # noqa: PLC0415

        register(_mpl)
    except ImportError:
        log.info("matplotlib backend unavailable; install with: uv sync --extra matplotlib")

    try:
        from .webengine.render import backend as _web  # noqa: PLC0415

        register(_web)
    except ImportError:
        log.info("webengine backend unavailable; install with: uv sync --extra webengine")


_autoregister()

