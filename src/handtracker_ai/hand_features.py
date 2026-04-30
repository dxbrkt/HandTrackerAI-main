from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import GestureConfig


THUMB_TIP = 4
INDEX_TIP = 8
MIDDLE_TIP = 12
RING_TIP = 16
PINKY_TIP = 20

THUMB_IP = 3
INDEX_PIP = 6
MIDDLE_PIP = 10
RING_PIP = 14
PINKY_PIP = 18

INDEX_MCP = 5
MIDDLE_MCP = 9
RING_MCP = 13
PINKY_MCP = 17

FINGER_NAME_TO_JOINTS = {
    "thumb": (2, THUMB_IP, THUMB_TIP),
    "index": (INDEX_MCP, INDEX_PIP, INDEX_TIP),
    "middle": (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP),
    "ring": (RING_MCP, RING_PIP, RING_TIP),
    "pinky": (PINKY_MCP, PINKY_PIP, PINKY_TIP),
}


Point3D = tuple[float, float, float]


@dataclass(slots=True)
class HandFeatures:
    coords: list[Point3D]
    palm_scale: float
    palm_center: Point3D
    wrist: Point3D
    finger_extended: dict[str, bool]
    finger_curl: dict[str, float]
    finger_angles: dict[str, float]
    pinch_distance: float
    pinch_ready: bool
    thumb_tip: Point3D
    index_tip: Point3D
    middle_tip: Point3D
    two_finger_center: tuple[float, float]
    extended_finger_count: int
    openness: float
    hand_size_confidence: float
    debug: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class HandFeatureExtractor:
    config: GestureConfig
    _smoothed_coords: list[Point3D] | None = field(init=False, default=None)

    def reset(self) -> None:
        self._smoothed_coords = None

    def extract(self, hand_landmarks) -> HandFeatures:
        raw_coords = [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark]
        coords = self._smooth_coords(raw_coords)
        palm_scale = self._palm_scale(coords)
        palm_center = self._palm_center(coords)
        finger_angles = {
            name: self._joint_angle(coords[a], coords[b], coords[c])
            for name, (a, b, c) in FINGER_NAME_TO_JOINTS.items()
        }
        finger_curl = self._finger_curl_scores(coords, palm_scale, palm_center)
        finger_extended = {
            "thumb": self._is_thumb_extended(coords, palm_scale, finger_angles["thumb"]),
            "index": self._is_finger_extended(
                coords, INDEX_TIP, INDEX_PIP, INDEX_MCP, palm_center, palm_scale, finger_angles["index"]
            ),
            "middle": self._is_finger_extended(
                coords, MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP, palm_center, palm_scale, finger_angles["middle"]
            ),
            "ring": self._is_finger_extended(
                coords, RING_TIP, RING_PIP, RING_MCP, palm_center, palm_scale, finger_angles["ring"]
            ),
            "pinky": self._is_finger_extended(
                coords, PINKY_TIP, PINKY_PIP, PINKY_MCP, palm_center, palm_scale, finger_angles["pinky"]
            ),
        }
        extended_finger_count = sum(1 for is_extended in finger_extended.values() if is_extended)
        pinch_distance = self._distance(coords[THUMB_TIP], coords[INDEX_TIP]) / palm_scale
        openness = self._distance(coords[INDEX_TIP], palm_center) / palm_scale
        hand_size_confidence = min(1.0, palm_scale / 0.12)

        return HandFeatures(
            coords=coords,
            palm_scale=palm_scale,
            palm_center=palm_center,
            wrist=coords[0],
            finger_extended=finger_extended,
            finger_curl=finger_curl,
            finger_angles=finger_angles,
            pinch_distance=pinch_distance,
            pinch_ready=pinch_distance <= self.config.pinch_threshold,
            thumb_tip=coords[THUMB_TIP],
            index_tip=coords[INDEX_TIP],
            middle_tip=coords[MIDDLE_TIP],
            two_finger_center=(
                (coords[INDEX_TIP][0] + coords[MIDDLE_TIP][0]) / 2,
                (coords[INDEX_TIP][1] + coords[MIDDLE_TIP][1]) / 2,
            ),
            extended_finger_count=extended_finger_count,
            openness=openness,
            hand_size_confidence=hand_size_confidence,
            debug={
                "pinch_distance": pinch_distance,
                "palm_scale": palm_scale,
                "openness": openness,
            },
        )

    def _smooth_coords(self, coords: list[Point3D]) -> list[Point3D]:
        if self._smoothed_coords is None:
            self._smoothed_coords = list(coords)
            return list(coords)

        alpha = min(0.95, max(0.05, self.config.landmark_smoothing))
        smoothed: list[Point3D] = []
        for previous, current in zip(self._smoothed_coords, coords):
            smoothed.append(
                (
                    previous[0] + (current[0] - previous[0]) * alpha,
                    previous[1] + (current[1] - previous[1]) * alpha,
                    previous[2] + (current[2] - previous[2]) * alpha,
                )
            )
        self._smoothed_coords = smoothed
        return smoothed

    @staticmethod
    def _distance(a: Point3D, b: Point3D) -> float:
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    def _palm_scale(self, coords: list[Point3D]) -> float:
        return max(
            self._distance(coords[0], coords[INDEX_MCP]),
            self._distance(coords[0], coords[PINKY_MCP]),
            self._distance(coords[INDEX_MCP], coords[PINKY_MCP]),
            1e-6,
        )

    @staticmethod
    def _palm_center(coords: list[Point3D]) -> Point3D:
        anchor_points = (0, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)
        return (
            sum(coords[idx][0] for idx in anchor_points) / len(anchor_points),
            sum(coords[idx][1] for idx in anchor_points) / len(anchor_points),
            sum(coords[idx][2] for idx in anchor_points) / len(anchor_points),
        )

    @staticmethod
    def _joint_angle(a: Point3D, b: Point3D, c: Point3D) -> float:
        ab = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
        cb = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
        ab_len = math.sqrt(sum(v * v for v in ab))
        cb_len = math.sqrt(sum(v * v for v in cb))
        if ab_len == 0 or cb_len == 0:
            return 0.0
        dot = sum(x * y for x, y in zip(ab, cb)) / (ab_len * cb_len)
        dot = max(-1.0, min(1.0, dot))
        return math.acos(dot)

    def _finger_curl_scores(
        self,
        coords: list[Point3D],
        palm_scale: float,
        palm_center: Point3D,
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        for name, (_, pip_idx, tip_idx) in FINGER_NAME_TO_JOINTS.items():
            tip_distance = self._distance(coords[tip_idx], palm_center) / palm_scale
            pip_distance = self._distance(coords[pip_idx], palm_center) / palm_scale
            scores[name] = max(0.0, pip_distance - tip_distance)
        return scores

    def _is_finger_extended(
        self,
        coords: list[Point3D],
        tip_idx: int,
        pip_idx: int,
        mcp_idx: int,
        palm_center: Point3D,
        palm_scale: float,
        angle: float,
    ) -> bool:
        tip_reach = self._distance(coords[tip_idx], palm_center) / palm_scale
        pip_reach = self._distance(coords[pip_idx], palm_center) / palm_scale
        mcp_reach = self._distance(coords[mcp_idx], palm_center) / palm_scale
        extension_gain = tip_reach - pip_reach
        finger_span = self._distance(coords[tip_idx], coords[mcp_idx]) / palm_scale
        return (
            angle >= 2.35
            and extension_gain > 0.12
            and tip_reach > mcp_reach + 0.18
            and finger_span > 0.55
        )

    def _is_thumb_extended(
        self,
        coords: list[Point3D],
        palm_scale: float,
        angle: float,
    ) -> bool:
        thumb_tip = coords[THUMB_TIP]
        thumb_ip = coords[THUMB_IP]
        thumb_mcp = coords[2]
        thumb_span = self._distance(thumb_tip, thumb_mcp) / palm_scale
        thumb_spread = self._distance(thumb_tip, coords[INDEX_MCP]) / palm_scale
        thumb_ip_span = self._distance(thumb_tip, thumb_ip) / palm_scale
        return (
            angle >= 2.0
            and thumb_span > 0.46
            and thumb_spread > 0.42
            and thumb_ip_span > 0.16
        )
