from __future__ import annotations

import importlib
import sys
import types
import unittest
from unittest.mock import patch


def load_action_controller_module():
    fake_pyautogui = types.SimpleNamespace(
        FAILSAFE=False,
        PAUSE=0,
        size=lambda: (1920, 1080),
        moveTo=lambda *args, **kwargs: None,
        click=lambda: None,
        press=lambda *args, **kwargs: None,
        hotkey=lambda *args, **kwargs: None,
        scroll=lambda *args, **kwargs: None,
    )
    with patch.dict(sys.modules, {"pyautogui": fake_pyautogui}):
        module = importlib.import_module("handtracker_ai.action_controller")
        return importlib.reload(module)


class ActionControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_action_controller_module()

    def test_adjust_volume_increases_and_clamps(self) -> None:
        controller = self.module.ActionController(volume_step=6)

        with patch.object(self.module.ActionController, "_get_system_volume", return_value=98):
            with patch.object(self.module.subprocess, "run") as run_mock:
                controller._adjust_volume(controller.volume_step)

        run_mock.assert_called_once_with(
            ["osascript", "-e", "set volume output volume 100"],
            check=False,
        )

    def test_adjust_volume_decreases(self) -> None:
        controller = self.module.ActionController(volume_step=6)

        with patch.object(self.module.ActionController, "_get_system_volume", return_value=24):
            with patch.object(self.module.subprocess, "run") as run_mock:
                controller._adjust_volume(-controller.volume_step)

        run_mock.assert_called_once_with(
            ["osascript", "-e", "set volume output volume 18"],
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
