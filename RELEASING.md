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

## 0.1.0 — current state (prepared 2026-06-18)

Everything below the "you run these" line is **done and local — nothing has been
pushed**. On branch `release/0.1.0`:

- ✅ Repo URLs corrected `markjajeh/qtviz` → `jawjay/qtviz` (README, `docs/`,
  `mkdocs.yml`, `pyproject.toml`).
- ✅ `CHANGELOG.md` 0.1.0 dated `2026-06-18`.
- ✅ Annotated tag **`v0.1.0`** created locally, pointing at the release-prep commit.
- ✅ Verified green before tagging: `381 passed, 9 skipped` (webengine needs a
  display; skipped offscreen), benchmarks deselected.
- ✅ `mkdocs build --strict` succeeds.

### ⚠ Tag-placement gotcha

`v0.1.0` currently points at the prep commit **on `release/0.1.0`**, not on `main`.

- If you merge this branch with a **merge commit** (this repo's convention — e.g.
  "Merge pull request …"), the tagged commit stays in history and the tag is valid.
- If you **squash-merge**, the tagged commit will not be on `main`. Re-tag after
  merge:
  ```bash
  git tag -d v0.1.0
  git tag -a v0.1.0 -m "qtviz 0.1.0 — first public pre-release" <main-merge-sha>
  ```

---

## You run these (outward-facing / irreversible)

```bash
# 1. Review the prep + tag
git show v0.1.0
git log --oneline main..release/0.1.0

# 2. Land the branch on main (PR route — matches repo history)
git push origin release/0.1.0
gh pr create --base main --head release/0.1.0 \
  --title "Release prep 0.1.0" --body "URLs + changelog date for the 0.1.0 tag."
# …review & merge the PR (merge commit preferred — see gotcha above)

# 3. Push the tag
git push origin v0.1.0          # if you squash-merged, re-tag first (see gotcha)

# 4. Create the GitHub Release from the tag
gh release create v0.1.0 \
  --title "qtviz 0.1.0" \
  --notes "First public pre-release. See CHANGELOG.md. Alpha: source/git install only (no PyPI)." \
  --prerelease

# 5. Enable GitHub Pages with the Actions source (one-time, maintainer-owned)
#    Web UI: Settings → Pages → Source: GitHub Actions
#    …or via API:
gh api -X POST repos/jawjay/qtviz/pages -f build_type=workflow

# 6. Deploy the docs site (the workflow is manual-trigger only)
gh workflow run docs.yml --ref main
gh run watch   # optional: follow the deploy

# 7. Verify
#    - https://github.com/jawjay/qtviz/releases/tag/v0.1.0
#    - https://jawjay.github.io/qtviz/  (Pages URL; first deploy can take a minute)
```

### Notes
- **Tag name.** Used `v0.1.0` (GitHub convention). If you prefer bare `0.1.0`,
  `git tag -d v0.1.0 && git tag -a 0.1.0 -m "…"` before pushing.
- **`gh` account.** `gh auth status` shows `jawjay` — matches the remote. Good.
- **No PyPI step** — intentional.
