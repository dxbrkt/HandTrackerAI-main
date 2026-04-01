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
    _smoothed_pointer: tuple[float, float] | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._wrist_history = deque(maxlen=self.config.dynamic_history_size)
        self._smoothed_pointer = None

    def classify(self, hand_landmarks) -> GesturePrediction | None:
        if hand_landmarks is None:
            self._wrist_history.clear()
            self._smoothed_pointer = None
            return None

        coords = [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark]
        wrist_x, wrist_y, _ = coords[0]
        self._wrist_history.append((wrist_x, wrist_y))

        finger_states = self._finger_states(coords)
        extended_fingers = self._count_extended_fingers(finger_states)
        pinch_distance = self._distance(coords[4], coords[8])

        dynamic_prediction = self._classify_dynamic_gesture(finger_states)
        if dynamic_prediction is not None:
            return dynamic_prediction

        if pinch_distance < self.config.pinch_threshold:
            return GesturePrediction(
                gesture="pinch",
                confidence=self._confidence_from_distance(
                    pinch_distance, self.config.pinch_threshold
                ),
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )

        if self._is_thumbs_up(coords, extended_fingers, finger_states):
            return GesturePrediction(
                gesture="thumbs_up",
                confidence=0.84,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )

        if self._is_thumbs_down(coords, extended_fingers, finger_states):
            return GesturePrediction(
                gesture="thumbs_down",
                confidence=0.84,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )

        if self._is_middle_finger(finger_states):
            return GesturePrediction(
                gesture="middle_finger",
                confidence=0.9,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )

        if extended_fingers >= self.config.open_palm_threshold:
            return GesturePrediction(
                gesture="open_palm",
                confidence=0.9,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )

        if extended_fingers <= self.config.fist_threshold:
            return GesturePrediction(
                gesture="fist",
                confidence=0.82,
                is_dynamic=False,
                debug={"extended_fingers": extended_fingers},
            )

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

        alpha = self.config.pointer_smoothing
        smooth_x = self._smoothed_pointer[0] * (1 - alpha) + target[0] * alpha
        smooth_y = self._smoothed_pointer[1] * (1 - alpha) + target[1] * alpha
        self._smoothed_pointer = (smooth_x, smooth_y)
        return self._smoothed_pointer

    def _classify_dynamic_gesture(
        self,
        finger_states: dict[str, bool],
    ) -> GesturePrediction | None:
        if len(self._wrist_history) < self.config.dynamic_history_size:
            return None

        start_x, start_y = self._wrist_history[0]
        end_x, end_y = self._wrist_history[-1]
        delta_x = end_x - start_x
        delta_y = end_y - start_y

        if self._is_two_finger_pose(finger_states):
            if delta_y <= -self.config.scroll_distance_threshold:
                self._wrist_history.clear()
                return GesturePrediction(
                    gesture="two_fingers_up",
                    confidence=min(0.95, abs(delta_y) * 3.0),
                    is_dynamic=True,
                    debug={"delta_y": delta_y},
                )
            if delta_y >= self.config.scroll_distance_threshold:
                self._wrist_history.clear()
                return GesturePrediction(
                    gesture="two_fingers_down",
                    confidence=min(0.95, abs(delta_y) * 3.0),
                    is_dynamic=True,
                    debug={"delta_y": delta_y},
                )

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

    def _finger_states(
        self, coords: list[tuple[float, float, float]]
    ) -> dict[str, bool]:
        states = {
            "index": coords[8][1] < coords[6][1],
            "middle": coords[12][1] < coords[10][1],
            "ring": coords[16][1] < coords[14][1],
            "pinky": coords[20][1] < coords[18][1],
        }
        states["thumb"] = abs(coords[4][0] - coords[3][0]) > 0.04
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
            and finger_states["thumb"]
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
        other_fingers_curled = not any(
            finger_states[name] for name in ("index", "middle", "ring", "pinky")
        )
        return (
            extended_fingers <= 2
            and finger_states["thumb"]
            and thumb_tip[1] > thumb_mcp[1] + 0.12
            and other_fingers_curled
        )

    @staticmethod
    def _is_two_finger_pose(finger_states: dict[str, bool]) -> bool:
        return (
            finger_states["index"]
            and finger_states["middle"]
            and not finger_states["ring"]
            and not finger_states["pinky"]
            and not finger_states["thumb"]
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

    @staticmethod
    def _confidence_from_distance(distance: float, threshold: float) -> float:
        if threshold <= 0:
            return 0.0
        ratio = max(0.0, min(1.0, 1 - distance / threshold))
        return 0.65 + ratio * 0.3
