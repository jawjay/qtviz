"""Tier-1 — public-API hardening (error taxonomy + boundary validation).

These lock in the contract changes from the API review:
- construction/validation rejections raise `ValidationError`, which is **both**
  a `QtvizError` and a stdlib `ValueError` (so old `except ValueError` and new
  `except QtvizError` handlers both catch bad input);
- mutable global setters validate at the boundary instead of failing later;
- install hints name the packaged extra (`qtviz[X]`), usable outside a checkout;
- packaging invariants (py.typed ships; no accidental namespace leaks).
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


# ── install hints name the packaged extra, not a repo-checkout workflow ──────
def test_hvplot_install_hint_names_packaged_extra():
    adapter = pytest.importorskip("qtviz.adapter")
    # A plain object has no `.hvplot` accessor regardless of whether hvplot is
    # installed, so this deterministically hits the missing-accessor branch.
    with pytest.raises(errors.AdapterError) as exc:
        adapter.from_hvplot(object(), "line")
    msg = str(exc.value)
    # An installed user can act on this hint without a repo checkout.
    assert 'qtviz[hvplot]' in msg
    assert "uv sync" not in msg


# ── every deliberate rejection sits under QtvizError ([D143] wave B) ─────────
@pytest.mark.parametrize(
    "build",
    [
        lambda: qv.Overlay([]),
        lambda: qv.Layout([]),
        lambda: qv.Color("definitely-not-a-color"),
        lambda: qv.Palette([]),
    ],
    ids=["overlay-empty", "layout-empty", "color-bad-name", "palette-empty"],
)
def test_constructor_rejections_are_qtviz_errors(build):
    with pytest.raises(errors.QtvizError):
        build()
    with pytest.raises(ValueError):  # legacy handlers keep working
        build()


def test_missing_dependency_error_sits_under_both_taxonomies():
    assert issubclass(errors.MissingDependencyError, errors.QtvizError)
    assert issubclass(errors.MissingDependencyError, ImportError)


# ── colors: CSS4 names, eager validation, close-match hints ([D143]) ─────────
def test_css4_color_names_accepted():
    assert qv.Color("steelblue").hex() == "#4682b4"
    assert qv.Color("rebeccapurple").hex() == "#663399"


def test_unknown_color_suggests_close_match():
    with pytest.raises(errors.ValidationError) as exc:
        qv.Color("steelblu")
    assert "steelblue" in str(exc.value)


def test_bad_static_color_fails_at_construction():
    data = {"x": np.arange(3), "y": np.arange(3)}
    with pytest.raises(errors.ValidationError):
        qv.Curve(data, x="x", y="y", color="not-a-color")
    with pytest.raises(errors.ValidationError):
        qv.Scatter(data, x="x", y="y", color="not-a-color")


# ── construction-time validation gaps closed (wave B) ────────────────────────
def test_scatter_marker_validated_at_construction():
    data = {"x": np.arange(3), "y": np.arange(3)}
    with pytest.raises(errors.ValidationError) as exc:
        qv.Scatter(data, x="x", y="y", marker="blob")
    assert "marker" in str(exc.value)


def test_image_rejects_wrong_ndim_and_extent():
    with pytest.raises(errors.ValidationError):
        qv.Image(np.arange(10.0), extent=(0, 1, 0, 1))  # 1-D into a 2-D element
    with pytest.raises(errors.ValidationError):
        qv.Image(np.zeros((4, 4)), extent=(0, 1))  # malformed extent
    qv.Image(np.zeros((4, 4, 4)), extent=(0, 1, 0, 1))  # RGBA stays legal


def test_channel_length_mismatch_names_the_element():
    el = qv.Scatter({"x": np.arange(3), "y": np.arange(3)}, x="x", y="y")
    with pytest.raises(errors.ValidationError) as exc:
        el.data.resolve_channels({"x": "x", "y": np.arange(2)}, who="Scatter")
    assert str(exc.value).startswith("Scatter:")


# ── packaging: PEP 561 marker ships with the package ─────────────────────────
def test_py_typed_marker_ships():
    from importlib import resources

    assert resources.files("qtviz").joinpath("py.typed").is_file()


# ── the namespace holds only deliberate names ────────────────────────────────
def test_no_accidental_namespace_leaks():
    assert not hasattr(qv, "PackageNotFoundError")
    assert not hasattr(qv, "annotations")


def test_palette_from_matplotlib_uses_supported_api():
    pytest.importorskip("matplotlib")
    p = qv.Palette.from_matplotlib("magma", n=5)
    assert len(p) == 5
    assert p.kind == "continuous"
