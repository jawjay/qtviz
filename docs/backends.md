# Writing a backend

Backends are qtviz's open seam: **registered, never imported by the core**.
Adding one touches only its own directory — the composition layer, negotiation,
`View`, and every existing backend are none the wiser. This page is the
contract; the acceptance bar is mechanical: *make the conformance suite green*.

```
your element renderers ──┐
Capabilities (honest) ───┼──►  Backend  ──register──►  qtviz.backends
RenderHandle (lifecycle) ┘
```

## The Backend protocol

A backend is any object with this surface (`qtviz.core.backend.Backend`):

```python
class MyBackend:
    name = "mybackend"
    capabilities = Capabilities(...)     # static, behavior-free, HONEST
    renderers = RendererRegistry()       # Element type → renderer fn

    def supports(self, element_type) -> bool: ...
    def render(self, node, *, theme, parent=None) -> RenderHandle: ...
    def can_host(self, kind) -> bool: ...          # "overlay" / "grid" panes?
    def honored_options(self, element_type) -> frozenset[str]: ...


import qtviz.backends
qtviz.backends.register(MyBackend())
```

`render` receives a **resolved** node: every element's channel accessors have
already become role-keyed numpy arrays (`element.data.series("x")`), and
datashaded elements have already become `Image`s. Your renderers read roles,
never user accessors.

## The three honesty contracts

These are what the conformance suite (`tests/qtviz/test_backend_conformance.py`)
actually enforces — they are the library's character, not style preferences:

1. **Capability honesty ([D52]).** Every flag in your `Capabilities` must have
   a code path behind it. No aspirational `dimensions={3}`, no `streaming=True`
   without an incremental path (`set_element_data`) or an equivalent.
2. **Honor-or-warn ([D51], spec §3.4).** For each element type, declare the
   `RECOMMENDED_OPTIONS` you actually consume in an `HONORED` table and return
   it from `honored_options()`. Call `check_recommended(element, ...)` before
   rendering: anything the user set that you don't honor warns once
   (`QtvizWarning`) — silent drops fail the suite.
3. **R1 — data space at every seam ([D59]).** Every coordinate you emit
   (events) or accept (state, brush bounds) is **data space**. If your engine
   works in another space (log exponents, screen pixels), you normalize at the
   boundary, in both directions.

## RenderHandle — the mutable half

Your `render()` returns a `RenderHandle` subclass owning the widget tree:

| Member | Contract |
|---|---|
| `widget` | a plain `QWidget` — the View parents it |
| `event_bus` | an `EventBus`; emit the typed events your capabilities declare |
| `update(new_root)` | re-render in place (raise `NotImplementedError` to let the View rebuild) |
| `set_element_data(id, arrays)` | in-place data write; return `False` when unsupported ([D77]) |
| `capture_state()` / `restore_state()` | a data-space `ViewState` — this is what makes backend *switching* seamless |
| `export(fmt, path, *, dpi=None, transparent=False)` | write what your `capabilities.exports` declares; warn on knobs you can't honor ([D72]) |
| `native(element_id)` | the live engine primitive for the escape valve ([D53]) |
| `toolbar()` | a native toolbar QWidget for `View(toolbar=True)`, or `None` when interaction is already native ([D95]) |
| `dispose()` | tear down everything you created |

## Events

Translate your engine's gestures into the typed vocabulary — `RangeEvent`,
`PickEvent`, `SelectEvent`, `HoverEvent`, `TapEvent` — and emit them on the
bus. Emit only what your `Capabilities` declare (`picking`, `brush`,
`range_events`). `SelectEvent` carries row **indices + data-space bounds**;
a source without row identity emits `indices=[]` with bounds ([D78]).

## A minimal worked example

A (deliberately tiny) backend that "renders" a Scatter as a live text summary —
useless for plotting, complete for the contract:

```python
import numpy as np
from PySide6.QtWidgets import QLabel

import qtviz.backends
from qtviz import Capabilities, Scatter
from qtviz.core._degrade import check_recommended
from qtviz.core.backend import RendererRegistry, RenderHandle
from qtviz.core.event import EventBus


class TextHandle(RenderHandle):
    def update(self, new_root):
        self.widget.setText(_summary(new_root))


def _summary(el) -> str:
    x = np.asarray(el.data.series("x"))
    return f"Scatter: {len(x)} points, x∈[{x.min():g}, {x.max():g}]"


class TextBackend:
    name = "textual"
    capabilities = Capabilities(
        dimensions=frozenset({2}), opengl=False, picking="none", brush="none",
        range_events=False, streaming=False, max_recommended_points=100_000,
        animation=False, exports=frozenset(),
    )                                             # honest: it does almost nothing

    def __init__(self):
        self.renderers = RendererRegistry()
        self.renderers.register(Scatter, lambda el, ctx: None)

    def supports(self, element_type):
        return self.renderers.get(element_type) is not None

    def honored_options(self, element_type):
        return frozenset()                        # honors nothing → everything warns

    def can_host(self, kind):
        return False

    def render(self, node, *, theme, parent=None):
        check_recommended(node, backend_name=self.name,
                          honored=self.honored_options(type(node)))
        return TextHandle(QLabel(_summary(node), parent), EventBus(), self.name)


qtviz.backends.register(TextBackend())
# qtviz.View(qv.Scatter(df, x="a", y="b"), backend="textual") now works.
```

## Acceptance

Run the suite: the conformance tests parametrize over `list_available()`, so
your backend is exercised the moment it registers — capabilities consistency,
render/dispose per supported element, state round-trips, export files,
honor-or-warn for every recommended option. Green = a real qtviz backend.

Data adapters mirror all of this on the data side
(`qtviz.data.register_data_adapter`; the `DataRef` contracts are documented in
[the stability policy](stability.md)).
