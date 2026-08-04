"""RawFigure — pass an existing web figure straight to the webengine backend (D26/D31).

A whole-figure passthrough: it wraps an existing Plotly / Bokeh / HoloViews
object and negotiates *only* to the webengine backend (no native backend has a
renderer for it). Because it *is* a complete figure, it is standalone — it can't
overlay with native traces (the webengine path builds one Plotly figure from
traces; a raw figure can't merge in). In a `Layout` it's a pane (W4).

The library is auto-detected from the figure's type; pass `kind=` to override.
"""

from __future__ import annotations

from ..core.element import Element
from ..errors import ValidationError

_KINDS = ("plotly", "bokeh", "holoviews")


def _detect_kind(figure) -> str:
    for klass in type(figure).__mro__:
        top = (klass.__module__ or "").split(".", 1)[0]
        if top in _KINDS:
            return top
    raise TypeError(
        f"could not detect the figure library for {type(figure).__name__}; "
        "pass kind='plotly' | 'bokeh' | 'holoviews'"
    )


class RawFigure(Element):
    """Host an existing Plotly / Bokeh / HoloViews figure unchanged (webengine only)."""

    DATA_KIND = "none"  # [D124]: the foreign figure is opaque, not a DataRef

    def __init__(self, figure, *, kind: str | None = None, backend_hint=None, id=None) -> None:
        super().__init__(backend_hint=backend_hint, id=id)
        self.figure = figure
        self.kind = kind or _detect_kind(figure)
        if self.kind not in _KINDS:
            raise ValidationError(f"RawFigure kind must be one of {_KINDS}, got {self.kind!r}")
        self._freeze()
