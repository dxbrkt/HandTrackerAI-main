from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field

from .config import GestureConfig
from .hand_features import HandFeatureExtractor, HandFeatures
from .models import GesturePrediction


@dataclass(slots=True)
class GestureEngine:
    config: GestureConfig
    _extractor: HandFeatureExtractor = field(init=False)
    _wrist_history: deque[tuple[float, float, float]] = field(init=False)
    _two_finger_history: deque[tuple[float, float, float]] = field(init=False)
    _thumb_history: deque[tuple[float, float, float]] = field(init=False)
    _smoothed_pointer: tuple[float, float] | None = field(init=False, default=None)
    _state: str = field(init=False, default="idle")
    _candidate_gesture: str | None = field(init=False, default=None)
    _candidate_confidence: float = field(init=False, default=0.0)
    _candidate_is_dynamic: bool = field(init=False, default=False)
    _candidate_frames: int = field(init=False, default=0)
    _confirmed_gesture: str | None = field(init=False, default=None)
    _emitted_gesture: str | None = field(init=False, default=None)
    _last_emit_at: dict[str, float] = field(init=False)
    _latest_features: HandFeatures | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._extractor = HandFeatureExtractor(self.config)
        self._wrist_history = deque(maxlen=self.config.dynamic_history_size)
        self._two_finger_history = deque(maxlen=self.config.scroll_history_size)
        self._thumb_history = deque(maxlen=self.config.thumb_scroll_history_size)
        self._last_emit_at = {}

    def classify(self, hand_landmarks) -> GesturePrediction | None:
        if hand_landmarks is None:
            self._reset_tracking_state(reset_pointer=True)
            return None

        features = self._extractor.extract(hand_landmarks)
        self._latest_features = features
        self._append_motion_history(features)

        candidate = self._select_candidate(features)
        if candidate is None or candidate.confidence < self.config.confidence_threshold:
            return self._to_idle_prediction(features)

        if candidate.gesture != self._candidate_gesture:
            self._candidate_gesture = candidate.gesture
            self._candidate_confidence = candidate.confidence
            self._candidate_is_dynamic = candidate.is_dynamic
            self._candidate_frames = 1
            required_frames = self._required_frames(candidate.gesture)
            if required_frames <= 1:
                self._state = "gesture_confirmed"
                self._confirmed_gesture = candidate.gesture
                emit_action = self._should_emit(candidate.gesture)
                if emit_action:
                    self._emitted_gesture = candidate.gesture
                    self._last_emit_at[candidate.gesture] = time.monotonic()
                return self._prediction_from_candidate(
                    candidate,
                    state="gesture_confirmed",
                    emit_action=emit_action,
                    debug={"stage_frames": self._candidate_frames, **candidate.debug},
                )
            self._state = "gesture_started"
            return self._prediction_from_candidate(
                candidate,
                state="gesture_started",
                emit_action=False,
                debug={"stage_frames": self._candidate_frames, **candidate.debug},
            )

        self._candidate_frames += 1
        self._candidate_confidence = max(self._candidate_confidence, candidate.confidence)
        self._candidate_is_dynamic = candidate.is_dynamic

        required_frames = self._required_frames(candidate.gesture)
        if self._candidate_frames < required_frames:
            self._state = "gesture_started"
            return self._prediction_from_candidate(
                candidate,
                state="gesture_started",
                emit_action=False,
                debug={
                    "stage_frames": self._candidate_frames,
                    "required_frames": required_frames,
                    **candidate.debug,
                },
            )

        self._state = "gesture_confirmed"
        self._confirmed_gesture = candidate.gesture
        emit_action = self._should_emit(candidate.gesture)
        if emit_action:
            self._emitted_gesture = candidate.gesture
            self._last_emit_at[candidate.gesture] = time.monotonic()

        return self._prediction_from_candidate(
            candidate,
            state="gesture_confirmed",
            emit_action=emit_action,
            debug={
                "stage_frames": self._candidate_frames,
                "required_frames": required_frames,
                **candidate.debug,
            },
        )

    def pointer_target(self, hand_landmarks=None) -> tuple[float, float] | None:
        if hand_landmarks is None:
            features = self._latest_features
        else:
            features = self._extractor.extract(hand_landmarks)
            self._latest_features = features

        if features is None:
            return None
        target = features.index_tip[:2]
        if self._smoothed_pointer is None:
            self._smoothed_pointer = target
            return target

        delta_x = target[0] - self._smoothed_pointer[0]
        delta_y = target[1] - self._smoothed_pointer[1]
        movement = math.hypot(delta_x, delta_y)
        if movement < self.config.pointer_deadzone:
            return self._smoothed_pointer

        base_alpha = min(
            0.8,
            self.config.pointer_smoothing * self.config.pointer_speed_multiplier,
        )
        adaptive_boost = min(0.18, movement * 0.45)
        alpha = min(0.88, base_alpha + adaptive_boost)
        smooth_x = self._smoothed_pointer[0] + delta_x * alpha
        smooth_y = self._smoothed_pointer[1] + delta_y * alpha
        self._smoothed_pointer = (smooth_x, smooth_y)
        return self._smoothed_pointer

    def _append_motion_history(self, features: HandFeatures) -> None:
        self._wrist_history.append(
            (features.wrist[0], features.wrist[1], features.palm_scale)
        )
        if self._is_two_finger_pose(features):
            self._two_finger_history.append(
                (
                    features.two_finger_center[0],
                    features.two_finger_center[1],
                    features.palm_scale,
                )
            )
        else:
            self._two_finger_history.clear()

        if self._is_thumb_scroll_pose(features):
            self._thumb_history.append(
                (features.thumb_tip[0], features.thumb_tip[1], features.palm_scale)
            )
        else:
            self._thumb_history.clear()

    def _select_candidate(self, features: HandFeatures) -> GesturePrediction | None:
        dynamic = self._classify_dynamic_gesture(features)
        if dynamic is not None:
            return dynamic

        candidates = [
            self._pinch_candidate(features),
            self._middle_finger_candidate(features),
            self._thumbs_down_candidate(features),
            self._thumbs_up_candidate(features),
            self._fist_candidate(features),
            self._open_palm_candidate(features),
        ]
        valid_candidates = [candidate for candidate in candidates if candidate is not None]
        if not valid_candidates:
            return None
        return max(valid_candidates, key=lambda item: item.confidence)

    def _classify_dynamic_gesture(self, features: HandFeatures) -> GesturePrediction | None:
        if (
            self._is_two_finger_pose(features)
            and len(self._two_finger_history) >= self.config.scroll_history_size
        ):
            delta_x, delta_y = self._normalized_motion(self._two_finger_history)
            if abs(delta_y) > self.config.scroll_distance_threshold and abs(delta_y) > abs(delta_x) * 1.25:
                gesture = "two_fingers_up" if delta_y < 0 else "two_fingers_down"
                return GesturePrediction(
                    gesture=gesture,
                    confidence=min(0.98, 0.72 + abs(delta_y) * 0.18),
                    is_dynamic=True,
                    debug={"normalized_delta_x": delta_x, "normalized_delta_y": delta_y},
                )

        if (
            self._is_thumb_scroll_pose(features)
            and len(self._thumb_history) >= self.config.thumb_scroll_history_size
        ):
            delta_x, delta_y = self._normalized_motion(self._thumb_history)
            if abs(delta_y) > self.config.thumb_scroll_distance_threshold and abs(delta_y) > abs(delta_x) * 1.15:
                gesture = "thumb_scroll_up" if delta_y < 0 else "thumb_scroll_down"
                return GesturePrediction(
                    gesture=gesture,
                    confidence=min(0.98, 0.72 + abs(delta_y) * 0.18),
                    is_dynamic=True,
                    debug={"normalized_delta_x": delta_x, "normalized_delta_y": delta_y},
                )

        if len(self._wrist_history) >= self.config.dynamic_history_size and features.extended_finger_count >= 3:
            delta_x, delta_y = self._normalized_motion(self._wrist_history)
            if abs(delta_x) > self.config.swipe_distance_threshold and abs(delta_x) > abs(delta_y) * 1.2:
                gesture = "swipe_left" if delta_x < 0 else "swipe_right"
                return GesturePrediction(
                    gesture=gesture,
                    confidence=min(0.98, 0.74 + abs(delta_x) * 0.12),
                    is_dynamic=True,
                    debug={"normalized_delta_x": delta_x, "normalized_delta_y": delta_y},
                )
        return None

    def _pinch_candidate(self, features: HandFeatures) -> GesturePrediction | None:
        curled_others = sum(
            1 for name in ("middle", "ring", "pinky") if not features.finger_extended[name]
        )
        if not features.pinch_ready or curled_others < 1:
            return None
        pinch_margin = max(0.0, self.config.pinch_threshold - features.pinch_distance)
        confidence = min(
            0.99,
            0.84 + pinch_margin * 0.8 + curled_others * 0.015,
        )
        return GesturePrediction(
            gesture="pinch",
            confidence=confidence,
            debug={
                "pinch_distance": features.pinch_distance,
                "curled_others": curled_others,
            },
        )

    def _thumbs_up_candidate(self, features: HandFeatures) -> GesturePrediction | None:
        other_extended = sum(
            1 for name in ("index", "middle", "ring", "pinky") if features.finger_extended[name]
        )
        thumb_raise = (features.coords[2][1] - features.thumb_tip[1]) / features.palm_scale
        if (
            features.finger_extended["thumb"]
            and other_extended == 0
            and thumb_raise > 0.42
        ):
            return GesturePrediction(
                gesture="thumbs_up",
                confidence=min(0.97, 0.7 + thumb_raise * 0.22),
                debug={"thumb_raise": thumb_raise},
            )
        return None

    def _thumbs_down_candidate(self, features: HandFeatures) -> GesturePrediction | None:
        other_extended = sum(
            1 for name in ("index", "middle", "ring", "pinky") if features.finger_extended[name]
        )
        thumb_drop = (features.thumb_tip[1] - features.coords[2][1]) / features.palm_scale
        if (
            features.finger_extended["thumb"]
            and other_extended <= 1
            and thumb_drop > 0.34
        ):
            return GesturePrediction(
                gesture="thumbs_down",
                confidence=min(0.97, 0.7 + thumb_drop * 0.2),
                debug={"thumb_drop": thumb_drop},
            )
        return None

    def _middle_finger_candidate(self, features: HandFeatures) -> GesturePrediction | None:
        if (
            features.finger_extended["middle"]
            and not features.finger_extended["index"]
            and not features.finger_extended["ring"]
            and not features.finger_extended["pinky"]
            and not features.finger_extended["thumb"]
        ):
            confidence = min(0.98, 0.82 + features.finger_angles["middle"] * 0.04)
            return GesturePrediction(
                gesture="middle_finger",
                confidence=confidence,
                debug={"middle_angle": features.finger_angles["middle"]},
            )
        return None

    def _open_palm_candidate(self, features: HandFeatures) -> GesturePrediction | None:
        if features.extended_finger_count < self.config.open_palm_threshold:
            return None
        confidence = min(0.97, 0.74 + features.openness * 0.08)
        return GesturePrediction(
            gesture="open_palm",
            confidence=confidence,
            debug={"extended_fingers": features.extended_finger_count},
        )

    def _fist_candidate(self, features: HandFeatures) -> GesturePrediction | None:
        if features.pinch_ready:
            return None
        curled_fingers = sum(
            1 for name in ("index", "middle", "ring", "pinky") if not features.finger_extended[name]
        )
        curled_to_palm = all(
            self._distance(features.coords[idx], features.palm_center) / features.palm_scale < 0.88
            for idx in (8, 12, 16, 20)
        )
        thumb_tucked = not features.finger_extended["thumb"] or (
            self._distance(features.thumb_tip, features.palm_center) / features.palm_scale < 0.92
        )
        if curled_fingers >= 4 and thumb_tucked and curled_to_palm:
            confidence = min(
                0.96,
                0.72 + sum(features.finger_curl[name] for name in ("index", "middle", "ring", "pinky")) * 0.32,
            )
            return GesturePrediction(
                gesture="fist",
                confidence=confidence,
                debug={"curled_fingers": curled_fingers},
            )
        return None

    def _to_idle_prediction(self, features: HandFeatures) -> GesturePrediction:
        self._candidate_gesture = None
        self._candidate_confidence = 0.0
        self._candidate_is_dynamic = False
        self._candidate_frames = 0
        self._confirmed_gesture = None
        self._emitted_gesture = None
        self._state = "idle"
        return GesturePrediction(
            gesture="neutral",
            confidence=max(0.25, features.hand_size_confidence * 0.55),
            state="idle",
            emit_action=False,
            debug=features.debug,
        )

    def _prediction_from_candidate(
        self,
        candidate: GesturePrediction,
        *,
        state: str,
        emit_action: bool,
        debug: dict[str, float],
    ) -> GesturePrediction:
        return GesturePrediction(
            gesture=candidate.gesture,
            confidence=max(candidate.confidence, self._candidate_confidence),
            state=state,
            is_dynamic=candidate.is_dynamic,
            emit_action=emit_action,
            debug=debug,
        )

    def _required_frames(self, gesture: str) -> int:
        if gesture in {"swipe_left", "swipe_right", "two_fingers_up", "two_fingers_down", "thumb_scroll_up", "thumb_scroll_down"}:
            return 1
        if gesture == "pinch":
            return max(self.config.gesture_start_frames, self.config.pinch_gesture_frames)
        if gesture == "fist":
            return max(self.config.gesture_start_frames, self.config.fist_gesture_frames)
        return max(self.config.gesture_start_frames + 1, self.config.static_gesture_frames)

    def _should_emit(self, gesture: str) -> bool:
        if gesture == "open_palm":
            return True
        if self._emitted_gesture == gesture:
            return False
        last_emit_at = self._last_emit_at.get(gesture, 0.0)
        return (time.monotonic() - last_emit_at) >= self.config.gesture_repeat_cooldown_seconds

    @staticmethod
    def _normalized_motion(history: deque[tuple[float, float, float]]) -> tuple[float, float]:
        start_x, start_y, _ = history[0]
        end_x, end_y, _ = history[-1]
        avg_scale = max(1e-6, sum(item[2] for item in history) / len(history))
        return (end_x - start_x) / avg_scale, (end_y - start_y) / avg_scale

    @staticmethod
    def _is_two_finger_pose(features: HandFeatures) -> bool:
        noisy_other_fingers = sum(
            1 for name in ("ring", "pinky") if features.finger_extended[name]
        )
        return (
            features.finger_extended["index"]
            and features.finger_extended["middle"]
            and noisy_other_fingers <= 1
        )

    @staticmethod
    def _is_thumb_scroll_pose(features: HandFeatures) -> bool:
        thumb_travel = abs(features.thumb_tip[1] - features.coords[2][1]) / features.palm_scale
        return (
            (features.finger_extended["thumb"] or thumb_travel > 0.28)
            and not features.finger_extended["index"]
            and not features.finger_extended["middle"]
            and not features.finger_extended["ring"]
            and not features.finger_extended["pinky"]
        )

    @staticmethod
    def _distance(a, b) -> float:
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    def _reset_tracking_state(self, *, reset_pointer: bool) -> None:
        self._extractor.reset()
        self._wrist_history.clear()
        self._two_finger_history.clear()
        self._thumb_history.clear()
        self._candidate_gesture = None
        self._candidate_confidence = 0.0
        self._candidate_is_dynamic = False
        self._candidate_frames = 0
        self._confirmed_gesture = None
        self._emitted_gesture = None
        self._state = "idle"
        self._latest_features = None
        if reset_pointer:
            self._smoothed_pointer = None
