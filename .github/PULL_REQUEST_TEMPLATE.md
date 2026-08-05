## What & why

<!-- What does this change, and what problem does it solve? Link the issue if one exists. -->

## Checklist

- [ ] Gates run locally: `uv run pytest -q`, `ruff check src tests examples`, `mypy src/qtviz`
- [ ] Tests added/updated (new elements/features need conformance coverage, not one-backend tests)
- [ ] If the public surface changed: `tests/qtviz/test_api_freeze.py` + `docs/api.md` + `CHANGELOG.md` updated **in this PR**
- [ ] Non-obvious design decisions recorded with a `[Dnn]` tag where applicable
