"""Tests for the sandboxgame command line interface."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import sandboxgame.game as game_module


def test_main_accepts_verbosity_option(monkeypatch) -> None:
    """Ensure ``main`` parses verbosity flags and runs the game."""

    recorded = {}

    class DummyGame:
        def __init__(self) -> None:
            recorded["instantiated"] = True

        def run(self) -> None:
            recorded["run"] = True

    def fake_apply_cli_verbosity(level: int) -> None:
        recorded["verbosity"] = level

    monkeypatch.setattr(game_module, "SandboxGame", DummyGame)
    monkeypatch.setattr(game_module, "apply_cli_verbosity", fake_apply_cli_verbosity)

    game_module.main(["--verbosity", "2"])

    assert recorded == {"instantiated": True, "verbosity": 2, "run": True}
