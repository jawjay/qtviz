"""Tier-1 — the [D129] channel-vocabulary guard.

The channel rule is one sentence: data comes first; every data binding is a
keyword accessor from a fixed 10-role vocabulary (`x y z u v value by lo hi
err`), plus the two sanctioned value→visual encodings (`color_by`,
`size_by`, [D139]). The freeze test pins *which names* are public and the
docs-sync test pins *where they're documented*; nothing pinned the
vocabulary itself — a new element could quietly invent an 11th role. This
makes that a test failure.
"""

from __future__ import annotations

import inspect

import pytest

qv = pytest.importorskip("qtviz")

pytestmark = pytest.mark.tier1

ROLES = {"x", "y", "z", "u", "v", "value", "by", "lo", "hi", "err"}
ENCODINGS = {"color_by", "size_by"}  # [D139]: value→color/size encodings

# Documented exemptions — bindings that are deliberately NOT roles. ErrorBars'
# limit flags are boolean "the true value lies beyond" masks (matplotlib's
# lolims/uplims semantic), not interval edges: renaming them to the `lo`/`hi`
# roles would collide with Spread's edge meaning. Bars' `annotate` is the one
# [D131] mark-annotation keyword; its [D136] accessor arm binds label text
# through that same keyword rather than inventing an 11th role for it.
# Anything added here needs the same kind of justification.
EXEMPT = {"ErrorBars": {"lo_limit", "hi_limit"}, "Bars": {"annotate"}}

ELEMENT_TYPES = sorted(
    (getattr(qv, name) for name in qv.__all__
     if isinstance(getattr(qv, name, None), type)
     and issubclass(getattr(qv, name), qv.Element)
     and getattr(qv, name) is not qv.Element),
    key=lambda t: t.__name__,
)


def test_all_30_elements_are_covered():
    assert len(ELEMENT_TYPES) == 30  # 28 + Inset ([D152]) + PolarGrid ([D119])


@pytest.mark.parametrize("et", ELEMENT_TYPES, ids=lambda t: t.__name__)
def test_declared_channels_use_the_role_vocabulary(et):
    channels = set(getattr(et, "CHANNELS", ()))
    assert channels <= ROLES, (
        f"{et.__name__}.CHANNELS declares roles outside the [D129] vocabulary: "
        f"{sorted(channels - ROLES)}"
    )


@pytest.mark.parametrize("et", ELEMENT_TYPES, ids=lambda t: t.__name__)
def test_accessor_parameters_use_the_role_vocabulary(et):
    """Every constructor parameter annotated as an `Accessor` (a data binding)
    must be one of the ten roles or a sanctioned encoding — annotation
    geometry (floats), style, and `extent` placement are not data bindings
    and are exempt by construction."""
    sig = inspect.signature(et.__init__)
    bound = {
        name for name, p in sig.parameters.items()
        if isinstance(p.annotation, str) and "Accessor" in p.annotation
    }
    off_vocabulary = bound - ROLES - ENCODINGS - EXEMPT.get(et.__name__, set())
    assert not off_vocabulary, (
        f"{et.__name__} binds data through parameters outside the [D129] "
        f"vocabulary: {sorted(off_vocabulary)}"
    )
