"""HandTracker AI SDK and demo application."""

__all__ = ["GestureControlApp"]


def __getattr__(name: str):
    if name == "GestureControlApp":
        from .app import GestureControlApp

        return GestureControlApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
