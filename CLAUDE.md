# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**qtviz** — declarative, native-Qt plotting for PySide6 apps. A plot is described once as immutable data (`Element`), then rendered through any of three backends: **pyqtgraph** (fast/native, the default), **matplotlib** (publication/vector), or **webengine** (Plotly/Bokeh in a QWebEngineView). Same element, identical result, swappable at runtime.

The canonical design document is `design/spec.md`; the 2.0 architecture (the Mark IR + uniform surface) is `design/2.0-mark-ir-and-surface.md`. Decisions are numbered `[Dnn]` (currently through [D136]) and recorded in `design/discussion-items.md` and the milestone docs; code comments, commits, and tests reference them by tag — keep doing that.

## Commands

Environment is **uv only — never pip** (`uv sync`, `uv add`, `uv run`). Dev setup:

```bash
uv sync --all-extras                            # everything (dev, docs, matplotlib, webengine, dask, xarray, datashader)
uv sync --extra dev --extra matplotlib          # minimum for the test suite (docs build needs --extra docs)
```

```bash
uv run pytest -q                                # full suite (benchmarks excluded by default)
uv run pytest tests/qtviz/test_elements.py -q   # one file
uv run pytest -k "test_name" -q                 # one test
uv run pytest -m benchmark -q                   # performance ceilings (opt-in)
uv run ruff check src tests examples
uv run mypy src/qtviz                           # zero errors is the release gate [D80]
uv run pytest -q --cov                          # coverage floor enforced via fail_under
uv run mkdocs build --strict                    # docs must build clean
uv run python tools/capture_screenshots.py      # regenerate docs/images/examples/*.png
```

CI runs ruff, mypy, and the offscreen suite on every PR and push to `main`; the **full** gate list (including benchmarks and coverage) is release-blocking and runs locally (see `RELEASING.md`). Qt runs headless automatically: `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen`, so GUI tests need no display (some webengine tests skip offscreen).

Test markers: `tier1` (pure core, no QApplication), `tier2` (Qt event loop + backend), `conformance` (contract suite every backend/adapter must pass), `benchmark`, `gui`.

## Architecture

Layering (strict, one-directional — core never imports a concrete backend):

- **`src/qtviz/core/`** — the spec's abstractions: `Element` (immutable, value-hashed, Qt-free declarative data), the **Mark IR** ([D121]/[D122]: `marks.py` — 9 typed drawing primitives in linear data space; `lowering.py` — `Element.lower(ctx) -> Lowered`), `Backend` protocol + `RenderContext`/`RenderHandle`/`ViewState` (`core/backend.py`), composition via operators (`a * b` → `Overlay`, `a + b` → `Layout`, in `compose.py`) with `.opts()` surface sugar ([D133]), `View` + `show()` (`core/view.py`), `Theme`/`Palette`/`Color`/`Norm`, typed events on an `EventBus`, `Capabilities` and backend negotiation, threading discipline.
- **`src/qtviz/elements/`** — the 28 element classes. Pure data constructors; a **tail of 14 lowers** (Quiver, Streamlines, Stem, Spread, Ecdf + the 9 annotations: one `lower()` in core, zero backend edits) and **14 stay native** (Scatter, Curve, Bars, Histogram, Area, BoxPlot, Violin, Image, Heatmap, Mesh, Contour, ErrorBars, Pie, RawFigure — engine idioms a lowering would visibly change; rationale in the 2.0 doc §8).
- **`src/qtviz/data/`** — container-agnostic data layer. `DataRef` (tabular vs gridded), a priority-ordered adapter registry (dict/NumPy/pandas/Arrow eager; dask/xarray/zarr lazy), channel **accessors** (column name, serializable `Expression` via `col()`/`lit()`, callable, or raw array — **every channel keyword takes the full union, never just column names**), streaming sources, viewport regridding. `resolve_node` dispatches on `Element.DATA_KIND`; big-data side-channels ride the typed `_aux` slot (`RasterAux`/`GridAux`, [D124]).
- **`src/qtviz/backends/{pyqtgraph,matplotlib,webengine}/`** — each implements the `Backend` protocol and registers through the **`qtviz.backends` entry-point group** ([D125]; a third-party backend needs zero qtviz edits). Each has a `_marks.py` adapter (~8 drawers, written once) for lowered elements — the pyqtgraph adapter is the one place its log pretransform lives — plus native renderers for the head elements; **a registered native renderer wins over lowering** (the fast-path override). Each maps `ViewState` to/from native ranges so pan/zoom/selection survive backend switches. The webengine backend hosts a Qt↔JS bridge (`core/`) with library extensions (`ext/`); `_runtime.py` files there are JavaScript embedded as Python strings (ruff E501 ignored, excluded from coverage).
- **`src/qtviz/adapter/`** (holoviews/hvplot ingestion) and **`src/qtviz/ext/`** (datashader: large data → screen-resolution rasters that re-aggregate on zoom).

Cross-cutting rules worth knowing before editing:

- **The channel vocabulary is one rule** ([D129]): data first; bindings are keyword accessors from a fixed 10-role set (`x y z u v value by lo hi err`); grids pass arrays as `data`, placed by `extent=` or coordinate vectors. `raster=` is the rasterization strategy; `scale` means only axis transform; `norm=`/`clim=` are the one colormap spec ([D130], `qv.Norm`); `annotate=` is the one mark-annotation keyword ([D131]); `label=` is only ever the legend string.
- **Honesty is declared once and proven** ([D51]/[D123]): each element carries `HONORED_NATIVE` (backends subtract small declared deltas) or `HONORED_BY_LOWERING` (proven by the tier-1 perturbation guard in `tests/qtviz/test_marks.py`: an option is honored iff perturbing it changes the `Lowered`). Never silently drop a parameter — that was the project's top diagnosed weakness.
- **Threading**: data resolution happens off the GUI thread; widget mutation is GUI-thread-only and enforced.
- **100% offline is a hard requirement**: no network at render time, ever. The webengine backend bundles JS from the installed `plotly`/`bokeh` packages — never a CDN.
- **API freeze ([D82]/[D135])**: the 2.0 public surface (70 names, `FROZEN_2_0`) is frozen (`docs/stability.md`). Any surface change must update `tests/qtviz/test_api_freeze.py`, `docs/api.md`, **and** `CHANGELOG.md` in the same commit.
- Tests live in `tests/qtviz/` (the acceptance suite targeting `import qtviz`); `tests/qtviz/backends/` and the conformance tests parametrize contracts across all backends — new elements/features generally need conformance coverage, not just one-backend tests. A new tail element needs a `lower()` + a guard-fixture entry, not three renderers.

## Conventions

- Commit messages follow the existing style — `feat(2.0): [D122] short description` — with no attribution trailers.
- Ruff line length 100; `select = ["E", "F", "I", "UP", "B", "SIM"]`.
- Published to PyPI; a release is a git tag + GitHub Release, with the tag triggering the PyPI publish workflow (`RELEASING.md`).
- Workflow cadence for new work: spec → plan → discussion items → benchmarks → TDD; discuss direction at milestone/scope boundaries (an issue works well) before implementing.
