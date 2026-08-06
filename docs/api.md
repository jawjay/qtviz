# API reference

Auto-generated from the public `qtviz` namespace (everything in `qtviz.__all__`).

Describe a plot once as immutable data (an `Element`), compose with `*`
(overlay) and `+` (layout), then render through any backend — pyqtgraph,
matplotlib, or webengine — swappable at runtime. `qv.show(...)` is the script
one-liner; `qv.View` is the plain QWidget for applications.

`qtviz.__version__` reports the installed version.

## Elements

::: qtviz.Scatter

::: qtviz.Curve

::: qtviz.Bars

::: qtviz.Histogram

::: qtviz.Image

::: qtviz.Heatmap

::: qtviz.ErrorBars

::: qtviz.Spread

::: qtviz.BoxPlot

::: qtviz.Violin

::: qtviz.Area

::: qtviz.Ecdf

::: qtviz.Pie

::: qtviz.Contour

::: qtviz.Mesh

::: qtviz.Quiver

::: qtviz.Stem

::: qtviz.Streamlines

::: qtviz.Inset

::: qtviz.RawFigure

### Polar ([D119])

::: qtviz.PolarGrid

::: qtviz.polar

::: qtviz.wedge

## Annotation & reference elements

::: qtviz.HLine

::: qtviz.VLine

::: qtviz.Span

::: qtviz.Text

::: qtviz.Arrow

::: qtviz.Rect

::: qtviz.Ellipse

::: qtviz.Polygon

::: qtviz.RefLine

## Composition & View

`Element` is the base class of every element above — the type to use in your
own annotations (`def render(el: qv.Element) -> None`). `Node` is the
`Element | Overlay | Layout` union that `View` and `show` accept.

::: qtviz.Element

::: qtviz.Node

::: qtviz.Overlay

::: qtviz.Layout

::: qtviz.View

::: qtviz.show

### Panes — downstream use of each surface

After render, each surface (grid cell, tab, splitter pane — or the whole plot
of a single-surface render) is addressable as a **pane** ([D145]/[D147]):
`view.pane("price")` returns a live `PaneHandle` — the "Axes of qtviz" —
scoped to interaction-side verbs (`set_range`, `autorange`, `select`,
`capture`/`restore`, `native`, `elements`). Describe-side configuration stays
on the node (`.opts()`, `Layout.with_pane` + `set_root`). Whole-render state
is a `LayoutState` — ordered `(label, ViewState)` pairs, matched by label
across rebuilds and backend switches. These are returned types, importable
from `qtviz.core.backend` ([D135] return-type convention).

::: qtviz.core.backend.PaneHandle

::: qtviz.core.backend.LayoutState

## Data binding

::: qtviz.col

::: qtviz.lit

::: qtviz.tabular

::: qtviz.gridded

::: qtviz.set_raster_threshold

::: qtviz.set_raster_size

::: qtviz.stream

## Encoding & styling

::: qtviz.Color

::: qtviz.Palette

::: qtviz.palettes

::: qtviz.Theme

::: qtviz.set_default_theme

::: qtviz.Norm

::: qtviz.OverlayOptions

::: qtviz.LayoutOptions

::: qtviz.AxisSpec

## Events

::: qtviz.Event

::: qtviz.RangeEvent

::: qtviz.PickEvent

::: qtviz.SelectEvent

::: qtviz.HoverEvent

::: qtviz.TapEvent

## Reactive

::: qtviz.signal

::: qtviz.derived

::: qtviz.effect

::: qtviz.batch

::: qtviz.Signal

## HoloViews / hvplot adapter

::: qtviz.from_holoviews

::: qtviz.from_holoviews_dmap

::: qtviz.from_hvplot

## Errors

`QtvizError` is the base of every error qtviz raises on purpose —
`except qv.QtvizError` catches every deliberate rejection. The full taxonomy
(validation, negotiation, adapters, missing dependencies) lives in
`qtviz.errors`.

::: qtviz.QtvizError

## Backend selection

::: qtviz.set_default_backend

## Backend authors (`qtviz.backends`)

The extension namespace ([D125]): third-party backends register through the
`qtviz.backends` entry-point group, and the author-facing contracts live here —
`qtviz.backends.Capabilities` (the honesty declaration) and
`qtviz.backends.set_backend_priority` (the auto-negotiation preference order).
See [Backends](backends.md) for the full extension guide.
