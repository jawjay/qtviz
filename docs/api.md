# API reference

Auto-generated from the public `qtviz` namespace (everything in `qtviz.__all__`).

`qtviz.__version__` reports the installed version.

## Elements

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - Scatter
        - Curve
        - Bars
        - Histogram
        - Image
        - Heatmap
        - ErrorBars
        - Spread
        - BoxPlot
        - Violin
        - Area
        - Ecdf
        - Pie
        - Contour
        - Mesh
        - Quiver
        - Stem
        - Streamlines
        - RawFigure

## Annotation & reference elements

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - HLine
        - VLine
        - Span
        - Text
        - Arrow
        - Rect
        - Ellipse
        - Polygon
        - RefLine

## Composition & View

`Element` is the base class of every element above — the type to use in your
own annotations (`def render(el: qv.Element) -> None`). `Node` is the
`Element | Overlay | Layout` union that `View` and `show` accept.

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - Element
        - Node
        - Overlay
        - Layout
        - View
        - show

## Data binding

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - col
        - lit
        - tabular
        - gridded
        - set_raster_threshold
        - set_raster_size
        - stream

## Encoding & styling

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - Color
        - Palette
        - palettes
        - Theme
        - set_default_theme
        - Norm
        - OverlayOptions
        - LayoutOptions
        - AxisSpec

## Events

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - Event
        - RangeEvent
        - PickEvent
        - SelectEvent
        - HoverEvent
        - TapEvent

## Reactive

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - signal
        - derived
        - effect
        - batch
        - Signal

## HoloViews / hvplot adapter

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - from_holoviews
        - from_holoviews_dmap
        - from_hvplot

## Errors

`QtvizError` is the base of every error qtviz raises on purpose —
`except qv.QtvizError` catches every deliberate rejection. The full taxonomy
(validation, negotiation, adapters, missing dependencies) lives in
`qtviz.errors`.

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - QtvizError

## Backend selection

::: qtviz
    options:
      show_root_heading: false
      show_root_toc_entry: false
      members:
        - set_default_backend

## Backend authors (`qtviz.backends`)

The extension namespace ([D125]): third-party backends register through the
`qtviz.backends` entry-point group, and the author-facing contracts live here —
`qtviz.backends.Capabilities` (the honesty declaration) and
`qtviz.backends.set_backend_priority` (the auto-negotiation preference order).
See [Backends](backends.md) for the full extension guide.
