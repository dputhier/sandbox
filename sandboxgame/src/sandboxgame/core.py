"""Core gameplay logic for the sandbox house defense game.

This module hosts the data structures that describe the state of the
world, including the player, enemies, bullets and the house layout.  The
OpenGL renderer (``sandboxgame.game``) consumes these classes so that the
gameplay rules are fully testable without requiring an OpenGL context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Callable, Iterable, List, Optional


# ---------------------------------------------------------------------------
# Vector helpers


@dataclass(frozen=True)
class Vector3:
    """Simple 3D vector used for positions and directions."""

    x: float
    y: float
    z: float

    def __add__(self, other: "Vector3") -> "Vector3":
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vector3") -> "Vector3":
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vector3":
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> "Vector3":
        return Vector3(self.x / scalar, self.y / scalar, self.z / scalar)

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalized(self) -> "Vector3":
        mag = self.length()
        if mag == 0:
            return Vector3(0.0, 0.0, 0.0)
        return self / mag

    def with_y(self, new_y: float) -> "Vector3":
        return Vector3(self.x, new_y, self.z)

    def cross(self, other: "Vector3") -> "Vector3":
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp *value* in the inclusive range ``[minimum, maximum]``."""

    return max(minimum, min(maximum, value))


# ---------------------------------------------------------------------------
# World description


@dataclass
class Room:
    """Axis-aligned rectangular room used for collision bounds."""

    name: str
    floor: int
    x_min: float
    x_max: float
    z_min: float
    z_max: float

    def contains(self, position: Vector3) -> bool:
        return (
            self.x_min <= position.x <= self.x_max
            and self.z_min <= position.z <= self.z_max
            and position.y >= self.floor * 3.0
            and position.y <= self.floor * 3.0 + 3.0
        )


@dataclass
class HouseLayout:
    """Two-storey, eight-room house description used for navigation."""

    rooms: List[Room] = field(default_factory=list)
    bounds_x: float = 12.0
    bounds_z: float = 16.0
    floor_height: float = 3.0

    @classmethod
    def standard(cls) -> "HouseLayout":
        rooms: List[Room] = []
        width = 6.0
        depth = 8.0
        names = [
            ("Kitchen", "Dining"),
            ("Living", "Study"),
            ("Bedroom", "Bathroom"),
            ("Guest", "Storage"),
        ]
        for floor in range(2):
            for row in range(2):
                for col in range(2):
                    label = names[floor * 2 + row][col]
                    x_min = -width + col * width
                    x_max = x_min + width
                    z_min = -depth + row * depth
                    z_max = z_min + depth
                    rooms.append(
                        Room(
                            name=f"{label} (Floor {floor + 1})",
                            floor=floor,
                            x_min=x_min,
                            x_max=x_max,
                            z_min=z_min,
                            z_max=z_max,
                        )
                    )
        layout = cls(rooms=rooms)
        layout.bounds_x = width
        layout.bounds_z = depth
        return layout

    def constrain(self, position: Vector3) -> Vector3:
        """Clamp the position to stay within the house footprint."""

        x = clamp(position.x, -self.bounds_x, self.bounds_x)
        z = clamp(position.z, -self.bounds_z, self.bounds_z)
        # Floors are discrete levels in this simplified model.
        floor = clamp(round(position.y / self.floor_height), 0, 1)
        y = floor * self.floor_height + 0.5
        return Vector3(x, y, z)

    def spawn_point(self) -> Vector3:
        return Vector3(0.0, 0.5, 0.0)

    def is_inside(self, position: Vector3) -> bool:
        return -self.bounds_x <= position.x <= self.bounds_x and -self.bounds_z <= position.z <= self.bounds_z


# ---------------------------------------------------------------------------
# Entities


class EnemyType(Enum):
    BRUTE = "brute"
    SPRINTER = "sprinter"
    LURKER = "lurker"


