from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field

import pyautogui


pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


@dataclass(slots=True)
class ActionController:
    cooldown_seconds: float = 0.85
    shutdown_hold_seconds: float = 2.5
    _last_trigger_at: dict[str, float] = field(init=False)
    _screen_width: int = field(init=False)
    _screen_height: int = field(init=False)
    _pending_shutdown_since: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._last_trigger_at = {}
        self._screen_width, self._screen_height = pyautogui.size()
        self._pending_shutdown_since = None

    def move_pointer(self, normalized_x: float, normalized_y: float) -> None:
        target_x = int(max(0.0, min(1.0, normalized_x)) * self._screen_width)
        target_y = int(max(0.0, min(1.0, normalized_y)) * self._screen_height)
        pyautogui.moveTo(target_x, target_y, duration=0)

    def reset_pending(self) -> None:
        self._pending_shutdown_since = None

    def trigger(self, gesture: str) -> bool:
        now = time.monotonic()

        if gesture == "middle_finger":
            if self._pending_shutdown_since is None:
                self._pending_shutdown_since = now
                return False
            if now - self._pending_shutdown_since < self.shutdown_hold_seconds:
                return False

            self._shutdown_mac()
            self._pending_shutdown_since = None
            self._last_trigger_at[gesture] = now
            return True

        self._pending_shutdown_since = None
        last_trigger = self._last_trigger_at.get(gesture, 0.0)
        if now - last_trigger < self.cooldown_seconds:
            return False

        action_map = {
            "pinch": lambda: pyautogui.click(),
            "fist": lambda: pyautogui.press("space"),
            "swipe_left": lambda: pyautogui.hotkey("ctrl", "left"),
            "swipe_right": lambda: pyautogui.hotkey("ctrl", "right"),
            "thumbs_up": lambda: pyautogui.press("volumeup"),
            "thumbs_down": lambda: pyautogui.press("volumedown"),
            "two_fingers_up": lambda: pyautogui.scroll(500),
            "two_fingers_down": lambda: pyautogui.scroll(-500),
        }
        action = action_map.get(gesture)
        if action is None:
            return False

        action()
        self._last_trigger_at[gesture] = now
        return True

    @staticmethod
    def _shutdown_mac() -> None:
        subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to shut down'],
            check=False,
        )
