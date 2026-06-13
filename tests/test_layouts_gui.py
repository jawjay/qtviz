"""GUI tests for `PlotGrid`, `PlotTabs`, `PlotSplitter`.

These use a backend-free `_StubBackend` so the tests don't depend on Plotly
or Bokeh being installed. The stub renders a trivial page that pings the
bridge so we can confirm a `PlotView` was actually constructed and wired up.

Run:
    QT_QPA_PLATFORM=offscreen pytest tests/test_layouts_gui.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("PySide6.QtWebEngineWidgets")

from PySide6.QtCore import Qt  # noqa: E402

from qtwebplot import PlotGrid, PlotTabs  # noqa: E402
from qtwebplot.backend import PlotBackend  # noqa: E402, F401 — typing import
from qtwebplot.layouts import PlotSplitter  # noqa: E402


class _StubBackend(PlotBackend):
    """Minimal backend that just announces itself once the bridge is ready."""

    def __init__(self, label: str) -> None:
        self._label = label
        self._view = None

    def to_html(self) -> str:
        # Body contains a marker the test can read back via runJavaScript.
        return f"""
        <!doctype html>
        <html><head><title>{self._label}</title></head>
        <body>
          <div id="marker" data-label="{self._label}">{self._label}</div>
          <script>
            qtwebplot.onReady(function () {{
              qtwebplot.send("stub.ready", {{label: "{self._label}"}});
            }});
          </script>
        </body></html>
        """

    def js_runtime(self) -> str | None:
        return None

    def on_attach(self, view) -> None:
        self._view = view

    def on_detach(self) -> None:
        self._view = None


def _wait_ready(qtbot, view, timeout: int = 10_000) -> None:
    with qtbot.waitSignal(view.ready, timeout=timeout):
        pass


# ── PlotGrid ─────────────────────────────────────────────────────────────────


@pytest.mark.gui
def test_grid_constructs_one_view_per_backend(qtbot):
    backends = [_StubBackend(f"g{i}") for i in range(4)]
    grid = PlotGrid(backends, cols=2)
    qtbot.addWidget(grid)
    grid.resize(800, 600)
    grid.show()

    assert len(grid) == 4
    assert len(grid.views) == 4
    assert len(grid.backends) == 4
    for v in grid.views:
        _wait_ready(qtbot, v)


@pytest.mark.gui
def test_grid_add_and_remove_live(qtbot):
    grid = PlotGrid([_StubBackend("a"), _StubBackend("b")], cols=2)
    qtbot.addWidget(grid)
    grid.show()

    for v in grid.views:
        _wait_ready(qtbot, v)

    grid.add(_StubBackend("c"))
    assert len(grid) == 3
    _wait_ready(qtbot, grid.views[-1])

    grid.remove(0)
    assert len(grid) == 2
    assert grid.backends[0].to_html().__contains__("b")


@pytest.mark.gui
def test_grid_view_at(qtbot):
    grid = PlotGrid([_StubBackend(f"g{i}") for i in range(5)], cols=2)
    qtbot.addWidget(grid)
    grid.show()

    assert grid.view_at(0, 0) is grid.views[0]
    assert grid.view_at(1, 0) is grid.views[2]
    assert grid.view_at(99, 0) is None


# ── PlotTabs ─────────────────────────────────────────────────────────────────


@pytest.mark.gui
def test_tabs_eager_builds_all(qtbot):
    tabs = PlotTabs(
        {"first": _StubBackend("t1"), "second": _StubBackend("t2"), "third": _StubBackend("t3")},
        lazy=False,
    )
    qtbot.addWidget(tabs)
    tabs.show()

    assert len(tabs) == 3
    assert len(tabs.views) == 3
    for v in tabs.views:
        _wait_ready(qtbot, v)


@pytest.mark.gui
def test_tabs_lazy_builds_only_active_until_visited(qtbot):
    tabs = PlotTabs(
        [("first", _StubBackend("t1")), ("second", _StubBackend("t2")), ("third", _StubBackend("t3"))],
        lazy=True,
    )
    qtbot.addWidget(tabs)
    tabs.show()

    # First tab is the active one — it should be built immediately.
    assert len(tabs) == 3
    assert len(tabs.views) == 1
    _wait_ready(qtbot, tabs.views[0])

    # Switching to the third tab should build *that* tab (and skip the second).
    tabs.tab_widget.setCurrentIndex(2)
    qtbot.waitUntil(lambda: len(tabs.views) == 2, timeout=2000)
    _wait_ready(qtbot, tabs.views[-1])

    # `view_for` triggers build for the still-unbuilt tab.
    v = tabs.view_for("second")
    assert v is not None
    assert len(tabs.views) == 3
    _wait_ready(qtbot, v)


@pytest.mark.gui
def test_tabs_build_all(qtbot):
    tabs = PlotTabs(
        [("first", _StubBackend("t1")), ("second", _StubBackend("t2"))],
        lazy=True,
    )
    qtbot.addWidget(tabs)
    tabs.show()

    assert len(tabs.views) == 1
    tabs.build_all()
    assert len(tabs.views) == 2
    for v in tabs.views:
        _wait_ready(qtbot, v)


# ── PlotSplitter ─────────────────────────────────────────────────────────────


@pytest.mark.gui
def test_splitter_constructs_views(qtbot):
    splitter = PlotSplitter(
        [_StubBackend("L"), _StubBackend("R")],
        orientation=Qt.Horizontal,
    )
    qtbot.addWidget(splitter)
    splitter.show()

    assert len(splitter) == 2
    for v in splitter.views:
        _wait_ready(qtbot, v)


@pytest.mark.gui
def test_grid_link_forwards_event_to_target(qtbot):
    backends = [_StubBackend("a"), _StubBackend("b")]
    grid = PlotGrid(backends, cols=2)
    qtbot.addWidget(grid)
    grid.show()

    for v in grid.views:
        _wait_ready(qtbot, v)

    received: list[tuple[PlotBackend, object]] = []

    def handler(target_backend, payload):
        received.append((target_backend, payload))

    grid.link(source=0, event="stub.tick", to=1, handler=handler)

    # Drive a stub.tick from view[0]'s JS side.
    grid.views[0].run_js("qtwebplot.send('stub.tick', {n: 42});")
    qtbot.waitUntil(lambda: len(received) == 1, timeout=2000)
    target_backend, payload = received[0]
    assert target_backend is grid.backends[1]
    assert payload == {"n": 42}


@pytest.mark.gui
def test_grid_link_unlinks_on_remove(qtbot):
    backends = [_StubBackend("a"), _StubBackend("b")]
    grid = PlotGrid(backends, cols=2)
    qtbot.addWidget(grid)
    grid.show()
    for v in grid.views:
        _wait_ready(qtbot, v)

    received: list = []
    grid.link(
        source=0,
        event="stub.tick",
        to=1,
        handler=lambda b, p: received.append(p),
    )

    # Remove the target — link should be auto-torn-down.
    grid.remove(1)
    grid.views[0].run_js("qtwebplot.send('stub.tick', {n: 1});")
    # Give the JS round-trip a window; assert no delivery.
    qtbot.wait(300)
    assert received == []


@pytest.mark.gui
def test_splitter_add_remove(qtbot):
    splitter = PlotSplitter([_StubBackend("a")])
    qtbot.addWidget(splitter)
    splitter.show()
    _wait_ready(qtbot, splitter.views[0])

    splitter.add(_StubBackend("b"))
    assert len(splitter) == 2
    _wait_ready(qtbot, splitter.views[-1])

    splitter.remove(0)
    assert len(splitter) == 1
