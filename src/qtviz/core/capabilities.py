"""`Capabilities` — a backend's static, behavior-free declaration (spec §2.5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Capabilities:
    dimensions: frozenset[int]
    opengl: bool
    picking: Literal["native", "approximate", "none"]
    brush: Literal["native", "approximate", "none"]
    range_events: bool
    streaming: bool
    max_recommended_points: int
    animation: bool
    exports: frozenset[str]
    threading_model: Literal["gui_only", "render_off_thread"] = "gui_only"
