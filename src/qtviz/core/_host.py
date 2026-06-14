"""Generic Qt-level layout host (spec §3.7).

`render_root` is the single entry the View calls. It decides whether a node
renders through one backend (Element, Overlay, or a homogeneous grid the
backend hosts itself — which keeps shared/linked primitives) or through the
backend-neutral `LayoutHost` (splitter/tabs/dock, or a grid whose panes span
backends). The host arranges per-pane widgets and returns a
`CompositeRenderHandle` with a merged event bus.

Lives outside `compose.py` so negotiation stays Qt-free (dev-plan §2).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QGridLayout,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QWidget,
)

from .. import backends
from .backend import CompositeRenderHandle
from .compose import Layout, negotiate
from .threading import require_gui_thread

_DOCK_AREAS = {
    "left": Qt.DockWidgetArea.LeftDockWidgetArea,
    "right": Qt.DockWidgetArea.RightDockWidgetArea,
    "top": Qt.DockWidgetArea.TopDockWidgetArea,
    "bottom": Qt.DockWidgetArea.BottomDockWidgetArea,
}


@require_gui_thread
def render_root(node, *, view_backend, theme, parent=None):
    """Render any Node to a single root handle (backend or composite)."""
    if isinstance(node, Layout):
        needs_host, chosen = _resolve_layout(node, view_backend)
        if needs_host:
            return LayoutHost.render(node, view_backend=view_backend, theme=theme, parent=parent)
        return backends.get(chosen).render(node, theme=theme, parent=parent)
    chosen = negotiate(node, view_backend)
    return backends.get(chosen).render(node, theme=theme, parent=parent)


def _resolve_layout(layout: Layout, view_backend) -> tuple[bool, str | None]:
    """`(needs_host, backend_name)`. Host splitter/tabs/dock (pure Qt containers)
    and grids whose panes span backends (or can't be hosted by one backend);
    otherwise a homogeneous grid renders through its single concrete backend."""
    if layout.kind in ("splitter", "tabs", "dock"):
        return True, None
    child_backends = {negotiate(child, view_backend) for child in layout.children}
    if len(child_backends) > 1:
        return True, None
    chosen = next(iter(child_backends))
    if chosen == "auto" or not backends.get(chosen).can_host("grid"):  # nested layout / un-hostable
        return True, None
    return False, chosen


class LayoutHost:
    @staticmethod
    @require_gui_thread
    def render(layout: Layout, *, view_backend, theme, parent=None) -> CompositeRenderHandle:
        child_handles = [
            render_root(child, view_backend=view_backend, theme=theme)
            for child in layout.children
        ]
        widgets = [h.widget for h in child_handles]
        container = _build_container(layout, widgets)
        if parent is not None:
            container.setParent(parent)
        return CompositeRenderHandle(container, child_handles)


def _build_container(layout: Layout, widgets: list) -> QWidget:
    kind = layout.kind
    opts = layout.options
    if kind == "splitter":
        splitter = QSplitter()
        for w in widgets:
            splitter.addWidget(w)
        return splitter
    if kind == "tabs":
        tabs = QTabWidget()
        labels = opts.tab_labels or [f"Panel {i + 1}" for i in range(len(widgets))]
        for w, label in zip(widgets, labels, strict=False):
            tabs.addTab(w, label)
        return tabs
    if kind == "dock":
        return _build_docks(widgets, opts)
    # grid (mixed-backend)
    host = QWidget()
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(opts.spacing)
    ncols = opts.cols or len(widgets)
    for i, w in enumerate(widgets):
        r, c = divmod(i, ncols)
        grid.addWidget(w, r, c)
    return host


def _build_docks(widgets: list, opts) -> QMainWindow:
    window = QMainWindow()
    window.setCentralWidget(widgets[0])
    areas = dict(opts.dock_areas or ())
    for i, w in enumerate(widgets[1:], start=1):
        dock = QDockWidget(f"Panel {i + 1}")
        dock.setWidget(w)
        area = _DOCK_AREAS.get(areas.get(i, "right"), Qt.DockWidgetArea.RightDockWidgetArea)
        window.addDockWidget(area, dock)
    return window
