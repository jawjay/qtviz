"""qtviz reactive layer — S-style signals (spec §9; D38–D40)."""

from __future__ import annotations

from .signal import Signal, batch, derived, effect, signal

__all__ = ["Signal", "signal", "derived", "effect", "batch"]
