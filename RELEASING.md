# Releasing qtviz

A release is a **git tag** (`vX.Y.Z`) + a **GitHub Release**; pushing the tag
triggers the publish workflow, which builds the sdist/wheel and uploads them
to **PyPI** via trusted publishing (no stored credentials). The docs site
deploys to GitHub Pages from `.github/workflows/docs.yml`.

## Release gates

CI runs ruff, mypy, and the offscreen test suite on every PR and push to
`main`. The **full** gate list below is release-blocking and runs locally
before tagging; all must pass ([D80]/[D81], `docs/stability.md`):

```bash
uv run pytest -q                 # the suite (benchmarks excluded by default)
uv run pytest -m benchmark -q    # the ceilings still hold
uv run ruff check src tests examples
uv run mypy src/qtviz            # zero errors ([D80])
uv run pytest -q --cov           # coverage ≥ the recorded floor ([D81], fail_under)
uv run mkdocs build --strict     # docs build clean
```

Surface changes must have updated `tests/qtviz/test_api_freeze.py`,
`docs/api.md`, and the CHANGELOG in the same commit ([D82]).

## Release steps

1. **Finalize the CHANGELOG** — retitle `## [Unreleased]` to the version with
   today's date; start a fresh empty `[Unreleased]`.
2. **Bump the version** in `pyproject.toml`; `uv lock` if dependencies moved.
3. **Run the full gate list** (above) on a clean `main`.
4. **Tag and push**:
   ```bash
   git tag -a vX.Y.Z -m "qtviz X.Y.Z — <one-line summary>"
   git push origin main vX.Y.Z
   ```
5. **GitHub Release** — create it from the tag with the CHANGELOG excerpt as
   the body. The publish workflow fires on the tag and uploads to PyPI.
6. **Verify**: the PyPI project page renders (README, images, metadata), and
   `pip install qtviz==X.Y.Z` works in a clean venv
   (`python -c "import qtviz; print(qtviz.__version__)"`).

### Manual publish fallback

If the workflow is unavailable:

```bash
uv build
uvx twine check dist/*
uv publish        # needs a PyPI token; trusted publishing is the normal path
```
