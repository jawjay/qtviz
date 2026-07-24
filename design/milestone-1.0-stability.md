# Milestone — 1.0 "Stability" (the promise release; improvement-plan [D66])

> 1.0 ships no features. It ships a **promise**: the surface you hold in your
> head stays put. Freeze + policy + the quality gates that keep the promise
> checkable. Decisions **[D79]–[D82]**.

## 0. Goal & scope

**Goal.** `import qtviz` is a stable contract: a documented public surface, a
documented deprecation policy, tooling that fails when either drifts, and docs
that cover the whole 0.3–0.6 arc — including the extension story.

**In scope.**
- **[D79] Removals & promise-keeping:** the `qtwebplot` shim goes (promised
  "two releases", overdue); `qtviz.Options` **stays** — 0.2 promised "kept
  importable through 1.0", so it warns through 1.0 and is removed in 1.1
  (the improvement-plan's "remove both" is corrected: the written promise wins).
- **Stability policy** (`docs/stability.md`): what is public (`qtviz.__all__`
  + the documented Backend/DataRef contracts), what is not (underscore
  modules, `handle.native()` returns, backend internals), semver rules, and
  the deprecation path (warn ≥2 minor releases → remove).
- **[D82] API freeze guard:** a tier-1 test pinning `qtviz.__all__` exactly —
  additions and removals both fail the suite until the frozen list (and the
  CHANGELOG) are deliberately updated.
- **[D80] Type checking:** mypy over `src/qtviz` (pragmatic config: 3.11,
  `ignore_missing_imports`; no strict mode), **local-blocking** via the
  release runbook — the owner deliberately deleted `ci.yml` (June 2026) and
  it stays deleted; gates live in `uv run` commands, not Actions.
- **[D81] Coverage gate:** pytest-cov config in pyproject; the runbook gate is
  `uv run pytest --cov` ≥ the measured floor (set just under actual, so it
  only catches regressions).
- **Docs completeness:** the "writing a backend" tutorial (the extensibility
  story finally documented: Backend protocol, registry, honor-or-warn tables,
  conformance suite); README rewritten to the 1.0 reality (the current one
  still says "built in phases toward 0.1"); mkdocs nav updated.
- **Release prep:** CHANGELOG — the four unreleased sections (0.3–0.6) were
  never tagged, so they fold into one `[1.0.0]` entry as subsections; version
  → `1.0.0`; classifier → Production/Stable. Tag + push stay the
  maintainer's, per the house release flow.

**Non-goals.** New features of any kind; resurrecting CI; publishing anywhere
(private forever, [D64]); Studio (post-1.0 exploration, unchanged).

## 1. Discussion items (recommended; confirm at review)

### [D79] Shim out, Options stays
`qtwebplot` was promised for two releases past the rename (0.1); five have
passed. `Options` was promised "through 1.0" — removing it *at* 1.0 breaks the
letter of a written deprecation promise in the very release whose point is
promise-keeping. It stays, warns, and 1.1 removes it (recorded in
`docs/stability.md`).

### [D80] mypy, pragmatic, local
Strict mypy over a Qt/numpy/pyqtgraph codebase is a milestone of its own;
1.0 takes the honest middle: default mypy with missing-import tolerance,
zero errors as the gate, tightening later at will. Local because the owner
removed Actions deliberately — a gate nobody runs in the written workflow is
theater; RELEASING.md makes it a release step.

### [D81] Coverage floor just under actual
The gate exists to catch *regressions*, not to chase a number. Measure, set
the floor ~2 points under, record it.

### [D82] Freeze = a failing test, not a doc sentence
`test_api_freeze.py` pins `qtviz.__all__` exactly. Deliberate additions edit
the frozen list + CHANGELOG in the same commit — the same honesty mechanism
as the conformance and docs-drift guards.

## 2. Phased increments (review at each boundary)
1. **Removals + policy + freeze guard** — shim deletion (package, pyproject,
   tests, README migration section), `docs/stability.md`, `test_api_freeze.py`.
2. **Quality gates** — mypy config + zero errors; pytest-cov config + measured
   floor; RELEASING.md gains the gate steps.
3. **Docs** — `docs/backends.md` tutorial; README rewrite; mkdocs nav.
4. **Release prep** — CHANGELOG fold to `[1.0.0]`, version bump, classifier;
   final suite/gates green. Tag + push: maintainer.

## 3. Acceptance
`import qtwebplot` raises `ModuleNotFoundError`; `qtviz.Options` still warns;
`test_api_freeze` pins the exact public surface; `uv run mypy src/qtviz` exits
0; `uv run pytest --cov` meets the recorded floor; the docs site builds strict
with the backend tutorial in nav; README describes 1.0, not "toward 0.1";
CHANGELOG has one dated `[1.0.0]`; `pyproject.version == "1.0.0"`. Suite
green; ruff clean.
