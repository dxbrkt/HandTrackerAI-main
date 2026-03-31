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

        extended_fingers = self._count_extended_fingers(coords)
        pinch_distance = self._distance(coords[4], coords[8])

        dynamic_prediction = self._classify_dynamic_gesture()
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

        thumb_up = self._is_thumbs_up(coords, extended_fingers)
        if thumb_up:
            return GesturePrediction(
                gesture="thumbs_up",
                confidence=0.84,
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

    def _classify_dynamic_gesture(self) -> GesturePrediction | None:
        if len(self._wrist_history) < self.config.dynamic_history_size:
            return None

        start_x, _ = self._wrist_history[0]
        end_x, _ = self._wrist_history[-1]
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

    def _count_extended_fingers(self, coords: list[tuple[float, float, float]]) -> int:
        count = 0
        for tip_idx, pip_idx in zip(FINGER_TIPS, FINGER_PIPS):
            if coords[tip_idx][1] < coords[pip_idx][1]:
                count += 1

        thumb_tip_x = coords[4][0]
        thumb_ip_x = coords[3][0]
        if abs(thumb_tip_x - thumb_ip_x) > 0.04:
            count += 1
        return count

    def _is_thumbs_up(
        self, coords: list[tuple[float, float, float]], extended_fingers: int
    ) -> bool:
        thumb_tip = coords[4]
        thumb_mcp = coords[2]
        other_fingers_curled = all(
            coords[tip][1] > coords[pip][1] for tip, pip in zip(FINGER_TIPS, FINGER_PIPS)
        )
        return (
            extended_fingers <= 2
            and thumb_tip[1] < thumb_mcp[1] - 0.12
            and other_fingers_curled
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
