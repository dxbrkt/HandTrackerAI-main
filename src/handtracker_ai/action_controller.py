from __future__ import annotations

import time
from dataclasses import dataclass, field

import pyautogui


pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


@dataclass(slots=True)
class ActionController:
    cooldown_seconds: float = 0.85
    _last_trigger_at: dict[str, float] = field(init=False)
    _screen_width: int = field(init=False)
    _screen_height: int = field(init=False)

    def __post_init__(self) -> None:
        self._last_trigger_at = {}
        self._screen_width, self._screen_height = pyautogui.size()

    def move_pointer(self, normalized_x: float, normalized_y: float) -> None:
        target_x = int(max(0.0, min(1.0, normalized_x)) * self._screen_width)
        target_y = int(max(0.0, min(1.0, normalized_y)) * self._screen_height)
        pyautogui.moveTo(target_x, target_y, duration=0)

    def trigger(self, gesture: str) -> bool:
        now = time.monotonic()
        last_trigger = self._last_trigger_at.get(gesture, 0.0)
        if now - last_trigger < self.cooldown_seconds:
            return False

        action_map = {
            "pinch": lambda: pyautogui.click(),
            "fist": lambda: pyautogui.press("space"),
            "swipe_left": lambda: pyautogui.hotkey("ctrl", "left"),
            "swipe_right": lambda: pyautogui.hotkey("ctrl", "right"),
            "thumbs_up": lambda: pyautogui.press("volumeup"),
        }
        action = action_map.get(gesture)
        if action is None:
            return False

        action()
        self._last_trigger_at[gesture] = now
        return True
