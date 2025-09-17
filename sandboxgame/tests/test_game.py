"""Tests for sandboxgame core gameplay logic."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sandboxgame.core import EnemyType, GameState, Vector3


def advance(state: GameState, seconds: float, step: float = 1 / 120.0) -> None:
    elapsed = 0.0
    while elapsed < seconds:
        state.update(step)
        elapsed += step


def test_enemy_elimination_by_bullet() -> None:
    state = GameState()
    enemy = state.spawn_enemy(EnemyType.BRUTE, position=Vector3(6.0, 0.5, 0.0), health=15.0)
    direction = enemy.position - state.player.position

    bullet = state.fire_projectile(direction)
    assert bullet is not None

    advance(state, 0.8)

    assert not enemy.is_alive()
    assert state.statistics.enemies_defeated == 1
    assert state.statistics.shots_landed >= 1


def test_ammo_management_requires_reload() -> None:
    state = GameState()
    state.player.magazine_size = 3
    state.player.ammo = 3

    direction = Vector3(1.0, 0.0, 0.0)

    for _ in range(3):
        bullet = state.fire_projectile(direction)
        assert bullet is not None
        advance(state, state.player.fire_rate)

    assert state.player.ammo == 0
    assert state.fire_projectile(direction) is None

    assert state.player.request_reload()
    advance(state, state.player.reload_duration)
    assert state.player.ammo == state.player.magazine_size

    assert state.fire_projectile(direction) is not None


def test_enemy_ai_moves_toward_player() -> None:
    state = GameState()
    enemy = state.spawn_enemy(EnemyType.SPRINTER, position=Vector3(0.0, 0.5, 8.0))

    start_distance = (enemy.position - state.player.position).length()
    advance(state, 1.0, step=1 / 60.0)
    end_distance = (enemy.position - state.player.position).length()

    assert end_distance < start_distance

