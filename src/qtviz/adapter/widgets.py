"""Optional Qt helpers for the HoloViews adapter (stage 3b, [D44] Level 1).

Kept separate from the pure `holoviews.py` so the translation core stays Qt-free
and Tier-1 testable. `kdim_panel` is a *turnkey* convenience: a `View` of a
`DynamicMap` plus one control per kdim, wired so changing a control re-renders the
plot. The composable primitive is `from_holoviews_dmap` — apps that want their own
UI drive its kdim `Signal`s directly and never touch this module.
"""

from __future__ import annotations

from typing import Any

_SLIDER_STEPS = 100


def kdim_panel(dm: Any, *, backend: str = "auto", theme: Any = None):
    """Build a `QWidget`: a `View` of `dm` above one control per kdim.

    Discrete kdims (with `.values`) get a combo box; continuous kdims (numeric
    `.range`) get a slider. Each control writes the chosen value into the kdim's
    `Signal`, which re-resolves and re-renders the View (debounced)."""
    from PySide6.QtCore import Qt  # noqa: PLC0415 — lazy, Qt only when used
    from PySide6.QtWidgets import (  # noqa: PLC0415
        QComboBox,
        QFormLayout,
        QSlider,
        QVBoxLayout,
        QWidget,
    )

    from ..core.view import View  # noqa: PLC0415
    from .holoviews import from_holoviews_dmap  # noqa: PLC0415

    binding = from_holoviews_dmap(dm)

    container = QWidget()
    outer = QVBoxLayout(container)
    outer.addWidget(View(binding.node, backend=backend, theme=theme))

    controls = QWidget()
    form = QFormLayout(controls)
    for kdim in dm.kdims:
        sig = binding.kdims[kdim.name]
        if kdim.values:
            combo = QComboBox()
            for v in kdim.values:
                combo.addItem(str(v), v)
            combo.currentIndexChanged.connect(
                lambda _i, c=combo, s=sig: s.set(c.currentData())
            )
            form.addRow(kdim.name, combo)
        else:
            lo, hi = kdim.range
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, _SLIDER_STEPS)
            slider.valueChanged.connect(
                lambda v, s=sig, lo=lo, hi=hi: s.set(lo + (hi - lo) * v / _SLIDER_STEPS)
            )
            slider.setValue(_SLIDER_STEPS // 2)  # midpoint — matches the seeded default
            form.addRow(kdim.name, slider)
    outer.addWidget(controls)
    return container
