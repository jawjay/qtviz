"""Tier-1 — docs drift guard (improvement-plan [D65]).

`docs/api.md` is mkdocstrings-driven: a name renders only if it is listed as a
`members:` entry. Nothing ties those lists to `qtviz.__all__`, so a new export
can silently miss the docs (it happened to `AxisSpec` in 0.3 increment 1). This
makes the drift a test failure instead: every public name must appear in
`docs/api.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

qv = pytest.importorskip("qtviz")

pytestmark = pytest.mark.tier1

_API_MD = Path(__file__).resolve().parents[2] / "docs" / "api.md"


def test_every_public_name_is_documented():
    import types

    text = _API_MD.read_text()
    missing = [
        name for name in qv.__all__
        if not name.startswith("__")                          # __version__ lives in prose
        and not isinstance(getattr(qv, name, None), types.ModuleType)  # submodule namespaces
        and f"- {name}\n" not in text
    ]
    assert not missing, (
        f"public names missing from docs/api.md members lists: {missing} — "
        f"add each to the appropriate section (docs drift guard, [D65])"
    )
