"""Tests for the input helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sandboxgame.utils.io import InputManager


def test_view_direction_accumulates_mouse_movement() -> None:
    manager = InputManager()

    # Initialize mouse position and apply a horizontal movement.
    manager.mouse.set_position(0.0, 0.0)
    manager.mouse.set_position(20.0, 0.0)
    look_right = manager.view_direction()
    assert look_right.x > 0.0
    assert look_right.z < 0.0
    assert look_right.length() == pytest.approx(1.0)

    # Without further movement the orientation remains stable.
    manager.mouse.set_position(20.0, 0.0)
    stable = manager.view_direction()
    assert stable.x == pytest.approx(look_right.x)
    assert stable.y == pytest.approx(look_right.y)
    assert stable.z == pytest.approx(look_right.z)

    # Moving the mouse downward should aim the camera downward.
    manager.mouse.set_position(20.0, 10.0)
    look_down = manager.view_direction()
    assert look_down.y < look_right.y
    assert look_down.length() == pytest.approx(1.0)
