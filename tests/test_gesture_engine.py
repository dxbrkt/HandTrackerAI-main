from __future__ import annotations

import unittest

from handtracker_ai.config import GestureConfig
from handtracker_ai.gesture_engine import GestureEngine


def make_coords() -> list[tuple[float, float, float]]:
    coords = [(0.5, 0.7, 0.0)] * 21
    coords[0] = (0.5, 0.7, 0.0)
    coords[2] = (0.44, 0.58, 0.0)
    coords[3] = (0.43, 0.50, 0.0)
    coords[4] = (0.42, 0.42, 0.0)
    coords[5] = (0.52, 0.56, 0.0)
    coords[6] = (0.52, 0.48, 0.0)
    coords[8] = (0.52, 0.62, 0.0)
    coords[9] = (0.56, 0.56, 0.0)
    coords[10] = (0.56, 0.48, 0.0)
    coords[12] = (0.56, 0.62, 0.0)
    coords[13] = (0.60, 0.58, 0.0)
    coords[14] = (0.60, 0.52, 0.0)
    coords[16] = (0.60, 0.66, 0.0)
    coords[17] = (0.65, 0.58, 0.0)
    coords[18] = (0.65, 0.53, 0.0)
    coords[20] = (0.65, 0.68, 0.0)
    return coords


class Landmark:
    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.z = z


class HandLandmarks:
    def __init__(self, coords: list[tuple[float, float, float]]) -> None:
        self.landmark = [Landmark(*coord) for coord in coords]


class GestureEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = GestureEngine(GestureConfig(dynamic_history_size=3))

    def classify_repeated(
        self, coords: list[tuple[float, float, float]], frames: int
    ):
        prediction = None
        for _ in range(frames):
            prediction = self.engine.classify(HandLandmarks(coords))
        return prediction

    def test_thumbs_up_is_not_classified_as_fist(self) -> None:
        prediction = self.classify_repeated(make_coords(), 3)

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "thumbs_up")

    def test_thumbs_down_is_not_classified_as_fist(self) -> None:
        coords = make_coords()
        coords[3] = (0.43, 0.66, 0.0)
        coords[4] = (0.42, 0.78, 0.0)

        prediction = self.classify_repeated(coords, 3)

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "thumbs_down")

    def test_thumbs_down_allows_one_noisy_extended_finger(self) -> None:
        coords = make_coords()
        coords[3] = (0.43, 0.64, 0.0)
        coords[4] = (0.42, 0.69, 0.0)
        coords[8] = (0.52, 0.45, 0.0)

        prediction = self.classify_repeated(coords, 3)

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "thumbs_down")

    def test_static_gesture_needs_stable_frames(self) -> None:
        coords = make_coords()
        coords[3] = (0.43, 0.66, 0.0)
        coords[4] = (0.42, 0.78, 0.0)

        first_prediction = self.engine.classify(HandLandmarks(coords))
        second_prediction = self.engine.classify(HandLandmarks(coords))
        third_prediction = self.engine.classify(HandLandmarks(coords))

        self.assertIsNotNone(first_prediction)
        self.assertIsNotNone(second_prediction)
        self.assertIsNotNone(third_prediction)
        self.assertEqual(first_prediction.gesture, "neutral")
        self.assertEqual(second_prediction.gesture, "neutral")
        self.assertEqual(third_prediction.gesture, "thumbs_down")

    def test_two_fingers_pose_allows_visible_thumb(self) -> None:
        coords = make_coords()
        coords[8] = (0.52, 0.34, 0.0)
        coords[12] = (0.56, 0.33, 0.0)

        for tip_y in (0.44, 0.37, 0.30):
            coords[8] = (0.52, tip_y, 0.0)
            coords[12] = (0.56, tip_y - 0.01, 0.0)
            prediction = self.engine.classify(HandLandmarks(coords))

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "two_fingers_up")

    def test_two_fingers_down_uses_shorter_motion_threshold(self) -> None:
        coords = make_coords()
        coords[8] = (0.52, 0.34, 0.0)
        coords[12] = (0.56, 0.33, 0.0)

        for tip_y in (0.34, 0.39, 0.43):
            coords[8] = (0.52, tip_y, 0.0)
            coords[12] = (0.56, tip_y - 0.01, 0.0)
            prediction = self.engine.classify(HandLandmarks(coords))

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "two_fingers_down")

    def test_two_fingers_scroll_works_with_one_noisy_extra_finger(self) -> None:
        engine = GestureEngine(
            GestureConfig(dynamic_history_size=3, scroll_history_size=4)
        )
        coords = make_coords()
        coords[8] = (0.52, 0.34, 0.0)
        coords[12] = (0.56, 0.33, 0.0)
        coords[16] = (0.60, 0.45, 0.0)

        prediction = None
        for tip_y in (0.34, 0.37, 0.40, 0.43):
            coords[8] = (0.52, tip_y, 0.0)
            coords[12] = (0.56, tip_y - 0.01, 0.0)
            prediction = engine.classify(HandLandmarks(coords))

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "two_fingers_down")

    def test_two_fingers_scroll_uses_shorter_history_than_swipe(self) -> None:
        engine = GestureEngine(
            GestureConfig(dynamic_history_size=8, scroll_history_size=4)
        )
        coords = make_coords()
        coords[8] = (0.52, 0.34, 0.0)
        coords[12] = (0.56, 0.33, 0.0)

        prediction = None
        for tip_y in (0.34, 0.37, 0.40, 0.43):
            coords[8] = (0.52, tip_y, 0.0)
            coords[12] = (0.56, tip_y - 0.01, 0.0)
            prediction = engine.classify(HandLandmarks(coords))

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "two_fingers_down")

    def test_thumb_scroll_down_works_with_thumbs_down_pose(self) -> None:
        engine = GestureEngine(
            GestureConfig(
                dynamic_history_size=8,
                thumb_scroll_history_size=3,
                thumb_scroll_distance_threshold=0.05,
            )
        )
        coords = make_coords()
        coords[3] = (0.43, 0.66, 0.0)
        coords[4] = (0.42, 0.72, 0.0)

        prediction = None
        for tip_y in (0.72, 0.77, 0.82):
            coords[4] = (0.42, tip_y, 0.0)
            prediction = engine.classify(HandLandmarks(coords))

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "thumb_scroll_down")

    def test_thumb_scroll_up_works_with_thumbs_up_pose(self) -> None:
        engine = GestureEngine(
            GestureConfig(
                dynamic_history_size=8,
                thumb_scroll_history_size=3,
                thumb_scroll_distance_threshold=0.05,
            )
        )
        coords = make_coords()
        coords[3] = (0.43, 0.49, 0.0)

        prediction = None
        for tip_y in (0.47, 0.40, 0.33):
            coords[4] = (0.42, tip_y, 0.0)
            prediction = engine.classify(HandLandmarks(coords))

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "thumb_scroll_up")

    def test_real_fist_still_detects_as_fist(self) -> None:
        coords = make_coords()
        coords[8] = (0.56, 0.64, 0.0)
        coords[3] = (0.47, 0.61, 0.0)
        coords[4] = (0.50, 0.62, 0.0)

        prediction = self.classify_repeated(coords, 4)

        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.gesture, "fist")

    def test_pointer_speed_multiplier_moves_cursor_faster(self) -> None:
        slow_engine = GestureEngine(
            GestureConfig(dynamic_history_size=3, pointer_smoothing=0.35, pointer_speed_multiplier=1.0)
        )
        fast_engine = GestureEngine(
            GestureConfig(dynamic_history_size=3, pointer_smoothing=0.35, pointer_speed_multiplier=1.75)
        )
        start_coords = make_coords()
        end_coords = make_coords()
        end_coords[8] = (0.82, 0.20, 0.0)

        slow_engine.pointer_target(HandLandmarks(start_coords))
        fast_engine.pointer_target(HandLandmarks(start_coords))
        slow_target = slow_engine.pointer_target(HandLandmarks(end_coords))
        fast_target = fast_engine.pointer_target(HandLandmarks(end_coords))

        self.assertIsNotNone(slow_target)
        self.assertIsNotNone(fast_target)
        assert slow_target is not None
        assert fast_target is not None
        self.assertGreater(fast_target[0], slow_target[0])
        self.assertLess(fast_target[1], slow_target[1])


if __name__ == "__main__":
    unittest.main()
