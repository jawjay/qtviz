"""qtviz error taxonomy (development-plan §3.5).

One base, caught broadly; specific subclasses, raised precisely. Every raise
should carry an actionable message (supported-backends list, install hint, …).
"""

from __future__ import annotations


class QtvizError(Exception):
    """Base for every error qtviz raises on purpose."""


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
