from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CameraConfig:
    device_index: int = 0
    width: int = 960
    height: int = 540
    fps_hint: int = 30


@dataclass(slots=True)
class GestureConfig:
    detection_confidence: float = 0.65
    tracking_confidence: float = 0.65
    pinch_threshold: float = 0.055
    open_palm_threshold: int = 4
    fist_threshold: int = 1
    swipe_distance_threshold: float = 0.18
    scroll_distance_threshold: float = 0.12
    command_cooldown_seconds: float = 0.85
    shutdown_hold_seconds: float = 2.5
    pointer_smoothing: float = 0.35
    dynamic_history_size: int = 8


@dataclass(slots=True)
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    gesture: GestureConfig = field(default_factory=GestureConfig)
    window_title: str = "HandTracker AI Demo"
