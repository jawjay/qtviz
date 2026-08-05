# Contributing to qtviz

Thanks for your interest! qtviz is a small, single-maintainer library with a
deliberately frozen public surface — **please open an issue to discuss
direction before starting a large change**; small fixes and doc improvements
can go straight to a PR.

## Development setup

The environment is **uv only** (never pip into the checkout); Python ≥ 3.11.

```bash
git clone https://github.com/jawjay/qtviz
cd qtviz
uv sync --all-extras          # everything: dev, docs, matplotlib, webengine, dask, xarray, datashader
# minimum for the test suite:
uv sync --extra dev --extra matplotlib
```

## Quality gates

CI runs ruff, mypy, and the offscreen test suite on every PR. The full gate
list (what a release must pass) is:

```bash
uv run pytest -q                 # the suite (benchmarks excluded by default)
uv run ruff check src tests examples
uv run mypy src/qtviz            # zero errors is the bar
uv run pytest -q --cov           # coverage floor enforced via fail_under
uv run mkdocs build --strict     # docs must build clean
uv run pytest -m benchmark -q    # performance ceilings (opt-in)
```

Qt runs headless automatically — `tests/conftest.py` sets
`QT_QPA_PLATFORM=offscreen`, so GUI tests need no display. Some webengine
tests self-skip offscreen (a `QWebEngineView` needs a real display).

## Tests

Markers: `tier1` (pure core, no QApplication), `tier2` (Qt event loop +
backend), `conformance` (the contract suite every backend/adapter must pass),
`benchmark`, `gui`.

- A new element or feature generally needs **conformance coverage** (the
  parametrized cross-backend suites), not just one-backend tests.
- A new *tail* element needs a `lower()` + an entry in the perturbation-guard
  fixtures (`tests/qtviz/test_marks.py`) — one core lowering, zero backend
  edits — not three renderers.
- The honesty rule: an option is honored or warns, **never silently
  dropped** — the conformance suite enforces this, so wire new options all
  the way through or don't accept them.

## Conventions

- **Decisions get `[Dnn]` tags.** Non-obvious design choices are recorded in
  the decision log (`design/discussion-items.md`, or the design doc for the
  current arc) and referenced from code, commits, and tests by tag.
- **Commits** follow the existing style: `feat(scope): [Dnn] short summary`.
- **The API-freeze rule**: any change to the public surface updates
  `tests/qtviz/test_api_freeze.py`, `docs/api.md`, and `CHANGELOG.md` in the
  same commit (`test_docs_sync.py` enforces the docs half).
- **100% offline rendering is a hard requirement** — no network at render
  time, ever; the webengine backend bundles JS from installed packages, never
  a CDN.
- Ruff line length is 100; keep comment density and naming in the style of
  the surrounding code.

## Docs & screenshots

```bash
uv run mkdocs serve                              # local docs
uv run python tools/capture_screenshots.py       # regenerate docs/images/examples/*.png (needs a display)
```

Examples follow a convention: each exposes `build()` (returns the widget —
testable) and `main()` (shows a window), and is covered by
`tests/qtviz/test_examples.py`.
