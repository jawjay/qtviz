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
    if any(isinstance(child, Layout) for child in layout.children):
        # nested grids host per-pane: a backend's `can_host("grid")` means a
        # *flat* grid — its cell renderer takes an Element/Overlay, never a
        # Layout (rendering one crashed before this routing).
        return True, None
    child_backends = {negotiate(child, view_backend) for child in layout.children}
    if len(child_backends) > 1:
        return True, None
    chosen = next(iter(child_backends))
    if chosen == "auto" or not backends.get(chosen).can_host("grid"):  # nested layout / un-hostable
        return True, None
    return False, chosen


# LayoutOptions the Qt host honors ([D109]/[D108]): grid shape (rows/cols
# incl. mosaic spans), ratios, spacing, tab/dock chrome, the container title
# (a header label on any kind), and — via the [D151] `_LinkController` —
# link_x/link_y across mixed-backend panes.
_HOST_LAYOUT_HONORED = frozenset({"rows", "cols", "spacing", "tab_labels",
                                  "dock_areas", "title", "link_x", "link_y",
                                  "width_ratios", "height_ratios"})


class _LinkController:
    """Cross-backend axis linking for host-composed layouts ([D151]).

    Single-backend grids link natively (pg `setXLink`, mpl `sharex`); a
    composite has no shared scene, so linking rides the event loop: a
    `RangeEvent` from a pane in a link group propagates its range to the
    group's other panes via `pane.set_range`. Two guards keep the loop from
    feeding back: a reentrancy flag (synchronous echoes — pg/mpl emit range
    callbacks *inside* the set) and a value guard (asynchronous echoes — a
    webengine pane reports its relayout later; a member already at the target
    range is skipped, so propagation converges instead of ping-ponging)."""

    def __init__(self, handle, x_groups, y_groups) -> None:
        from .event import RangeEvent  # noqa: PLC0415

        self._handle = handle
        self._x_groups = [frozenset(g) for g in x_groups]
        self._y_groups = [frozenset(g) for g in y_groups]
        self._syncing = False
        self._sub = handle.event_bus.subscribe(RangeEvent, self._on_range)

    def _on_range(self, ev) -> None:
        # A throttled *trailing* delivery rides a QTimer that outlives the
        # subscription — it can land after the render is disposed. Dead
        # renders don't link.
        if self._syncing or ev.pane is None or self._handle.widget is None:
            return
        self._syncing = True
        try:
            self._propagate(ev.pane, "x", ev.x, self._x_groups)
            self._propagate(ev.pane, "y", ev.y, self._y_groups)
        finally:
            self._syncing = False

    def _propagate(self, origin: str, axis: str, rng, groups) -> None:
        import math  # noqa: PLC0415

        if rng is None:
            return
        for group in groups:
            if origin not in group:
                continue
            for label in group:
                if label == origin:
                    continue
                from ..errors import DisposedError  # noqa: PLC0415

                try:
                    pane = self._handle.pane(label)
                    cur = getattr(pane.capture(), f"{axis}_range")
                    if cur is not None and all(
                            math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
                            for a, b in zip(cur, rng, strict=True)):
                        continue  # value guard: already there (async echo)
                    pane.set_range(**{axis: tuple(rng)})
                except (KeyError, DisposedError):
                    continue  # the render changed/died underneath — drop
            return  # a pane belongs to exactly one group per axis

    def dispose(self) -> None:
        self._sub.dispose()


