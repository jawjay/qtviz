"""matplotlib backend — FigureCanvasQTAgg wrapper + RenderHandle (spec §4.2)."""

from __future__ import annotations

import os
import uuid
from math import ceil
from pathlib import Path

os.environ.setdefault("QT_API", "pyside6")  # bind matplotlib's Qt to PySide6

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ...core.backend import RenderContext, RendererRegistry, RenderHandle, ViewState
from ...core.capabilities import Capabilities
from ...core.compose import Layout, Overlay
from ...core.element import Element
from ...core.event import EventBus, SelectEvent
from ...core.threading import require_gui_thread
from ...data import resolve_node
from ...errors import RendererMissingError
from . import _events
from ._renderers import RENDERERS
from ._theme import apply_theme_ax, apply_theme_fig

_CAPS = Capabilities(
    dimensions=frozenset({2, 3}),
    opengl=False,
    picking="native",
    brush="approximate",
    range_events=True,
    streaming=False,
    max_recommended_points=100_000,
    animation=True,
    exports=frozenset({"png", "svg", "pdf"}),
    threading_model="gui_only",
)


class MplRenderHandle(RenderHandle):
    def __init__(self, canvas, fig, bus, surfaces, root, backend) -> None:
        super().__init__(canvas, bus, "matplotlib")
        self._fig = fig
        self._surfaces = surfaces  # [{"ax", "surface_id", "selectables"}]
        self._root = root
        self._backend = backend

    @property
    def axes(self):
        return [s["ax"] for s in self._surfaces]

    def capture_state(self) -> ViewState:
        if not self._surfaces:
            return ViewState()
        ax = self._surfaces[0]["ax"]
        return ViewState(x_range=tuple(ax.get_xlim()), y_range=tuple(ax.get_ylim()))

    def restore_state(self, state: ViewState) -> None:
        if not self._surfaces:
            return
        ax = self._surfaces[0]["ax"]
        if state.x_range:
            ax.set_xlim(*state.x_range)
        if state.y_range:
            ax.set_ylim(*state.y_range)
        self._fig.canvas.draw_idle()

    def select_bounds(self, ax_index: int, xmin, ymin, xmax, ymax) -> None:
        """Programmatic brush (approximate) — emits one SelectEvent per
        selectable element on the axes (element id + indices + bounds)."""
        bounds = (float(xmin), float(ymin), float(xmax), float(ymax))
        for source_id, x, y in self._surfaces[ax_index]["selectables"]:
            mask = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
            self.event_bus.emit(SelectEvent(source_id, np.nonzero(mask)[0].tolist(), bounds))

    def export(self, fmt: str, path) -> Path:
        path = Path(path)
        self._fig.savefig(str(path), format=fmt)
        return path

    def dispose(self) -> None:
        for s in self._surfaces:
            for controller in getattr(s["ax"], "_qtviz_rasters", ()):
                controller.dispose()
        self.event_bus.dispose()
        self._fig.clf()
        w = self.widget
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        self.widget = None


class MatplotlibBackend:
    name = "matplotlib"

    def __init__(self) -> None:
        self.capabilities = _CAPS
        self.renderers = RendererRegistry()
        for element_type, fn in RENDERERS.items():
            self.renderers.register(element_type, fn)

    def supports(self, element_type: type) -> bool:
        return self.renderers.get(element_type) is not None

    def can_host(self, kind: str) -> bool:
        return kind in ("overlay", "grid")

    @require_gui_thread
    def render(self, node, *, theme, parent=None) -> MplRenderHandle:
        node = resolve_node(node)  # accessors → role-keyed eager refs (D14)
        fig = Figure()
        canvas = FigureCanvasQTAgg(fig)
        if parent is not None:
            canvas.setParent(parent)
        apply_theme_fig(fig, theme)
        bus = EventBus()
        surfaces: list = []
        self._render_into(node, fig, theme, bus, surfaces)
        canvas.draw_idle()
        return MplRenderHandle(canvas, fig, bus, surfaces, node, self)

    # ── internal ──
    def _render_into(self, node, fig, theme, bus, surfaces) -> None:
        if isinstance(node, Layout):
            n = len(node.children)
            ncols = node.options.cols or n
            nrows = ceil(n / ncols)
            opts = node.options
            for i, child in enumerate(node.children):
                base = surfaces[0]["ax"] if surfaces else None
                ax = fig.add_subplot(
                    nrows, ncols, i + 1,
                    sharex=base if opts.link_x else None,
                    sharey=base if opts.link_y else None,
                )
                self._render_cell(child, ax, theme, bus, surfaces)
        else:
            self._render_cell(node, fig.add_subplot(1, 1, 1), theme, bus, surfaces)

    def _render_cell(self, node, ax, theme, bus, surfaces) -> None:
        apply_theme_ax(ax, theme)
        surface_id = uuid.uuid4().hex
        selectables: list = []
        surfaces.append({"ax": ax, "surface_id": surface_id, "selectables": selectables})
        _events.connect_range(ax, surface_id, bus)
        children = node.children if isinstance(node, Overlay) else (node,)
        for element in children:
            self._render_element(element, ax, theme, bus, selectables)

    def _render_element(self, element: Element, ax, theme, bus, selectables) -> None:
        fn = self.renderers.get(type(element))
        if fn is None:
            raise RendererMissingError(
                f"matplotlib has no renderer for {type(element).__name__}"
            )
        ctx = RenderContext(theme=theme, parent=ax, event_bus=bus, backend=self, parent_axes=ax)
        artist = fn(element, ctx)
        _events.attach(element, artist, ctx, selectables)
