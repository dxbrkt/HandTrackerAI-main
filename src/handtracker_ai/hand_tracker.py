from __future__ import annotations

import time
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import drawing_utils as mp_drawing

from .config import AppConfig
from .gesture_engine import GestureEngine
from .models import FrameResult

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
_MODEL_PATH = Path.home() / ".cache" / "handtracker_ai" / "hand_landmarker.task"


_MIN_MODEL_BYTES = 5_000_000


def _ensure_model() -> Path:
    if _MODEL_PATH.exists() and _MODEL_PATH.stat().st_size < _MIN_MODEL_BYTES:
        _MODEL_PATH.unlink()
    if not _MODEL_PATH.exists():
        _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading hand landmarker model to {_MODEL_PATH} ...")
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print("Download complete.")
    return _MODEL_PATH


class _LandmarkList:
    """Adapter: wraps a Tasks API landmark list so hand_features.py can use .landmark."""
    __slots__ = ("landmark",)

    def __init__(self, landmarks) -> None:
        self.landmark = landmarks


class HandTracker:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        model_path = _ensure_model()

        base_options = mp_python.BaseOptions(model_asset_path=str(model_path))
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=config.gesture.detection_confidence,
            min_hand_presence_confidence=config.gesture.detection_confidence,
            min_tracking_confidence=config.gesture.tracking_confidence,
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(options)
        self._connections = mp_vision.HandLandmarksConnections.HAND_CONNECTIONS
        self._engine = GestureEngine(config.gesture)
        self._camera = cv2.VideoCapture(config.camera.device_index)
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.width)
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.height)
        self._camera.set(cv2.CAP_PROP_FPS, config.camera.fps_hint)
        self._start_ns = time.time_ns()

    def _timestamp_ms(self) -> int:
        return (time.time_ns() - self._start_ns) // 1_000_000

    def read(self, track_enabled: bool = True) -> FrameResult | None:
        started_at = time.perf_counter()
        ok, frame = self._camera.read()
        if not ok:
            return None

        frame = cv2.flip(frame, 1)
        if not track_enabled:
            self._engine.classify(None)
            return FrameResult(
                frame_bgr=frame,
                prediction=None,
                latency_ms=(time.perf_counter() - started_at) * 1000,
                hand_landmarks=None,
            )

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self._landmarker.detect_for_video(mp_image, self._timestamp_ms())

        prediction = None
        hand_landmarks = None
        if result.hand_landmarks:
            raw_landmarks = result.hand_landmarks[0]
            hand_landmarks = _LandmarkList(raw_landmarks)
            mp_drawing.draw_landmarks(frame, raw_landmarks, self._connections)
            prediction = self._engine.classify(hand_landmarks)
        else:
            self._engine.classify(None)

        return FrameResult(
            frame_bgr=frame,
            prediction=prediction,
            latency_ms=(time.perf_counter() - started_at) * 1000,
            hand_landmarks=hand_landmarks,
        )

    def pointer_target(self, frame_result: FrameResult):
        if frame_result.hand_landmarks is None:
            return None
        return self._engine.pointer_target()

    def close(self) -> None:
        self._camera.release()
        self._landmarker.close()
