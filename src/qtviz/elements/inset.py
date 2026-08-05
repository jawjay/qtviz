"""`Inset` — a child surface floating on a parent surface ([D152]).

The qtviz shape of matplotlib's `ax.inset_axes`: a **structural element**
composed into an overlay like an annotation (`parent * Inset(child,
rect=…)`). The child is a full surface tree (an Element or Overlay with its
own `OverlayOptions`/`AxisSpec`s) placed in **axes-fraction** coordinates of
the parent's plot area. An `Inset` cannot lower — it is a sub-*surface*, not
marks — so each backend renders it natively (`design/inset-axes.md` Part II).

A **labeled** inset is a pane ([D153]): it joins `flat_pane_labels`, so its
zoom window rides `LayoutState` across rebuilds and backend switches,
`view.pane("zoom").set_range(…)` drives it, events from inside it carry
`pane="zoom"`, and `pane.export(…)` writes just the inset. `indicate=True`
draws the parent-side rectangle marking the child's declared x/y window
([D154] — the static v1; both lims must be set on the child's surface).
"""

from __future__ import annotations

from ..core.element import Element
from ..errors import ValidationError


class Inset(Element):
    DATA_KIND = "none"          # data-less at its own level ([D124]) …
    STRUCTURAL_CHILD = "child"  # … but carries a child NODE the pipeline resolves
    HONORED_NATIVE = frozenset({"rect", "label", "indicate"})

    def __init__(self, child, *, rect: tuple[float, float, float, float],
                 label: str | None = None, indicate: bool = False,
                 backend_hint: str | None = None, id: str | None = None) -> None:
        from ..core.compose import Layout, Overlay  # noqa: PLC0415 — avoid a cycle

        super().__init__(backend_hint=backend_hint, id=id)
        if isinstance(child, Layout):
            raise ValidationError(
                "Inset child must be an Element or Overlay (one surface); "
                "for multiple panes use Layout, not an inset")
        if not isinstance(child, (Element, Overlay)):
            raise ValidationError(
                f"Inset child must be an Element or Overlay, got {type(child).__name__}")
        # depth 1: an inset holding an inset is rejected, not rendered badly
        inner = child.children if isinstance(child, Overlay) else (child,)
        if any(isinstance(el, Inset) for el in inner):
            raise ValidationError("insets do not nest (depth 1)")
        r = tuple(float(v) for v in rect)
        if len(r) != 4:
            raise ValidationError(f"rect must be (x0, y0, w, h), got {rect!r}")
        x0, y0, w, h = r
        if w <= 0 or h <= 0:
            raise ValidationError(f"rect width/height must be > 0, got {rect!r}")
        if not (-0.5 <= x0 <= 1.5 and -0.5 <= y0 <= 1.5):
            raise ValidationError(
                f"rect origin is axes-fraction of the parent plot area; "
                f"{(x0, y0)!r} is out of the sane (-0.5..1.5) band")
        if label is not None and not label:
            raise ValidationError("inset label must be a non-empty string")
        self.child = child
        self.rect = r
        self.label = label
        self.indicate = bool(indicate)
        self._freeze()

    def legend_entry(self, theme, index: int = 0):
        return None  # chrome: an inset never contributes to the parent legend