def _link_pane_groups(layout: Layout, mode) -> list[list[str]]:
    """[D151]: link groups as flat pane labels for a host-composed layout.
    Groups come from `link_groups` over the layout's direct children (grid
    cells for grids; `True` on splitter/tabs/dock links all — `"col"/"row"`
    are grid-only, rejected at construction). A nested-`Layout` child holds
    many surfaces, so which one to link is ambiguous — it is excluded with a
    one-time warning; its *internal* linking is its own options' business."""
    from .compose import flat_pane_labels, grid_geometry, link_groups  # noqa: PLC0415

    n = len(layout.children)
    cells = (grid_geometry(layout)[0] if layout.kind == "grid"
             else [(0, i, 1, 1) for i in range(n)])
    index_groups = link_groups(cells, n, mode)
    if not index_groups:
        return []
    labels = flat_pane_labels(layout)
    counts = [len(flat_pane_labels(child)) for child in layout.children]
    offsets = [0]
    for c in counts:
        offsets.append(offsets[-1] + c)
    out: list[list[str]] = []
    dropped = False
    for group in index_groups:
        members = [labels[offsets[i]] for i in group if counts[i] == 1]
        dropped = dropped or len(members) != len(group)
        if len(members) > 1:
            out.append(members)
    if dropped:
        import warnings  # noqa: PLC0415

        from ..errors import QtvizWarning  # noqa: PLC0415

        warnings.warn(
            "layout-host: a nested Layout pane is excluded from axis linking "
            "(many surfaces — ambiguous); link inside it with its own "
            "link_x/link_y.", QtvizWarning, stacklevel=4)
    return out


class LayoutHost:
    @staticmethod
    @require_gui_thread
    def render(layout: Layout, *, view_backend, theme, parent=None) -> CompositeRenderHandle:
        from ._degrade import check_layout  # noqa: PLC0415

        check_layout(layout.options, consumer="layout-host",
                     honored=_HOST_LAYOUT_HONORED)
        from .compose import flat_pane_labels  # noqa: PLC0415

        child_handles = [
            render_root(child, view_backend=view_backend, theme=theme)
            for child in layout.children
        ]
        widgets = [h.widget for h in child_handles]
        container = _build_container(layout, widgets)
        if layout.options.title:
            container = _titled(container, layout.options.title, theme)
        if parent is not None:
            container.setParent(parent)
        handle = CompositeRenderHandle(container, child_handles,
                                       pane_labels=flat_pane_labels(layout))
        opts = layout.options
        if opts.link_x or opts.link_y:  # [D151]: linking crosses host panes
            x_groups = _link_pane_groups(layout, opts.link_x)
            y_groups = _link_pane_groups(layout, opts.link_y)
            if x_groups or y_groups:
                handle._link = _LinkController(handle, x_groups, y_groups)
        return handle


def _titled(inner: QWidget, title: str, theme) -> QWidget:
    """Wrap any container with a header label — the host's suptitle ([D108])."""
    from PySide6.QtWidgets import QLabel, QVBoxLayout  # noqa: PLC0415

    outer = QWidget()
    box = QVBoxLayout(outer)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(0)
    label = QLabel(title)
    label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    label.setStyleSheet(
        f"color: {theme.foreground.css()}; background: {theme.background.css()}; "
        f"font-size: {theme.title_size}pt; padding: 4px;")
    box.addWidget(label)
    box.addWidget(inner, stretch=1)
    return outer


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
        # captions: explicit tab_labels win, then pane labels ([D145] — one
        # spec names panes AND tabs: Layout.tabs({"Raw": a, "Fitted": b}))
        labels = (opts.tab_labels or layout.labels
                  or [f"Panel {i + 1}" for i in range(len(widgets))])
        for w, label in zip(widgets, labels, strict=False):
            tabs.addTab(w, label)
        return tabs
    if kind == "dock":
        return _build_docks(widgets, opts)
    # grid (mixed-backend), with mosaic spans and stretch ratios ([D108])
    from .compose import grid_geometry  # noqa: PLC0415

    host = QWidget()
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(opts.spacing)
    cells, nrows, ncols = grid_geometry(layout)
    for w, (r, c, rs, cs) in zip(widgets, cells, strict=True):
        grid.addWidget(w, r, c, rs, cs)
    for c, ratio in enumerate(opts.width_ratios or ()):
        grid.setColumnStretch(c, max(1, round(ratio * 100)))
    for r, ratio in enumerate(opts.height_ratios or ()):
        grid.setRowStretch(r, max(1, round(ratio * 100)))
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