@dataclass
class Player:
    position: Vector3
    speed: float = 6.0
    health: int = 100
    magazine_size: int = 40
    ammo: int = 40
    fire_rate: float = 0.08
    reload_duration: float = 1.5
    fire_cooldown: float = 0.0
    reload_cooldown: float = 0.0
    eye_height: float = 1.4
    view_direction: Vector3 = field(
        default_factory=lambda: Vector3(0.0, 0.0, -1.0)
    )

    def move(self, direction: Vector3, dt: float, layout: HouseLayout) -> None:
        if direction.length() == 0:
            return
        displacement = direction.normalized() * self.speed * dt
        self.position = layout.constrain(self.position + displacement)

    def update(self, dt: float) -> None:
        if self.fire_cooldown > 0:
            self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        if self.reload_cooldown > 0:
            self.reload_cooldown = max(0.0, self.reload_cooldown - dt)
            if self.reload_cooldown == 0.0:
                self.ammo = self.magazine_size

    def can_fire(self) -> bool:
        return self.ammo > 0 and self.fire_cooldown == 0.0 and self.reload_cooldown == 0.0

    def trigger_shot(self) -> bool:
        if not self.can_fire():
            return False
        self.ammo -= 1
        self.fire_cooldown = self.fire_rate
        return True

    def request_reload(self) -> bool:
        if self.reload_cooldown > 0 or self.ammo == self.magazine_size:
            return False
        self.reload_cooldown = self.reload_duration
        return True

    def set_view_direction(self, direction: Optional[Vector3]) -> None:
        if direction is None:
            return
        if direction.length() == 0:
            return
        self.view_direction = direction.normalized()

    def eye_position(self) -> Vector3:
        return self.position + Vector3(0.0, self.eye_height, 0.0)


@dataclass
class Enemy:
    enemy_type: EnemyType
    position: Vector3
    health: float = 50.0
    speed: float = 2.5
    hit_radius: float = 0.75
    attack_interval: float = 1.25
    attack_damage: int = 8
    attack_cooldown: float = 0.0

    def update(self, dt: float, player_position: Vector3, layout: HouseLayout) -> None:
        if self.health <= 0:
            return

        if self.attack_cooldown > 0:
            self.attack_cooldown = max(0.0, self.attack_cooldown - dt)

        offset = player_position - self.position
        distance = offset.length()
        direction = offset.normalized() if distance else Vector3(0.0, 0.0, 0.0)

        desired_speed = self.speed

        if self.enemy_type is EnemyType.BRUTE:
            desired_speed *= 0.6
        elif self.enemy_type is EnemyType.SPRINTER:
            desired_speed *= 1.4
        else:  # LURKER
            if distance < 4.5:
                # Back away slightly to keep distance before dashing in.
                direction = direction * -1.0
                desired_speed *= 0.9

        if distance > self.hit_radius * 0.5:
            displacement = direction * desired_speed * dt
            self.position = layout.constrain(self.position + displacement)

    def is_alive(self) -> bool:
        return self.health > 0


@dataclass
class Bullet:
    position: Vector3
    velocity: Vector3
    damage: float
    ttl: float
    radius: float = 0.25

    def update(self, dt: float) -> None:
        self.position = self.position + self.velocity * dt
        self.ttl -= dt

    def is_active(self) -> bool:
        return self.ttl > 0


@dataclass
class GameStatistics:
    enemies_defeated: int = 0
    shots_fired: int = 0
    shots_landed: int = 0
    damage_taken: int = 0


EventCallback = Callable[[str, dict], None]


