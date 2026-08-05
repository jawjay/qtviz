# Releasing qtviz

qtviz is **not published to PyPI** (by design — see `design/project_no_pypi`/roadmap),
and the repo is **private permanently** (owner decision, 2026-07-24), so there is no
Pages deploy either. A release is: a **git tag** + a **GitHub Release**; docs are
built/read locally (`uv run mkdocs serve`).
Install is `pip install git+<repo>` (for repo collaborators) or from source.

## Release gates (1.0+, run locally — CI was removed deliberately)

Every release runs these; all must pass ([D80]/[D81], `docs/stability.md`):

```bash
uv run pytest -q                 # the suite (benchmarks excluded by default)
uv run pytest -m benchmark -q    # the ceilings still hold
uv run ruff check src tests examples
uv run mypy src/qtviz            # zero errors ([D80])
uv run pytest -q --cov           # coverage ≥ the recorded floor ([D81], fail_under)
uv run mkdocs build --strict     # docs build clean
```

Surface changes must have updated `tests/qtviz/test_api_freeze.py` + the
CHANGELOG in the same commit ([D82]).

---

## 2.0.0 — current state (prepared 2026-08-04)

Everything is **done and local on `main`** — version bumped, docs rewritten,
gates green; **the tag has not been created**. The owner runs:

```bash
git tag -a v2.0.0 -m "qtviz 2.0.0 — the Mark IR + uniform surface"
git push origin main v2.0.0
```

- ✅ `pyproject.toml` at `2.0.0`; `CHANGELOG.md` 2.0.0 dated `2026-08-04`
  (full rename + behavior-change tables).
- ✅ `docs/stability.md` rewritten for the `FROZEN_2_0` surface (70 names);
  deprecation ledger cleared with the one-time-break note.
- ✅ Design record: `design/2.0-mark-ir-and-surface.md` §8 reconciles the
  proposal against what shipped ([D121]–[D136]).
- ✅ Verified green before hand-off: `887 passed, 11 skipped` (webengine needs
  a display; skipped offscreen), benchmarks pass, mypy zero, ruff clean,
  `mkdocs build --strict` succeeds.

### Historical: 0.1.0 (prepared 2026-06-18)

The 0.1.0 prep notes (tag-placement gotcha included) are preserved in git
history; `v0.1.0` was created on `release/0.1.0`.
