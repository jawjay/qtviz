"""Layout helpers for composing many `PlotView` widgets at once.

Each helper wraps a Qt container (`QGridLayout`, `QTabWidget`, `QSplitter`)
and builds one `PlotView` per backend. Backends may be mixed (Plotly +
Bokeh + custom) — every cell is just an independent `PlotView`.

The helpers add no visualization logic — they only manage Qt parentage,
lazy construction (tabs), and add/remove ergonomics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from qtviz.backends.webengine._linking import _Link, resolve_view
from qtviz.backends.webengine.backend import PlotBackend
from qtviz.backends.webengine.view import PlotView


__all__ = ["PlotGrid", "PlotSplitter", "PlotTabs"]


# `Unlink` is the callable returned from every `.link(...)` method. Invoke
# it to tear down a single link explicitly.
Unlink = Callable[[], None]
LinkHandler = Callable[[PlotBackend, Any], None]


# ── PlotGrid ──────────────────────────────────────────────────────────────────


class PlotGrid(QWidget):
    """A QGridLayout of `PlotView` cells. Eager: every backend builds its
    view immediately.

    Memory cost is N * (one QWebEngineView). For dashboards with 20+ small
    plots, consider whether `PlotTabs(lazy=True)` is a better fit.
    """

    def __init__(
        self,
        backends: Sequence[PlotBackend] = (),
        *,
        cols: int = 2,
        spacing: int = 4,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if cols < 1:
            raise ValueError("cols must be >= 1")
        self._cols = cols

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(spacing)

        self._views: list[PlotView] = []
        self._backends: list[PlotBackend] = []
        self._links: list[_Link] = []

        for backend in backends:
            self.add(backend)

    # ── properties ───────────────────────────────────────────────────────
    @property
    def views(self) -> list[PlotView]:
        return list(self._views)

    @property
    def backends(self) -> list[PlotBackend]:
        return list(self._backends)

    @property
    def cols(self) -> int:
        return self._cols

    def __len__(self) -> int:
        return len(self._views)

    def __iter__(self) -> Iterable[PlotView]:
        return iter(self._views)

    # ── mutation ─────────────────────────────────────────────────────────
    def add(self, backend: PlotBackend) -> PlotView:
        view = PlotView(backend, parent=self)
        index = len(self._views)
        row, col = divmod(index, self._cols)
        self._grid.addWidget(view, row, col)
        self._views.append(view)
        self._backends.append(backend)
        return view

    def remove(self, index: int) -> None:
        if index < 0 or index >= len(self._views):
            raise IndexError(f"index {index} out of range for grid of {len(self._views)}")
        view = self._views.pop(index)
        self._backends.pop(index)
        self._drop_links_for(view)
        self._grid.removeWidget(view)
        view.setParent(None)
        view.deleteLater()
        self._relayout()

    def clear(self) -> None:
        for link in self._links:
            link.disconnect()
        self._links.clear()
        while self._views:
            view = self._views.pop()
            self._backends.pop()
            self._grid.removeWidget(view)
            view.setParent(None)
            view.deleteLater()

    def view_at(self, row: int, col: int) -> PlotView | None:
        index = row * self._cols + col
        if 0 <= index < len(self._views):
            return self._views[index]
        return None

    # ── linking ──────────────────────────────────────────────────────────
    def link(
        self,
        *,
        source: int | PlotView,
        event: str,
        to: int | PlotView | Sequence[int | PlotView],
        handler: LinkHandler,
    ) -> Unlink:
        """Forward `event` messages from `source` to `handler(target_backend, payload)`
        for each target. Returns an unlink callable.

        `source` and `to` are PlotView indices or PlotView instances. `event`
        is the message name as seen on `view.received` (e.g. `"plotly.hover"`).
        The link is auto-torn-down if either endpoint is removed from the grid.
        """
        source_view = resolve_view(self._views, source)
        targets = to if isinstance(to, (list, tuple)) else [to]
        target_views = [resolve_view(self._views, t) for t in targets]
        link = _Link(source_view, event, target_views, handler)
        self._links.append(link)

        def unlink() -> None:
            link.disconnect()
            if link in self._links:
                self._links.remove(link)

        return unlink

    # ── internals ────────────────────────────────────────────────────────
    def _drop_links_for(self, view: PlotView) -> None:
        surviving = []
        for link in self._links:
            if link.references(view):
                link.disconnect()
            else:
                surviving.append(link)
        self._links = surviving

    def _relayout(self) -> None:
        """Re-place existing views after a removal."""
        for i, view in enumerate(self._views):
            row, col = divmod(i, self._cols)
            self._grid.addWidget(view, row, col)

    # ── lifecycle ────────────────────────────────────────────────────────
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 — Qt naming
        self.clear()
        super().closeEvent(event)


# ── PlotTabs ──────────────────────────────────────────────────────────────────


@dataclass
class _TabEntry:
    label: str
    backend: PlotBackend
    container: QWidget
    view: PlotView | None = None


class PlotTabs(QWidget):
    """A QTabWidget of `PlotView`s, lazy by default.

    With `lazy=True` (default), each tab's `PlotView` is constructed only the
    first time that tab becomes current. With `lazy=False`, every tab builds
    its view immediately at construction / `add(...)` time.

    `views` returns only the views that have actually been built. Use
    `build_all()` to force-build every tab's view if you need to iterate them.
    """

    def __init__(
        self,
        backends: (
            Mapping[str, PlotBackend]
            | Sequence[tuple[str, PlotBackend]]
            | None
        ) = None,
        *,
        lazy: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._lazy = lazy
        self._entries: list[_TabEntry] = []
        self._links: list[_Link] = []

        self._tabs = QTabWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs)

        self._tabs.currentChanged.connect(self._on_current_changed)

        if backends is not None:
            items = backends.items() if isinstance(backends, Mapping) else backends
            for label, backend in items:
                self.add(label, backend)

    # ── properties ───────────────────────────────────────────────────────
    @property
    def views(self) -> list[PlotView]:
        return [e.view for e in self._entries if e.view is not None]

    @property
    def backends(self) -> list[PlotBackend]:
        return [e.backend for e in self._entries]

    @property
    def labels(self) -> list[str]:
        return [e.label for e in self._entries]

    @property
    def lazy(self) -> bool:
        return self._lazy

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterable[tuple[str, PlotBackend]]:
        return iter((e.label, e.backend) for e in self._entries)

    # ── mutation ─────────────────────────────────────────────────────────
    def add(self, label: str, backend: PlotBackend) -> int:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        entry = _TabEntry(label=label, backend=backend, container=container, view=None)
        self._entries.append(entry)
        index = self._tabs.addTab(container, label)

        if not self._lazy:
            self._build(entry)
        elif self._tabs.currentIndex() == index:
            # First tab becomes current immediately — build it.
            self._build(entry)
        return index

    def remove(self, index: int) -> None:
        if index < 0 or index >= len(self._entries):
            raise IndexError(
                f"index {index} out of range for tabs of {len(self._entries)}"
            )
        self._tabs.removeTab(index)
        entry = self._entries.pop(index)
        if entry.view is not None:
            self._drop_links_for(entry.view)
            entry.view.setParent(None)
            entry.view.deleteLater()
        entry.container.deleteLater()

    def clear(self) -> None:
        for link in self._links:
            link.disconnect()
        self._links.clear()
        while self._entries:
            self.remove(0)

    # ── linking ──────────────────────────────────────────────────────────
    def link(
        self,
        *,
        source: int | PlotView | str,
        event: str,
        to: int | PlotView | str | Sequence[int | PlotView | str],
        handler: LinkHandler,
    ) -> Unlink:
        """Forward `event` messages from `source` to `handler(target_backend, payload)`.

        `source` and `to` accept tab indices, tab labels, or PlotView
        instances. Tabs that haven't been built yet are built first (so
        their views exist to be wired) — this means linking a lazy tab
        eagerly materializes it.
        """

        def to_view(ref: int | PlotView | str) -> PlotView:
            if isinstance(ref, str):
                view = self.view_for(ref)
                if view is None:
                    raise KeyError(f"no tab labelled {ref!r}")
                return view
            if isinstance(ref, int):
                # Build the tab so its view exists.
                entry = self._entries[ref]
                if entry.view is None:
                    self._build(entry)
                return entry.view  # type: ignore[return-value]
            return ref

        source_view = to_view(source)
        targets = to if isinstance(to, (list, tuple)) else [to]
        target_views = [to_view(t) for t in targets]
        link = _Link(source_view, event, target_views, handler)
        self._links.append(link)

        def unlink() -> None:
            link.disconnect()
            if link in self._links:
                self._links.remove(link)

        return unlink

    def _drop_links_for(self, view: PlotView) -> None:
        surviving = []
        for link in self._links:
            if link.references(view):
                link.disconnect()
            else:
                surviving.append(link)
        self._links = surviving

    def view_for(self, label: str) -> PlotView | None:
        """Return (and build, if lazy) the view for `label`. None if no such tab."""
        for entry in self._entries:
            if entry.label == label:
                if entry.view is None:
                    self._build(entry)
                return entry.view
        return None

    def build_all(self) -> None:
        """Force-build every tab's view. Useful for bulk configuration via
        `views` after construction."""
        for entry in self._entries:
            if entry.view is None:
                self._build(entry)

    @property
    def tab_widget(self) -> QTabWidget:
        """Escape hatch — direct access to the underlying QTabWidget for
        styling, `setTabsClosable`, etc."""
        return self._tabs

    # ── internals ────────────────────────────────────────────────────────
    def _build(self, entry: _TabEntry) -> None:
        if entry.view is not None:
            return
        entry.view = PlotView(entry.backend, parent=entry.container)
        entry.container.layout().addWidget(entry.view)

    def _on_current_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._entries):
            return
        entry = self._entries[index]
        if entry.view is None:
            self._build(entry)

    # ── lifecycle ────────────────────────────────────────────────────────
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.clear()
        super().closeEvent(event)


# ── PlotSplitter ──────────────────────────────────────────────────────────────


class PlotSplitter(QSplitter):
    """A QSplitter of `PlotView`s. Each pane is independently sized via the
    splitter handle.

    `PlotSplitter` is a direct `QSplitter` subclass, so all of `QSplitter`'s
    API is available (`setSizes`, `setHandleWidth`, `saveState`, etc.).
    """

    def __init__(
        self,
        backends: Sequence[PlotBackend] = (),
        *,
        orientation: Qt.Orientation = Qt.Horizontal,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(orientation, parent)
        self._views: list[PlotView] = []
        self._backends: list[PlotBackend] = []
        self._links: list[_Link] = []
        for backend in backends:
            self.add(backend)

    @property
    def views(self) -> list[PlotView]:
        return list(self._views)

    @property
    def backends(self) -> list[PlotBackend]:
        return list(self._backends)

    def __len__(self) -> int:
        return len(self._views)

    def add(self, backend: PlotBackend) -> PlotView:
        view = PlotView(backend)
        self.addWidget(view)
        self._views.append(view)
        self._backends.append(backend)
        return view

    def remove(self, index: int) -> None:
        if index < 0 or index >= len(self._views):
            raise IndexError(
                f"index {index} out of range for splitter of {len(self._views)}"
            )
        view = self._views.pop(index)
        self._backends.pop(index)
        self._drop_links_for(view)
        view.setParent(None)
        view.deleteLater()

    def clear(self) -> None:
        for link in self._links:
            link.disconnect()
        self._links.clear()
        while self._views:
            view = self._views.pop()
            self._backends.pop()
            view.setParent(None)
            view.deleteLater()

    def link(
        self,
        *,
        source: int | PlotView,
        event: str,
        to: int | PlotView | Sequence[int | PlotView],
        handler: LinkHandler,
    ) -> Unlink:
        source_view = resolve_view(self._views, source)
        targets = to if isinstance(to, (list, tuple)) else [to]
        target_views = [resolve_view(self._views, t) for t in targets]
        link = _Link(source_view, event, target_views, handler)
        self._links.append(link)

        def unlink() -> None:
            link.disconnect()
            if link in self._links:
                self._links.remove(link)

        return unlink

    def _drop_links_for(self, view: PlotView) -> None:
        surviving = []
        for link in self._links:
            if link.references(view):
                link.disconnect()
            else:
                surviving.append(link)
        self._links = surviving

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.clear()
        super().closeEvent(event)