class GameState:
    """Authoritative simulation state for the sandbox game."""

    def __init__(self, layout: Optional[HouseLayout] = None) -> None:
        self.layout = layout or HouseLayout.standard()
        self.player = Player(position=self.layout.spawn_point())
        self.enemies: List[Enemy] = []
        self.bullets: List[Bullet] = []
        self.statistics = GameStatistics()
        self.listeners: List[EventCallback] = []

    def add_listener(self, callback: EventCallback) -> None:
        self.listeners.append(callback)

    def dispatch(self, event_type: str, payload: Optional[dict] = None) -> None:
        data = payload or {}
        for callback in list(self.listeners):
            callback(event_type, data)

    # ------------------------------------------------------------------
    # Entity management

    def spawn_enemy(
        self,
        enemy_type: EnemyType,
        position: Optional[Vector3] = None,
        health: Optional[float] = None,
    ) -> Enemy:
        enemy = Enemy(
            enemy_type=enemy_type,
            position=position or Vector3(0.0, 0.5, 6.0),
        )
        if health is not None:
            enemy.health = health
        self.enemies.append(enemy)
        self.dispatch("enemy_spawned", {"enemy": enemy})
        return enemy

    def fire_projectile(self, direction: Optional[Vector3] = None) -> Optional[Bullet]:
        if direction is not None:
            self.player.set_view_direction(direction)

        aim = self.player.view_direction
        if aim.length() == 0:
            aim = Vector3(0.0, 0.0, -1.0)
        direction = aim.normalized()

        if not self.player.trigger_shot():
            return None

        velocity = direction * 30.0
        bullet = Bullet(
            position=self.player.eye_position() + direction * 0.3,
            velocity=velocity,
            damage=15.0,
            ttl=1.5,
        )
        self.bullets.append(bullet)
        self.statistics.shots_fired += 1
        self.dispatch("bullet_fired", {"bullet": bullet})
        return bullet

    # ------------------------------------------------------------------
    # Simulation loop

    def update(
        self,
        dt: float,
        movement: Optional[Vector3] = None,
        aim_direction: Optional[Vector3] = None,
        fire: bool = False,
        reload: bool = False,
    ) -> None:
        if reload:
            self.player.request_reload()

        if movement is not None:
            self.player.move(movement, dt, self.layout)

        if aim_direction is not None:
            self.player.set_view_direction(aim_direction)

        self.player.update(dt)

        if fire and self.player.can_fire():
            self.fire_projectile()

        self._update_bullets(dt)
        self._update_enemies(dt)
        self._handle_collisions()

    # ------------------------------------------------------------------
    # Internal helpers

    def _update_bullets(self, dt: float) -> None:
        active: List[Bullet] = []
        for bullet in self.bullets:
            bullet.update(dt)
            if not bullet.is_active() or not self.layout.is_inside(bullet.position):
                continue
            active.append(bullet)
        self.bullets = active

    def _update_enemies(self, dt: float) -> None:
        for enemy in self.enemies:
            enemy.update(dt, self.player.position, self.layout)

    def _handle_collisions(self) -> None:
        survivors: List[Enemy] = []
        for enemy in self.enemies:
            if not enemy.is_alive():
                continue
            # Enemy attacks player on close contact.
            if self._enemy_can_attack_player(enemy):
                self._resolve_enemy_attack(enemy)

            survivors.append(enemy)

        self.enemies = survivors

        active_bullets: List[Bullet] = []
        for bullet in self.bullets:
            victim = self._find_bullet_collision(bullet, self.enemies)
            if victim is None:
                active_bullets.append(bullet)
                continue
            victim.health -= bullet.damage
            if victim.health <= 0:
                self.statistics.enemies_defeated += 1
                self.dispatch("enemy_defeated", {"enemy": victim})
            self.statistics.shots_landed += 1

        self.bullets = active_bullets

    def _enemy_can_attack_player(self, enemy: Enemy) -> bool:
        if enemy.attack_cooldown > 0:
            return False
        distance = (enemy.position - self.player.position).length()
        return distance <= enemy.hit_radius + 0.2

    def _resolve_enemy_attack(self, enemy: Enemy) -> None:
        self.player.health -= enemy.attack_damage
        enemy.attack_cooldown = enemy.attack_interval
        self.statistics.damage_taken += enemy.attack_damage
        self.dispatch("player_damaged", {"enemy": enemy, "health": self.player.health})

    def _find_bullet_collision(
        self, bullet: Bullet, enemies: Iterable[Enemy]
    ) -> Optional[Enemy]:
        for enemy in enemies:
            if not enemy.is_alive():
                continue
            if (enemy.position - bullet.position).length() <= enemy.hit_radius + bullet.radius:
                return enemy
        return None

    # ------------------------------------------------------------------
    # Convenience helpers used by the renderer/tests

    def is_game_over(self) -> bool:
        return self.player.health <= 0


__all__ = [
    "Vector3",
    "Room",
    "HouseLayout",
    "Player",
    "Enemy",
    "EnemyType",
    "Bullet",
    "GameState",
    "GameStatistics",
]

