"""Mark drawers — the matplotlib [D122] adapter.

One function per mark type, written once; `render_lowered` is the generic
renderer for any element whose `lower()` is overridden and that has no native
fast-path registration. Marks arrive in linear data space ([D121]); mpl's axes
transform handles log, so no pretransform here — only the RefLine
straight-line warn-drop rule survives ([D99]). Angles are CCW degrees ([D96]);
mpl rotation is CCW too, so no sign flip.
"""

from __future__ import annotations

import numpy as np

from ...core.lowering import LowerContext
from ...core.marks import (
    ArrowMark,
    Band,
    Markers,
    PolygonMark,
    Polyline,
    Rule,
    SpanMark,
    TextMark,
)
from ._events import wire_pick
from ._renderers import _MARKER, _ls

_DRAWSTYLE = {"pre": "steps-pre", "post": "steps-post", "mid": "steps-mid"}

# Arrow head vocabulary → mpl arrowstyle ([D96]).
_ARROWSTYLE = {"end": "-|>", "both": "<|-|>", "none": "-"}


def draw_polyline(m: Polyline, ctx):
    st = m.stroke
    color = st.color.mpl()
    if m.connect == "pairs":
        from matplotlib.collections import LineCollection  # noqa: PLC0415

        segs = list(np.stack([m.x, m.y], axis=1).reshape(-1, 2, 2))
        item = LineCollection(segs, colors=[color], linewidths=st.width,
                              linestyles=_ls(st.dash), alpha=st.alpha)
        ctx.parent_axes.add_collection(item)
        return item
    (line,) = ctx.parent_axes.plot(
        m.x, m.y, color=color, lw=st.width, ls=_ls(st.dash), alpha=st.alpha,
        drawstyle=_DRAWSTYLE[m.step] if m.step is not None else "default")
    if m.fill_to is not None:
        fill = m.fill or m.stroke
        ctx.parent_axes.fill_between(m.x, m.y, m.fill_to,
                                     color=fill.color.mpl(), alpha=fill.alpha)
    return line


def draw_markers(m: Markers, ctx):
    color: object = (m.fill if isinstance(m.fill, np.ndarray)
                     else (m.fill or ctx.theme.foreground).mpl())
    size = np.asarray(m.size, dtype="float64") ** 2  # mpl `s` is pt²
    return ctx.parent_axes.scatter(
        m.x, m.y, color=color, s=size, alpha=m.alpha, marker=_MARKER[m.marker],
        edgecolors=None if m.edge is None else m.edge.color.mpl())


def draw_band(m: Band, ctx):
    color = m.fill.color.mpl()
    if m.orient == "h":  # ([D99]) band spans x as a function of y
        return ctx.parent_axes.fill_betweenx(m.pos, m.lo, m.hi,
                                             color=color, alpha=m.fill.alpha)
    return ctx.parent_axes.fill_between(m.pos, m.lo, m.hi,
                                        color=color, alpha=m.fill.alpha)


def _slope_scales_ok(ctx) -> bool:
    if ctx.x_scale in ("log", "symlog") or ctx.y_scale in ("log", "symlog"):
        import warnings  # noqa: PLC0415

        from ...errors import QtvizWarning  # noqa: PLC0415

        warnings.warn("matplotlib: RefLine is a straight data-space line and has "
                      "no log-scale form; it was dropped.", QtvizWarning, stacklevel=2)
        return False
    return True


def draw_rule(m: Rule, ctx):
    st = m.stroke
    kw = {"color": st.color.mpl(), "lw": st.width, "ls": _ls(st.dash),
          "alpha": st.alpha}
    if m.orient == "slope":
        if not _slope_scales_ok(ctx):
            return None
        return ctx.parent_axes.axline((0.0, m.at), slope=m.slope, **kw)
    if m.orient == "h":
        return ctx.parent_axes.axhline(m.at, **kw)
    return ctx.parent_axes.axvline(m.at, **kw)


def draw_span(m: SpanMark, ctx):
    fn = ctx.parent_axes.axhspan if m.orient == "h" else ctx.parent_axes.axvspan
    return fn(m.lo, m.hi, color=m.fill.color.mpl(), alpha=m.fill.alpha)


_VA = {"center": "center", "top": "top", "bottom": "bottom"}


def draw_text(m: TextMark, ctx):
    fg = m.color.mpl()
    kwargs: dict = {"color": fg, "ha": m.halign, "va": _VA[m.valign],
                    "rotation": m.rotation, "rotation_mode": "anchor"}
    if m.size is not None:
        kwargs["fontsize"] = m.size
    if m.frame:
        kwargs["bbox"] = {"boxstyle": "round,pad=0.35",
                          "facecolor": ctx.theme.background.mpl(), "edgecolor": fg}
    text = ctx.parent_axes.text(m.x, m.y, m.text, **kwargs)
    if m.mask is not None:  # [D117] contour-label line break
        x0, y0, x1, y1 = m.mask
        (mask,) = ctx.parent_axes.plot([x0, x1], [y0, y1],
                                       color=ctx.theme.background.mpl(),
                                       lw=m.mask_width, solid_capstyle="butt",
                                       zorder=text.get_zorder() - 0.1)
        return [mask, text]
    return text


def draw_polygon(m: PolygonMark, ctx):
    """One closed data-space outline ([D97]) as a Polygon patch — the shared
    core point builders (`rect_points`/`ellipse_points`/`close_points`) supply
    the geometry, so all shapes ride one patch type."""
    from matplotlib import patches  # noqa: PLC0415

    style: dict = {"linewidth": 0.0, "edgecolor": "none", "facecolor": "none"}
    if m.stroke is not None:
        style.update(edgecolor=m.stroke.color.mpl(), linewidth=m.stroke.width,
                     alpha=m.stroke.alpha)
    if m.fill is not None:
        style["facecolor"] = m.fill.color.mpl()
    patch = patches.Polygon(np.column_stack([m.x, m.y]), closed=True, **style)
    ctx.parent_axes.add_patch(patch)
    return patch


def draw_arrow(m: ArrowMark, ctx):
    st = m.stroke
    return ctx.parent_axes.annotate(
        "", xy=(m.x1, m.y1), xytext=(m.x0, m.y0),
        arrowprops={"arrowstyle": _ARROWSTYLE[m.head], "color": st.color.mpl(),
                    "lw": st.width, "alpha": st.alpha, "shrinkA": 0, "shrinkB": 0},
        annotation_clip=False,
    )


MARK_DRAWERS = {
    Polyline: draw_polyline,
    Band: draw_band,
    Markers: draw_markers,
    Rule: draw_rule,
    SpanMark: draw_span,
    TextMark: draw_text,
    PolygonMark: draw_polygon,
    ArrowMark: draw_arrow,
}


def render_lowered(element, ctx):
    """The generic renderer for lowered elements. Brush selection registers in
    `attach` via `element.select_xy()` (uniform with the natives); pickable
    Markers wire here because only the drawer holds the live artist."""
    lowered = element.lower(LowerContext(theme=ctx.theme,
                                         series_index=ctx.series_index,
                                         show_legend=ctx.show_legend))
    artists = []
    for mark in lowered.marks:
        artist = MARK_DRAWERS[type(mark)](mark, ctx)
        if artist is None:
            continue
        if isinstance(mark, Markers) and mark.pickable and hasattr(artist, "get_offsets"):
            wire_pick(artist, element.id, ctx.event_bus)
        artists.extend(artist) if isinstance(artist, list) else artists.append(artist)
    if len(artists) == 1:
        return artists[0]
    return artists or None
