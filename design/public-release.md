# Public release — the pre-publication amendment wave ([D137]–[D144])

**Status:** in progress (2026-08-05). The repo goes public and qtviz publishes to
PyPI — reversing [D64] (private permanently) and the no-PyPI stance — with one
final pre-publication API amendment wave. Decisions below follow the house
format; each lands in the commit of the wave that implements it.

## [D137] Pre-publication amendment charter

**Context.** The 2.0 surface froze (`FROZEN_2_0`, [D135]) while the repo was
private with zero external users. Going public + PyPI is the last moment
breaking fixes are free: after first publish, every rename needs the
[deprecation policy](../docs/stability.md).

**Decision.** One bounded amendment wave (A–G) before the repo goes public.
Breaking changes are allowed *in this wave only*; the deprecation path is
explicitly waived (there is no one to deprecate for). The freeze test, docs,
and CHANGELOG move in lockstep per wave. After the wave, the frozen surface is
final and the stability policy applies with full force.

**Deferred out of the wave.** `Contour` gets no `norm=`/`clim=` yet: honoring
them means re-mapping level→color across three native renderers (an mpl norm
object, a re-baked Plotly colorscale, a re-indexed pyqtgraph LUT), and the
honesty rule ([D51]) forbids shipping the keywords un-honored. Scatter's
norm/clim landed (wave C); Contour's is a post-release follow-up.

**Status.** ✅ in progress — waves land as `fix(release)`/`feat(release)` commits.

## [D138] Orientation vocabulary — `orient=` spelled out; `direction` stays

**Context.** `Bars(orient="v"|"h")` and `Span(orient=...)` used single-letter
values in a library that otherwise spells values out (`"grouped"`,
`"triangle_down"`); `ErrorBars(direction="y"|"x"|"both")` looked like a second
name for the same idea.

**Decision.** `orient: Literal["vertical", "horizontal"]` is mark orientation
(Bars, Span). `direction` is a different concept — which axis carries error,
including `"both"` — and stays on ErrorBars unchanged. The Mark IR keeps its
internal `"v"/"h"` encoding; elements map at construction.

**Status.** ✅ wave C.

## [D139] `by=` vs `color_by=` — codify, don't rename

**Context.** `by` appears on Bars/Area/BoxPlot/Violin/Pie, `color_by` on
Scatter/Curve (and Bars, which has both); users couldn't predict which.

**Decision.** The split is semantic, not accidental — **`by=` groups rows into
series** (palette-cycled, one legend entry per category); **`color_by=` encodes
a value per point into color** (continuous or categorical mapping). Bars
legitimately takes both (group into bars; color the bars by a value). No
rename; the rule is documented in `docs/stability.md` and enforced by the
[D129] vocabulary test.

The wave-G vocabulary guard (`tests/qtviz/test_channel_vocabulary.py`) also
records the one deliberate exemption: `ErrorBars(lo_limit=, hi_limit=)` are
boolean beyond-the-limit masks (matplotlib's lolims/uplims), not the
`lo`/`hi` interval-edge roles — renaming them would collide with Spread's
meaning.

**Status.** ✅ wave C/D (docs); test in wave G.

## [D140] Top-level surface amendment (70 → 71 names)

**Context.** `Element` (the library's central noun) and `QtvizError` (the one
broad handler) were unimportable from `qtviz`; `Capabilities` and
`set_backend_priority` — backend-author contracts — sat in the end-user list;
`show(node=)` disagreed with `View(root=)`.

**Decision.** Add `Element`, `QtvizError`, `Node` (the `Element|Overlay|Layout`
alias) to `qtviz.*`. Move `Capabilities` and `set_backend_priority` to
`qtviz.backends` (the [D125] extension namespace). Rename `show(node)` →
`show(root)`. Submodule-export rule: a submodule is in `__all__` iff it carries
public API not re-exported at top level.

**Status.** ✅ wave D.

## [D141] QApplication safety — `View` construction can never abort

**Context.** `qv.show(qv.View(...))` hard-aborted (Qt `qFatal`, no traceback)
when no QApplication existed; the hello-world was forced to pass a builder
callable to `show()`.

**Decision.** `View.__init__` ensures a QApplication exists (creating and
holding one if needed) before any widget construction. The builder-callable
form of `show()` remains supported but is no longer required.

**Status.** ✅ wave E.

## [D142] `[Dnn]` markers move out of public docstring summaries

**Context.** 35 of the 70 public names carried decision tags in their
docstrings — 76 occurrences rendered on the public API page (e.g. `Norm`
opening "[D130] the one colormap-normalization spec…").

**Decision.** Public docstrings speak to users; decision tags live in code
comments, tests, commits, and `design/`. Strip `[Dnn]` from docstring summary
lines; where the design context matters in-code, keep it as a `#` comment.

**Status.** ✅ wave F.

## [D143] Colors — full CSS4 named set, eager validation, close-match hints

**Context.** `color=` accepted only 16 names, was validated lazily (a bad name
surfaced at render, far from the call), and the error didn't say what *is*
accepted. Everyone coming from matplotlib types `"steelblue"`.

**Decision.** Vendor the full CSS4/X11 named-color table (~148 names, hex —
the set CSS, SVG, and matplotlib agree on) into `core/color.py`. Validate
static `color=` eagerly in every element constructor (`check_color`). Unknown
names raise `ValidationError` with `difflib` close matches and the accepted
forms. All color/palette rejections join the `ValidationError` taxonomy.

**Status.** ✅ wave B.

## [D144] Lazy backend loading — entry points load on first use

**Context.** `import qtviz` took ~0.48 s and imported PySide6, pyqtgraph, *and*
matplotlib (an optional extra) because `_autoregister()` eagerly `ep.load()`ed
every entry point. Elements are "Qt-free pure data" in the docs, but the
package couldn't be imported without Qt.

**Decision.** `_autoregister()` records entry points unloaded; a materialize
step loads them on first registry access (`get()`, listing, negotiation,
`set_default_backend`). Import-failure behavior (INFO + install hint) is
preserved. Full Qt-free `import qtviz` (View still imports PySide6 at module
load) is recorded as a follow-up, not part of this wave.

**Status.** ✅ wave G.
