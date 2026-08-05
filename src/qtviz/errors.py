"""qtviz error taxonomy (development-plan §3.5).

One base, caught broadly; specific subclasses, raised precisely. Every raise
should carry an actionable message (supported-backends list, install hint, …).
"""

from __future__ import annotations


class QtvizError(Exception):
    """Base for every error qtviz raises on purpose."""


class ValidationError(QtvizError, ValueError):
    """Invalid arguments to an Element / Options / data constructor: an
    out-of-range value, a mutually-exclusive pair, an unknown column name, or
    accessors that resolve to mismatched lengths.

    Subclasses both `QtvizError` — so ``except QtvizError`` catches every
    deliberate qtviz rejection, *including* bad construction input — and the
    stdlib `ValueError`, so existing ``except ValueError`` handlers keep
    working unchanged. Genuine *type* mismatches (e.g. tabular data where a
    gridded array is required) still raise `TypeError`, not this.
    """


class NegotiationError(QtvizError):
    """A backend could not be resolved for a node tree."""


class IncompatibleOverlayError(NegotiationError):
    """An Overlay's children resolve to (or require) different backends.

    Overlay is single-surface, so all children must share one backend (§2.3).
    """


class UnsupportedElementError(NegotiationError):
    """The chosen backend has no renderer for this Element type."""


class NoBackendForError(NegotiationError):
    """No registered backend supports this Element type at all."""


class BackendNotAvailableError(QtvizError):
    """A requested backend is not installed/registered (carries an install hint)."""


class RendererMissingError(QtvizError):
    """A backend was asked to render an Element it never registered."""


class AdapterError(QtvizError):
    """No registered data adapter handles the given input (§6.3)."""


class DisposedError(QtvizError, RuntimeError):
    """A live facade (a `PaneHandle`, [D147]) was used after the render it
    wraps was replaced or torn down. Fetch a fresh one from the current render
    (`view.pane(...)`) instead of caching across rebuilds."""


class MissingDependencyError(QtvizError, ImportError):
    """An optional dependency is required for the requested feature but is not
    installed. Carries the packaged install hint (``pip install "qtviz[X]"``).

    Subclasses both `QtvizError` (so ``except QtvizError`` stays the one broad
    handler) and the stdlib `ImportError` (the failure genuinely is a missing
    import, and existing ``except ImportError`` guards keep working)."""


class UnsupportedHoloViewsElement(QtvizError):
    """`from_holoviews` met an element it can neither translate natively nor host
    as a `RawFigure` (Phase 3, [D28]). Carries the offending type name + a hint."""


class QtvizWarning(UserWarning):
    """A deliberate, non-fatal qtviz degradation notice — e.g. a backend ignoring
    a *recommended* option it does not honor (spec §3.4 honor-or-warn, [D51]).

    A `UserWarning` subclass so it shows by default and can be filtered as a group
    (``warnings.filterwarnings("ignore", category=qtviz.errors.QtvizWarning)``).
    Degradations warn-and-proceed; they never raise."""
