# Contributing

Issues and pull requests are welcome — qtviz is a small, single-maintainer
library with a deliberately frozen public surface, so **open an issue to
discuss direction before starting a large change**; small fixes and doc
improvements can go straight to a PR.

The full guide lives in the repo:
[CONTRIBUTING.md](https://github.com/jawjay/qtviz/blob/main/CONTRIBUTING.md).
The short version:

```bash
git clone https://github.com/jawjay/qtviz
cd qtviz
uv sync --all-extras            # uv only — never pip into the checkout

uv run pytest -q                # Qt runs offscreen automatically
uv run ruff check src tests examples
uv run mypy src/qtviz           # zero errors is the bar
uv run mkdocs build --strict
```

CI runs ruff, mypy, the offscreen suite (Python 3.11–3.13), and a strict docs
build on every PR.

Three conventions worth knowing before you write code:

- **The API-freeze rule** — any change to the public surface updates
  `tests/qtviz/test_api_freeze.py`, `docs/api.md`, and `CHANGELOG.md` in the
  same commit.
- **Honor-or-warn** — an option a renderer accepts is honored or warns,
  never silently dropped; the conformance suite enforces it.
- **`[Dnn]` decision tags** — non-obvious design choices are recorded in the
  [decision log](https://github.com/jawjay/qtviz/blob/main/design/discussion-items.md)
  and referenced by tag from code, commits, and tests.
