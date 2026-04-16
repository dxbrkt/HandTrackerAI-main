from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from .config import GestureConfig
from .models import GesturePrediction


FINGER_TIPS = (8, 12, 16, 20)
FINGER_PIPS = (6, 10, 14, 18)


@dataclass(slots=True)
class GestureEngine:
    config: GestureConfig
    _wrist_history: deque[tuple[float, float]] = field(init=False)
    _two_finger_history: deque[tuple[float, float]] = field(init=False)
    _thumb_history: deque[tuple[float, float]] = field(init=False)
    _smoothed_pointer: tuple[float, float] | None = field(init=False, default=None)
    _pending_static_gesture: str | None = field(init=False, default=None)
    _pending_static_frames: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self._wrist_history = deque(maxlen=self.config.dynamic_history_size)
        self._two_finger_history = deque(maxlen=self.config.scroll_history_size)
        self._thumb_history = deque(maxlen=self.config.thumb_scroll_history_size)
        self._smoothed_pointer = None
        self._pending_static_gesture = None
        self._pending_static_frames = 0

    def classify(self, hand_landmarks) -> GesturePrediction | None:
        if hand_landmarks is None:
            self._wrist_history.clear()
            self._two_finger_history.clear()
            self._thumb_history.clear()
            self._smoothed_pointer = None
            self._reset_pending_static_gesture()
            return None

        coords = [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark]
        wrist_x, wrist_y, _ = coords[0]
        self._wrist_history.append((wrist_x, wrist_y))

        finger_states = self._finger_states(coords)
        if self._is_two_finger_pose(finger_states):
            self._two_finger_history.append(self._two_finger_center(coords))
        else:
            self._two_finger_history.clear()
        if self._is_thumb_scroll_pose(finger_states):
            self._thumb_history.append((coords[4][0], coords[4][1]))
        else:
            self._thumb_history.clear()
        extended_fingers = self._count_extended_fingers(finger_states)
        pinch_distance = self._distance(coords[4], coords[8])

        dynamic_prediction = self._classify_dynamic_gesture(finger_states)
        if dynamic_prediction is not None:
            self._reset_pending_static_gesture()
            return dynamic_prediction

        if pinch_distance < self.config.pinch_threshold:
            static_prediction = GesturePrediction(
                gesture="pinch",
                confidence=self._confidence_from_distance(
                    pinch_distance, self.config.pinch_threshold
                ),
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )
            return self._stabilize_static_prediction(static_prediction)

        if self._is_thumbs_up(coords, extended_fingers, finger_states):
            static_prediction = GesturePrediction(
                gesture="thumbs_up",
                confidence=0.84,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )
            return self._stabilize_static_prediction(static_prediction)

        if self._is_thumbs_down(coords, extended_fingers, finger_states):
            static_prediction = GesturePrediction(
                gesture="thumbs_down",
                confidence=0.84,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )
            return self._stabilize_static_prediction(static_prediction)

        if self._is_middle_finger(finger_states):
            static_prediction = GesturePrediction(
                gesture="middle_finger",
                confidence=0.9,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )
            return self._stabilize_static_prediction(static_prediction)

        if extended_fingers >= self.config.open_palm_threshold:
            self._reset_pending_static_gesture()
            return GesturePrediction(
                gesture="open_palm",
                confidence=0.9,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )

        if extended_fingers <= self.config.fist_threshold and self._is_fist(
            coords, finger_states
        ):
            static_prediction = GesturePrediction(
                gesture="fist",
                confidence=0.82,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )
            return self._stabilize_static_prediction(static_prediction)

        self._reset_pending_static_gesture()
        return GesturePrediction(
            gesture="neutral",
            confidence=0.55,
            is_dynamic=False,
            debug={"extended_fingers": extended_fingers},
        )

    def pointer_target(self, hand_landmarks) -> tuple[float, float] | None:
        if hand_landmarks is None:
            return None

        index_tip = hand_landmarks.landmark[8]
        target = (index_tip.x, index_tip.y)
        if self._smoothed_pointer is None:
            self._smoothed_pointer = target
            return target

        alpha = min(1.0, self.config.pointer_smoothing * self.config.pointer_speed_multiplier)
        delta_x = target[0] - self._smoothed_pointer[0]
        delta_y = target[1] - self._smoothed_pointer[1]
        smooth_x = self._smoothed_pointer[0] + delta_x * alpha
        smooth_y = self._smoothed_pointer[1] + delta_y * alpha
        self._smoothed_pointer = (smooth_x, smooth_y)
        return self._smoothed_pointer

    def _classify_dynamic_gesture(
        self,
        finger_states: dict[str, bool],
    ) -> GesturePrediction | None:
        two_finger_scroll_threshold = self.config.scroll_distance_threshold * 0.42
        thumb_scroll_threshold = self.config.thumb_scroll_distance_threshold

        if (
            self._is_two_finger_pose(finger_states)
            and len(self._two_finger_history) >= self.config.scroll_history_size
        ):
            start_two_x, start_two_y = self._two_finger_history[0]
            end_two_x, end_two_y = self._two_finger_history[-1]
            delta_two_x = end_two_x - start_two_x
            delta_two_y = end_two_y - start_two_y

            if (
                delta_two_y <= -two_finger_scroll_threshold
                and abs(delta_two_y) > abs(delta_two_x) * 1.05
            ):
                self._wrist_history.clear()
                self._two_finger_history.clear()
                return GesturePrediction(
                    gesture="two_fingers_up",
                    confidence=min(0.95, abs(delta_two_y) * 4.0),
                    is_dynamic=True,
                    debug={"delta_y": delta_two_y},
                )
            if (
                delta_two_y >= two_finger_scroll_threshold
                and abs(delta_two_y) > abs(delta_two_x) * 1.05
            ):
                self._wrist_history.clear()
                self._two_finger_history.clear()
                return GesturePrediction(
                    gesture="two_fingers_down",
                    confidence=min(0.95, abs(delta_two_y) * 4.0),
                    is_dynamic=True,
                    debug={"delta_y": delta_two_y},
                )

        if (
            self._is_thumb_scroll_pose(finger_states)
            and len(self._thumb_history) >= self.config.thumb_scroll_history_size
        ):
            start_thumb_x, start_thumb_y = self._thumb_history[0]
            end_thumb_x, end_thumb_y = self._thumb_history[-1]
            delta_thumb_x = end_thumb_x - start_thumb_x
            delta_thumb_y = end_thumb_y - start_thumb_y

            if (
                delta_thumb_y <= -thumb_scroll_threshold
                and abs(delta_thumb_y) > abs(delta_thumb_x) * 1.05
            ):
                self._thumb_history.clear()
                self._wrist_history.clear()
                return GesturePrediction(
                    gesture="thumb_scroll_up",
                    confidence=min(0.95, abs(delta_thumb_y) * 4.5),
                    is_dynamic=True,
                    debug={"delta_y": delta_thumb_y},
                )
            if (
                delta_thumb_y >= thumb_scroll_threshold
                and abs(delta_thumb_y) > abs(delta_thumb_x) * 1.05
            ):
                self._thumb_history.clear()
                self._wrist_history.clear()
                return GesturePrediction(
                    gesture="thumb_scroll_down",
                    confidence=min(0.95, abs(delta_thumb_y) * 4.5),
                    is_dynamic=True,
                    debug={"delta_y": delta_thumb_y},
                )

        if len(self._wrist_history) < self.config.dynamic_history_size:
            return None

        start_x, start_y = self._wrist_history[0]
        end_x, end_y = self._wrist_history[-1]
        delta_x = end_x - start_x

        if delta_x <= -self.config.swipe_distance_threshold:
            self._wrist_history.clear()
            return GesturePrediction(
                gesture="swipe_left",
                confidence=min(0.95, abs(delta_x) * 2.5),
                is_dynamic=True,
                debug={"delta_x": delta_x},
            )
        if delta_x >= self.config.swipe_distance_threshold:
            self._wrist_history.clear()
            return GesturePrediction(
                gesture="swipe_right",
                confidence=min(0.95, abs(delta_x) * 2.5),
                is_dynamic=True,
                debug={"delta_x": delta_x},
            )
        return None

    def _stabilize_static_prediction(
        self, prediction: GesturePrediction
    ) -> GesturePrediction:
        gesture = prediction.gesture
        if gesture == self._pending_static_gesture:
            self._pending_static_frames += 1
        else:
            self._pending_static_gesture = gesture
            self._pending_static_frames = 1

        required_frames = (
            self.config.fist_gesture_frames
            if gesture == "fist"
            else self.config.static_gesture_frames
        )
        if self._pending_static_frames >= required_frames:
            return prediction

        return GesturePrediction(
            gesture="neutral",
            confidence=max(0.2, prediction.confidence * 0.45),
            is_dynamic=False,
            debug={
                **prediction.debug,
                "pending_gesture": gesture,
                "pending_frames": self._pending_static_frames,
                "required_frames": required_frames,
            },
        )

    def _reset_pending_static_gesture(self) -> None:
        self._pending_static_gesture = None
        self._pending_static_frames = 0

    def _finger_states(
        self, coords: list[tuple[float, float, float]]
    ) -> dict[str, bool]:
        palm_scale = self._palm_scale(coords)
        states = {
            "index": self._is_finger_extended(coords, 8, 6, 5, palm_scale),
            "middle": self._is_finger_extended(coords, 12, 10, 9, palm_scale),
            "ring": self._is_finger_extended(coords, 16, 14, 13, palm_scale),
            "pinky": self._is_finger_extended(coords, 20, 18, 17, palm_scale),
        }
        states["thumb"] = self._is_thumb_extended(coords)
        return states

    def _count_extended_fingers(self, finger_states: dict[str, bool]) -> int:
        return sum(1 for is_extended in finger_states.values() if is_extended)

    def _is_thumbs_up(
        self,
        coords: list[tuple[float, float, float]],
        extended_fingers: int,
        finger_states: dict[str, bool],
    ) -> bool:
        thumb_tip = coords[4]
        thumb_mcp = coords[2]
        other_fingers_curled = not any(
            finger_states[name] for name in ("index", "middle", "ring", "pinky")
        )
        return (
            extended_fingers <= 2
            and self._is_thumb_extended(coords)
            and thumb_tip[1] < thumb_mcp[1] - 0.12
            and other_fingers_curled
        )

    def _is_thumbs_down(
        self,
        coords: list[tuple[float, float, float]],
        extended_fingers: int,
        finger_states: dict[str, bool],
    ) -> bool:
        thumb_tip = coords[4]
        thumb_mcp = coords[2]
        other_extended = sum(
            1 for name in ("index", "middle", "ring", "pinky") if finger_states[name]
        )
        thumb_delta_y = thumb_tip[1] - thumb_mcp[1]
        thumb_delta_x = abs(thumb_tip[0] - thumb_mcp[0])
        return (
            extended_fingers <= 3
            and self._is_thumb_extended(coords)
            and other_extended <= 1
            and thumb_delta_y > 0.09
            and thumb_delta_y > thumb_delta_x * 0.85
        )

    @staticmethod
    def _is_thumb_scroll_pose(finger_states: dict[str, bool]) -> bool:
        return (
            finger_states["thumb"]
            and not finger_states["index"]
            and not finger_states["middle"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
        )

    @staticmethod
    def _is_two_finger_pose(finger_states: dict[str, bool]) -> bool:
        noisy_other_fingers = sum(
            1 for name in ("ring", "pinky") if finger_states[name]
        )
        return (
            finger_states["index"]
            and finger_states["middle"]
            and noisy_other_fingers <= 1
        )

    @staticmethod
    def _is_middle_finger(finger_states: dict[str, bool]) -> bool:
        return (
            finger_states["middle"]
            and not finger_states["index"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
            and not finger_states["thumb"]
        )

    @staticmethod
    def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    def _palm_scale(self, coords: list[tuple[float, float, float]]) -> float:
        wrist = coords[0]
        index_mcp = coords[5]
        pinky_mcp = coords[17]
        return max(
            self._distance(wrist, index_mcp),
            self._distance(wrist, pinky_mcp),
            self._distance(index_mcp, pinky_mcp),
            1e-6,
        )

    def _is_finger_extended(
        self,
        coords: list[tuple[float, float, float]],
        tip_idx: int,
        pip_idx: int,
        mcp_idx: int,
        palm_scale: float,
    ) -> bool:
        tip = coords[tip_idx]
        pip = coords[pip_idx]
        mcp = coords[mcp_idx]
        vertical_extension = mcp[1] - tip[1]
        tip_to_mcp = self._distance(tip, mcp)
        pip_to_mcp = self._distance(pip, mcp)
        return (
            tip[1] < pip[1] - palm_scale * 0.02
            and vertical_extension > palm_scale * 0.18
            and tip_to_mcp > pip_to_mcp * 1.05
        )

    def _is_thumb_extended(self, coords: list[tuple[float, float, float]]) -> bool:
        thumb_tip = coords[4]
        thumb_ip = coords[3]
        thumb_mcp = coords[2]
        palm_scale = self._palm_scale(coords)
        thumb_reach = self._distance(thumb_tip, thumb_mcp)
        horizontal_spread = abs(thumb_tip[0] - thumb_ip[0])
        vertical_spread = abs(thumb_tip[1] - thumb_mcp[1])
        return (
            thumb_reach > palm_scale * 0.55
            and (
                horizontal_spread > palm_scale * 0.18
                or vertical_spread > palm_scale * 0.35
            )
        )

    def _is_fist(
        self,
        coords: list[tuple[float, float, float]],
        finger_states: dict[str, bool],
    ) -> bool:
        if any(finger_states[name] for name in ("index", "middle", "ring", "pinky")):
            return False

        palm_scale = self._palm_scale(coords)
        palm_center = (
            (coords[5][0] + coords[17][0]) / 2,
            (coords[0][1] + coords[9][1]) / 2,
            0.0,
        )
        curled_fingers_near_palm = all(
            self._distance(coords[tip_idx], palm_center) < palm_scale * 0.78
            for tip_idx in FINGER_TIPS
        )
        curled_fingers_compact = all(
            coords[tip_idx][1] >= coords[pip_idx][1] - palm_scale * 0.03
            for tip_idx, pip_idx in zip(FINGER_TIPS, FINGER_PIPS)
        )
        thumb_near_palm = self._distance(coords[4], palm_center) < palm_scale * 0.72
        return (
            curled_fingers_near_palm
            and curled_fingers_compact
            and thumb_near_palm
            and not self._is_thumb_extended(coords)
        )

    @staticmethod
    def _confidence_from_distance(distance: float, threshold: float) -> float:
        if threshold <= 0:
            return 0.0
        ratio = max(0.0, min(1.0, 1 - distance / threshold))
        return 0.65 + ratio * 0.3

    @staticmethod
    def _two_finger_center(
        coords: list[tuple[float, float, float]]
    ) -> tuple[float, float]:
        return (
            (coords[8][0] + coords[12][0]) / 2,
            (coords[8][1] + coords[12][1]) / 2,
        )
