"""0.3 increment 3 — the legend contract ([D55]/[D60], milestone-0.3-firstclass §2).

Legend stops being a color-mapping side-effect: every element can contribute a
`legend_entry()` (a `label` + swatch), an Overlay aggregates the contributions
into one legend, and the previously-dead `OverlayOptions.legend` (+ the new
`legend_position`) actually control it.
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

from qtviz.errors import ValidationError  # noqa: E402

_DATA = {"x": np.linspace(0.0, 10.0, 30), "y": np.linspace(0.0, 5.0, 30),
         "cat": np.array(["a", "b", "c"] * 10)}


def _has(name):
    return name in {getattr(b, "name", b) for b in qv.backends.list_available()}


def _overlay(*children, **opts):
    return qv.Overlay(children, options=qv.OverlayOptions(**opts))


# ── Tier-1: the contract itself (pure) ───────────────────────────────────────
@pytest.mark.tier1
def test_legend_entry_label_and_swatch():
    theme = qv.Theme.light()
    # default color → the element's palette slot (by overlay index)
    e = qv.Curve(_DATA, x="x", y="y", label="raw").legend_entry(theme, 1)
    assert e.label == "raw" and e.swatch == theme.palette[1]
    # explicit color wins
    e2 = qv.Curve(_DATA, x="x", y="y", label="raw", color="#ff0000").legend_entry(theme)
    assert e2.swatch.hex().lower() == "#ff0000"


@pytest.mark.tier1
def test_legend_entry_none_without_label_and_for_color_by():
    theme = qv.Theme.light()
    assert qv.Curve(_DATA, x="x", y="y").legend_entry(theme) is None
    # a color_by Scatter already emits its own categorical/continuous Legend
    assert qv.Scatter(_DATA, x="x", y="y", color_by="cat",
                      label="pts").legend_entry(theme) is None
    # …but a static Scatter contributes like any styled element
    assert qv.Scatter(_DATA, x="x", y="y", label="pts").legend_entry(theme).label == "pts"


@pytest.mark.tier1
def test_all_styling_elements_carry_label():
    theme = qv.Theme.light()
    els = [
        qv.Scatter(_DATA, x="x", y="y", label="s"),
        qv.Curve(_DATA, x="x", y="y", label="c"),
        qv.Bars(_DATA, x="x", y="y", label="b"),
        qv.Histogram(_DATA, value="y", label="h"),
        qv.ErrorBars({"x": [1.0], "y": [2.0], "e": [0.1]}, x="x", y="y", err="e", label="e"),
        qv.Spread({"x": [1.0], "lo": [0.0], "hi": [2.0]}, x="x", y_lo="lo", y_hi="hi",
                  label="sp"),
    ]
    assert [el.legend_entry(theme).label for el in els] == ["s", "c", "b", "h", "e", "sp"]
    assert all("label" in type(el).RECOMMENDED_OPTIONS for el in els)


@pytest.mark.tier1
def test_legend_position_vocabulary_validated():
    assert qv.OverlayOptions(legend_position="top").legend_position == "top"
    with pytest.raises(ValidationError):
        qv.OverlayOptions(legend_position="bottom-left")


# ── Tier-2: overlay aggregation on the native backends ───────────────────────
def _labeled_overlay(**opts):
    return _overlay(
        qv.Curve(_DATA, x="x", y="y", label="raw"),
        qv.Curve(_DATA, x="x", y=qv.col("y") * 2.0, label="smoothed"),
        **opts,
    )


@pytest.mark.tier2
def test_pyqtgraph_overlay_legend_has_both_entries(qtbot):
    view = qv.View(_labeled_overlay(), backend="pyqtgraph")
    qtbot.addWidget(view)
    lg = getattr(view.handle.plots[0], "_qtviz_legend", None)
    assert lg is not None
    labels = [label.text for _sample, label in lg.items]
    assert labels == ["raw", "smoothed"]


@pytest.mark.tier2
def test_matplotlib_overlay_legend_has_both_entries(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    view = qv.View(_labeled_overlay(), backend="matplotlib")
    qtbot.addWidget(view)
    legend = view.handle.axes[0].get_legend()
    assert legend is not None
    assert [t.get_text() for t in legend.get_texts()] == ["raw", "smoothed"]


@pytest.mark.tier2
@pytest.mark.parametrize("backend", ["pyqtgraph", "matplotlib"])
def test_legend_false_suppresses_all_legends(backend, qtbot):
    if not _has(backend):
        pytest.skip(f"{backend} not registered")
    # labeled curves AND a color_by scatter — legend=False silences both paths
    node = _overlay(
        qv.Curve(_DATA, x="x", y="y", label="raw"),
        qv.Scatter(_DATA, x="x", y="y", color_by="cat"),
        legend=False,
    )
    view = qv.View(node, backend=backend)
    qtbot.addWidget(view)
    if backend == "matplotlib":
        assert view.handle.axes[0].get_legend() is None
    else:
        assert getattr(view.handle.plots[0], "_qtviz_legend", None) is None


@pytest.mark.tier2
@pytest.mark.parametrize("backend", ["pyqtgraph", "matplotlib"])
def test_no_double_legend_with_color_by(backend, qtbot):
    """Risk #3: a color_by Scatter inside a labeled Overlay yields ONE legend —
    the color key merged with the labeled entries, not two stacked legends."""
    if not _has(backend):
        pytest.skip(f"{backend} not registered")
    node = _overlay(
        qv.Scatter(_DATA, x="x", y="y", color_by="cat"),
        qv.Curve(_DATA, x="x", y="y", label="trend"),
    )
    view = qv.View(node, backend=backend)
    qtbot.addWidget(view)
    if backend == "matplotlib":
        ax = view.handle.axes[0]
        legends = [a for a in ax.get_children() if type(a).__name__ == "Legend"]
        assert len(legends) == 1
        texts = [t.get_text() for t in ax.get_legend().get_texts()]
    else:
        plot = view.handle.plots[0]
        lg = plot._qtviz_legend
        assert lg is not None
        texts = [label.text for _s, label in lg.items]
    assert set(texts) == {"a", "b", "c", "trend"}  # color key + the labeled entry


@pytest.mark.tier2
def test_legend_position_none_suppresses(qtbot):
    view = qv.View(_labeled_overlay(legend_position="none"), backend="pyqtgraph")
    qtbot.addWidget(view)
    assert getattr(view.handle.plots[0], "_qtviz_legend", None) is None


@pytest.mark.tier2
def test_matplotlib_legend_position_top(qtbot):
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    view = qv.View(_labeled_overlay(legend_position="top"), backend="matplotlib")
    qtbot.addWidget(view)
    legend = view.handle.axes[0].get_legend()
    assert legend._loc == 9  # mpl code for "upper center"


@pytest.mark.tier2
def test_bare_labeled_element_gets_a_legend(qtbot):
    """`label` is honored even without an explicit Overlay (a bare element renders
    as a one-child surface) — this is what makes label honor-or-warn honest."""
    view = qv.View(qv.Curve(_DATA, x="x", y="y", label="only"), backend="pyqtgraph")
    qtbot.addWidget(view)
    lg = view.handle.plots[0]._qtviz_legend
    assert [label.text for _s, label in lg.items] == ["only"]


# ── Tier-1: webengine carries the label as the trace name ────────────────────
@pytest.mark.tier1
def test_webengine_trace_name_uses_label():
    from qtviz.backends.webengine import _figure

    fig = _figure.build_figure(_labeled_overlay(), qv.Theme.light())
    assert [t["name"] for t in fig["data"]] == ["raw", "smoothed"]


# ═══════════════════════════════════════════════════════════════════════════════
# Increment 4 — legend parity: webengine legends on, pyqtgraph gradient colorbar
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.tier1
def test_webengine_showlegend_follows_surface():
    from qtviz.backends.webengine import _figure

    fig = _figure.build_figure(_labeled_overlay(), qv.Theme.light())
    assert fig["layout"]["showlegend"] is True
    assert [t["showlegend"] for t in fig["data"]] == [True, True]
    off = _figure.build_figure(_labeled_overlay(legend=False), qv.Theme.light())
    assert off["layout"]["showlegend"] is False
    # an unlabeled trace contributes no legend entry (its name is an opaque id)
    bare = _figure.build_figure(qv.Curve(_DATA, x="x", y="y"), qv.Theme.light())
    assert bare["data"][0]["showlegend"] is False


@pytest.mark.tier1
def test_webengine_label_is_now_honored():
    import warnings

    from qtviz.backends.webengine import _figure
    from qtviz.core import _degrade

    _degrade.reset()
    with warnings.catch_warnings():
        warnings.simplefilter("error", category=qv.errors.QtvizWarning)
        _figure.build_figure(_labeled_overlay(), qv.Theme.light())  # no label warning


@pytest.mark.tier1
def test_webengine_continuous_color_by_emits_colorbar():
    from qtviz.backends.webengine import _figure

    fig = _figure.build_figure(qv.Scatter(_DATA, x="x", y="y", color_by="y"),
                               qv.Theme.light())
    marker = fig["data"][0]["marker"]
    assert "colorbar" in marker and "colorscale" in marker
    assert np.allclose(np.asarray(marker["color"]), _DATA["y"])   # numeric, Plotly maps it
    assert marker["cmin"] == float(np.min(_DATA["y"]))
    assert marker["cmax"] == float(np.max(_DATA["y"]))


@pytest.mark.tier1
def test_webengine_legend_position_top():
    from qtviz.backends.webengine import _figure

    fig = _figure.build_figure(_labeled_overlay(legend_position="top"), qv.Theme.light())
    assert fig["layout"]["legend"]["orientation"] == "h"


@pytest.mark.tier2
def test_pyqtgraph_continuous_colorbar_is_a_true_gradient(qtbot):
    import pyqtgraph as pg

    view = qv.View(qv.Scatter(_DATA, x="x", y="y", color_by="y"), backend="pyqtgraph")
    qtbot.addWidget(view)
    plot = view.handle.plots[0]
    bar = getattr(plot, "_qtviz_cbar", None)
    assert isinstance(bar, pg.ColorBarItem)
    lo, hi = bar.levels()
    assert np.allclose((lo, hi), (float(np.min(_DATA["y"])), float(np.max(_DATA["y"]))))
    # the ramp no longer masquerades as a stepped swatch key
    assert getattr(plot, "_qtviz_legend", None) is None


@pytest.mark.tier2
def test_native_series_colors_cycle_and_match_legend(qtbot):
    """Two default-colored series must draw in distinct palette slots (0.4 fix:
    native renderers used palette[0] for every series while webengine cycled),
    and the legend swatches must match the drawn colors. An annotation element
    in the overlay must NOT consume a palette slot."""
    theme = qv.Theme.light()
    node = qv.Overlay([
        qv.Curve(_DATA, x="x", y="y", label="a"),
        qv.HLine(3.0),                                        # chrome, no slot
        qv.Curve(_DATA, x="x", y=qv.col("y") * 2.0, label="b"),
    ])
    view = qv.View(node, backend="pyqtgraph", theme=theme)
    qtbot.addWidget(view)
    a, _h, b = node.children
    pen_a = view.native(a.id).opts["pen"].color().name()
    pen_b = view.native(b.id).opts["pen"].color().name()
    assert pen_a == theme.palette[0].qt().name()
    assert pen_b == theme.palette[1].qt().name()              # slot 1, not 0 or 2
    entries = {lb.text: s for s, lb in view.handle.plots[0]._qtviz_legend.items}
    assert entries["a"].item.opts["brush"].color().name() == pen_a
    assert entries["b"].item.opts["brush"].color().name() == pen_b


@pytest.mark.tier2
def test_milestone_0_3_acceptance(qtbot):
    """milestone-0.3-firstclass §8, end to end: labeled Curves in a log-x Overlay
    render with a log axis, a two-entry legend, and a data-space brush on
    pyqtgraph; the backend switch to matplotlib keeps all three; the webengine
    figure spec carries the log axis + legend."""
    if not _has("matplotlib"):
        pytest.skip("matplotlib not registered")
    from qtviz.backends.webengine import _figure

    data = {"x": np.array([1.0, 10.0, 100.0, 1000.0]), "y": np.array([1.0, 2.0, 3.0, 4.0])}
    node = qv.Overlay(
        [qv.Curve(data, x="x", y="y", label="raw"),
         qv.Curve(data, x="x", y=qv.col("y") * 2.0, label="smoothed")],
        options=qv.OverlayOptions(title="Acceptance", x=qv.AxisSpec(scale="log"),
                                  legend=True),
    )
    view = qv.View(node, backend="pyqtgraph")
    qtbot.addWidget(view)
    plot = view.handle.plots[0]
    assert plot.getAxis("bottom").logMode                       # log x, data pre-transformed
    assert [lb.text for _s, lb in plot._qtviz_legend.items] == ["raw", "smoothed"]
    got: list = []
    view.on(qv.SelectEvent, got.append, throttle_ms=0)
    plot.getViewBox().select_bounds(5.0, 0.0, 500.0, 10.0)      # data-space brush
    assert got and got[-1].bounds == (5.0, 0.0, 500.0, 10.0)

    view.set_backend("matplotlib")                              # swap keeps everything
    ax = view.handle.axes[0]
    assert ax.get_xscale() == "log"
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["raw", "smoothed"]

    fig = _figure.build_figure(node, qv.Theme.light())          # webengine spec parity
    assert fig["layout"]["xaxis"]["type"] == "log"
    assert fig["layout"]["showlegend"] is True
    assert [t["name"] for t in fig["data"]] == ["raw", "smoothed"]


@pytest.mark.tier2
def test_pyqtgraph_eq_hist_density_keeps_endpoints_key(qtbot):
    """Legend honesty ([D48]): an eq_hist density raster's color↔value map is
    non-linear, so it keeps the endpoints-only key — never a gradient bar that
    would imply linear ticks."""
    pytest.importorskip("datashader")
    rng = np.random.default_rng(3)
    data = {"x": rng.normal(size=5000), "y": rng.normal(size=5000)}
    view = qv.View(qv.Scatter(data, x="x", y="y", raster="datashader"),
                   backend="pyqtgraph")
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view.handle is not None, timeout=5000)
    plot = view.handle.plots[0]
    assert getattr(plot, "_qtviz_cbar", None) is None
    assert getattr(plot, "_qtviz_legend", None) is not None  # endpoints-only key
