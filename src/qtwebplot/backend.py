"""PlotBackend — the minimal contract for something hostable in a PlotView."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from PySide6.QtCore import QUrl

if TYPE_CHECKING:
    from qtwebplot.core import WebBridgeView


@runtime_checkable
class PlotBackend(Protocol):
    """Anything that can produce an HTML document and optionally bind to a view.

    Required: `to_html()`. Everything else has a sensible default; backends
    override what they need.
    """

    def to_html(self) -> str: ...

    def js_runtime(self) -> str | None:
        """Optional JS source injected after the core bootstrap. Use to wire
        library-specific events through `qtwebplot.send` and register handlers
        via `qtwebplot.on(name, fn)`.
        """
        return None

    def base_url(self) -> QUrl:
        return QUrl()

    def on_attach(self, view: WebBridgeView) -> None:
        """Called when the backend is bound to a view. Backends typically
        stash the view here so methods like `react(...)` can call `view.send`.
        """
        return None

    def on_detach(self) -> None:
        return None

    def set_figure(self, figure: Any) -> None:
        """Optional: replace the underlying figure object. PlotView delegates
        `set_figure` calls here.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement set_figure()"
        )
