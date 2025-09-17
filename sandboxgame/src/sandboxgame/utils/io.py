"""Input helpers for the sandbox PyOpenGL application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set

try:  # pragma: no cover - import guarded for test environments
    import glfw  # type: ignore
except Exception:  # pragma: no cover - gracefully handle missing glfw
    glfw = None  # type: ignore

from ..core import Vector3


@dataclass
class KeyboardState:
    pressed: Set[int] = field(default_factory=set)

    def press(self, key: int) -> None:
        self.pressed.add(key)

    def release(self, key: int) -> None:
        self.pressed.discard(key)

    def is_pressed(self, key: int) -> bool:
        return key in self.pressed


@dataclass
class MouseState:
    left_button: bool = False
    right_button: bool = False
    last_x: float = 0.0
    last_y: float = 0.0
    delta_x: float = 0.0
    delta_y: float = 0.0

    def set_position(self, x: float, y: float) -> None:
        self.delta_x = x - self.last_x
        self.delta_y = y - self.last_y
        self.last_x = x
        self.last_y = y


class InputManager:
    """Manage keyboard/mouse state and expose gameplay-friendly helpers."""

    def __init__(self) -> None:
        self.keyboard = KeyboardState()
        self.mouse = MouseState()
        self.window: Optional["glfw._GLFWwindow"] = None  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # GLFW integration

    def attach(self, window: "glfw._GLFWwindow") -> None:  # type: ignore[name-defined]
        if glfw is None:
            raise RuntimeError("GLFW is not available; cannot attach input manager.")
        self.window = window
        glfw.set_key_callback(window, self._on_key)
        glfw.set_cursor_pos_callback(window, self._on_cursor)
        glfw.set_mouse_button_callback(window, self._on_mouse_button)

    def poll(self) -> None:
        if glfw is not None and self.window is not None:
            glfw.poll_events()

    # ------------------------------------------------------------------
    # Callbacks

    def _on_key(self, _window, key, _scancode, action, _mods) -> None:
        if glfw is None:
            return
        if action == glfw.PRESS:
            self.keyboard.press(key)
        elif action == glfw.RELEASE:
            self.keyboard.release(key)

    def _on_cursor(self, _window, xpos: float, ypos: float) -> None:
        self.mouse.set_position(xpos, ypos)

    def _on_mouse_button(self, _window, button, action, _mods) -> None:
        if glfw is None:
            return
        if button == glfw.MOUSE_BUTTON_LEFT:
            self.mouse.left_button = action == glfw.PRESS
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            self.mouse.right_button = action == glfw.PRESS

    # ------------------------------------------------------------------
    # High level helpers used by the renderer

    def movement_vector(self) -> Vector3:
        if glfw is None:
            return Vector3(0.0, 0.0, 0.0)

        x = 0.0
        z = 0.0
        if self.keyboard.is_pressed(glfw.KEY_W):
            z -= 1.0
        if self.keyboard.is_pressed(glfw.KEY_S):
            z += 1.0
        if self.keyboard.is_pressed(glfw.KEY_A):
            x -= 1.0
        if self.keyboard.is_pressed(glfw.KEY_D):
            x += 1.0
        return Vector3(x, 0.0, z)

    def look_vector(self) -> Vector3:
        # Convert relative mouse movement into a direction vector on the XZ plane.
        if abs(self.mouse.delta_x) < 1e-5 and abs(self.mouse.delta_y) < 1e-5:
            return Vector3(0.0, 0.0, -1.0)
        return Vector3(self.mouse.delta_x, 0.0, -self.mouse.delta_y).normalized()

    def wants_to_fire(self) -> bool:
        return self.mouse.left_button

    def wants_to_reload(self) -> bool:
        if glfw is None:
            return False
        return self.keyboard.is_pressed(glfw.KEY_R)


__all__ = ["InputManager", "KeyboardState", "MouseState"]

