"""[D136] the `annotate=` accessor arm — Bars annotating from a column.

The 2.0 union shipped as `bool | fmt-str`; this closes the deferred arm:
a **non-str accessor** (`col()` expression, callable, or raw array) supplies
per-bar label text from the data instead of formatting the bar's own value.
A bare `str` stays a [D86] format spec (`col("name")` is the column arm —
the one place the accessor union's plain-string form is taken).

`by=` aggregates rows into bars (`group_bars` sums), so a per-row label
source is ambiguous there — construction-time `ValidationError`, never a
silent drop ([D51]).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")

_B = {"cat": ["a", "b", "c"], "v": [3.0, 5.0, 2.0],
      "name": ["alpha", "beta", "gamma"], "n": [10, 20, 30]}


def _backend(name):
    import qtviz.backends as B

    if name not in B.list_available():
        pytest.skip(f"{name} backend unavailable")
    return B.get(name)


# ── tier 1 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier1
def test_accessor_arm_construction():
    el = qv.Bars(_B, x="cat", y="v", annotate=qv.col("name"))
    # one stored field: `annotate` holds the accessor; `annotate_by` derives it
    assert el.annotate_by is el.annotate is not None
    # str stays the fmt arm; bool arms unchanged
    assert qv.Bars(_B, x="cat", y="v", annotate=".1f").annotate_by is None
    assert qv.Bars(_B, x="cat", y="v", annotate=True).annotate == "auto"
    # callable and raw-array accessors are accepted too
    qv.Bars(_B, x="cat", y="v", annotate=lambda t: t["name"])
    qv.Bars(_B, x="cat", y="v", annotate=np.array(["p", "q", "r"]))


@pytest.mark.tier1
def test_accessor_arm_value_semantics():
    a = qv.Bars(_B, x="cat", y="v", annotate=qv.col("name"))
    b = qv.Bars(_B, x="cat", y="v", annotate=qv.col("name"))
    assert a == b and hash(a) == hash(b)
    assert a != qv.Bars(_B, x="cat", y="v", annotate=qv.col("cat"))


@pytest.mark.tier1
def test_accessor_arm_rejects_by():
    from qtviz.errors import ValidationError

    with pytest.raises(ValidationError, match="annotate"):
        qv.Bars(_B, x="cat", y="v", by="cat", annotate=qv.col("name"))


@pytest.mark.tier1
def test_bad_fmt_str_still_raises():
    from qtviz.errors import ValidationError

    with pytest.raises(ValidationError):
        qv.Bars(_B, x="cat", y="v", annotate="nope}")


@pytest.mark.tier1
def test_webengine_traces_use_column_text():
    from qtviz.backends.webengine import _figure

    light = qv.Theme.light()
    bar = _figure.build_figure(
        qv.Bars(_B, x="cat", y="v", annotate=qv.col("name")), light)["data"][0]
    assert bar["text"] == ["alpha", "beta", "gamma"]
    # numeric label columns format through '%g', not float repr
    bar = _figure.build_figure(
        qv.Bars(_B, x="cat", y="v", annotate=qv.col("n")), light)["data"][0]
    assert bar["text"] == ["10", "20", "30"]


@pytest.mark.tier1
def test_horizontal_accessor_labels():
    from qtviz.backends.webengine import _figure

    bar = _figure.build_figure(
        qv.Bars(_B, x="cat", y="v", orient="horizontal",
                annotate=qv.col("name")), qv.Theme.light())["data"][0]
    assert bar["text"] == ["alpha", "beta", "gamma"]


# ── tier 2 ───────────────────────────────────────────────────────────────────
@pytest.mark.tier2
def test_mpl_accessor_labels(qtbot):
    pytest.importorskip("matplotlib")
    b = _backend("matplotlib")
    handle = b.render(qv.Bars(_B, x="cat", y="v", annotate=qv.col("name")),
                      theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    texts = [t.get_text() for t in handle.axes[0].texts]
    assert texts == ["alpha", "beta", "gamma"]


@pytest.mark.tier2
def test_pg_accessor_labels(qtbot):
    import pyqtgraph as pg

    handle = _backend("pyqtgraph").render(
        qv.Bars(_B, x="cat", y="v", annotate=qv.col("name")),
        theme=qv.Theme.light())
    qtbot.addWidget(handle.widget)
    texts = [i for p in handle.plots for i in p.getViewBox().addedItems
             if isinstance(i, pg.TextItem)]
    assert sorted(t.textItem.toPlainText() for t in texts) == [
        "alpha", "beta", "gamma"]
