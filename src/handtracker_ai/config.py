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
    confidence_threshold: float = 0.68
    landmark_smoothing: float = 0.38
    pinch_threshold: float = 0.22
    open_palm_threshold: int = 4
    fist_threshold: int = 1
    static_gesture_frames: int = 3
    gesture_start_frames: int = 2
    pinch_gesture_frames: int = 1
    scroll_repeat_cooldown_seconds: float = 0.15
    fist_gesture_frames: int = 2
    swipe_distance_threshold: float = 0.95
    scroll_distance_threshold: float = 0.20
    scroll_history_size: int = 3
    thumb_scroll_distance_threshold: float = 0.20
    thumb_scroll_history_size: int = 3
    gesture_repeat_cooldown_seconds: float = 0.55
    command_cooldown_seconds: float = 0.85
    shutdown_hold_seconds: float = 2.5
    pointer_smoothing: float = 0.18
    pointer_speed_multiplier: float = 1.35
    pointer_deadzone: float = 0.012
    dynamic_history_size: int = 8


@dataclass(slots=True)
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    gesture: GestureConfig = field(default_factory=GestureConfig)
    window_title: str = "HandTracker AI Demo"
