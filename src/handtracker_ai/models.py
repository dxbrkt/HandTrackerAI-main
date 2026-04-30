from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GesturePrediction:
    gesture: str
    confidence: float
    state: str = "gesture_confirmed"
    is_dynamic: bool = False
    emit_action: bool = False
    debug: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FrameResult:
    frame_bgr: Any
    prediction: GesturePrediction | None
    latency_ms: float
    hand_landmarks: Any | None = None
