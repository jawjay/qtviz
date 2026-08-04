"""Tier-1 — public-API hardening (error taxonomy + boundary validation).

These lock in the contract changes from the API review:
- construction/validation rejections raise `ValidationError`, which is **both**
  a `QtvizError` and a stdlib `ValueError` (so old `except ValueError` and new
  `except QtvizError` handlers both catch bad input);
- mutable global setters validate at the boundary instead of failing later;
- install hints are uniform (uv, never pip).
"""

from __future__ import annotations

import numpy as np
import pytest

qv = pytest.importorskip("qtviz")
errors = pytest.importorskip("qtviz.errors")

pytestmark = pytest.mark.tier1


# ── ValidationError sits under BOTH taxonomies (One-Version backward compat) ──
def test_validation_error_is_both_qtviz_and_value_error():
    assert issubclass(errors.ValidationError, errors.QtvizError)
    assert issubclass(errors.ValidationError, ValueError)


@pytest.mark.parametrize(
    "build",
    [
        lambda t: qv.Scatter(t, x="x", y="y", alpha=1.5),                       # out of range
        lambda t: qv.Scatter(t, x="x", y="y", color="red", color_by="cat"),     # exclusive
        lambda t: qv.Scatter(t, x="x", y="y", size=5.0, size_by="z"),           # exclusive
        lambda t: qv.Scatter(t, x="nope", y="y"),                               # unknown column
        lambda t: qv.Curve(t, x="x", y="y", alpha=-0.1),
        lambda t: qv.Spread(t, x="x", lo="y_lo", hi="y_hi", alpha=2.0),
    ],
)
def test_construction_rejections_raise_validation_error(table, build):
    with pytest.raises(errors.ValidationError):
        build(table)


def test_bad_input_caught_as_qtviz_error(table):
    # The whole point of #1: `except QtvizError` now catches construction errors.
    with pytest.raises(errors.QtvizError):
        qv.Scatter(table, x="x", y="y", alpha=9.0)


def test_bad_input_still_caught_as_value_error(table):
    # ...without breaking code that already catches ValueError.
    with pytest.raises(ValueError):
        qv.Scatter(table, x="x", y="y", alpha=9.0)


def test_rawfigure_bad_kind_raises_validation_error():
    with pytest.raises(errors.ValidationError):
        qv.RawFigure(object(), kind="bogus")


def test_mismatched_channel_lengths_raise_validation_error():
    from qtviz.data.ref import EagerTabularRef

    cols = {"a": np.arange(3), "b": np.arange(5)}
    ref = EagerTabularRef(source=cols, columns=cols)
    with pytest.raises(errors.ValidationError):
        ref.resolve_channels({"x": "a", "y": "b"})


# ── boundary validation on the mutable global setters (#3) ───────────────────
def test_set_default_backend_rejects_unregistered_name():
    with pytest.raises(errors.BackendNotAvailableError):
        qv.set_default_backend("definitely-not-a-backend")


def test_set_backend_priority_is_lenient_with_unknown_names():
    # A priority may name a not-yet-installed optional backend — must not raise.
    import qtviz.backends as B

    saved = list(B._PRIORITY)
    try:
        qv.set_backend_priority(["pyqtgraph", "not-installed-yet"])
    finally:
        B._PRIORITY[:] = saved


@pytest.mark.parametrize("bad", [0, -10])
def test_set_raster_threshold_rejects_non_positive(bad):
    with pytest.raises(errors.ValidationError):
        qv.set_raster_threshold(bad)


@pytest.mark.parametrize("dims", [(0, 100), (100, 0), (-1, -1)])
def test_set_raster_size_rejects_non_positive(dims):
    with pytest.raises(errors.ValidationError):
        qv.set_raster_size(*dims)


# ── install hints are uniform: uv, never pip (#5) ────────────────────────────
def test_hvplot_install_hint_uses_uv_not_pip():
    adapter = pytest.importorskip("qtviz.adapter")
    # A plain object has no `.hvplot` accessor regardless of whether hvplot is
    # installed, so this deterministically hits the missing-accessor branch.
    with pytest.raises(errors.AdapterError) as exc:
        adapter.from_hvplot(object(), "line")
    msg = str(exc.value)
    assert "uv" in msg
    assert "pip install" not in msg
