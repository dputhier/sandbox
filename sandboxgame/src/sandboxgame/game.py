"""PyOpenGL powered runtime loop for the sandbox house defense game."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from .core import EnemyType, GameState, Vector3
from .utils.io import InputManager

logger = logging.getLogger(__name__)


try:  # pragma: no cover - OpenGL is optional during tests
    from OpenGL.GL import (
        GL_COLOR_BUFFER_BIT,
        GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_TEST,
        GL_LINES,
        GL_MODELVIEW,
        GL_PROJECTION,
        GL_QUADS,
        glBegin,
        glClear,
        glClearColor,
        glColor3f,
        glEnable,
        glEnd,
        glLoadIdentity,
        glMatrixMode,
        glPopMatrix,
        glPushMatrix,
        glScalef,
        glTranslatef,
        glVertex3f,
    )
    from OpenGL.GLU import gluLookAt, gluPerspective
    HAVE_OPENGL = True
except Exception:  # pragma: no cover - fall back to stubs
    HAVE_OPENGL = False

    def _missing(*_args, **_kwargs) -> None:
        raise RuntimeError(
            "PyOpenGL is required to render the sandbox game. "
            "Install the 'PyOpenGL' package to enable rendering."
        )

    GL_COLOR_BUFFER_BIT = GL_DEPTH_BUFFER_BIT = GL_DEPTH_TEST = 0
    GL_LINES = GL_MODELVIEW = GL_PROJECTION = GL_QUADS = 0
    glBegin = glClear = glClearColor = glColor3f = glEnable = glEnd = _missing
    glLoadIdentity = glMatrixMode = glPopMatrix = glPushMatrix = _missing
    glScalef = glTranslatef = glVertex3f = _missing
    gluLookAt = gluPerspective = _missing

try:  # pragma: no cover - glfw optional for tests
    import glfw  # type: ignore
    HAVE_GLFW = True
except Exception:  # pragma: no cover
    glfw = None  # type: ignore
    HAVE_GLFW = False


@dataclass
class SandboxConfig:
    width: int = 1280
    height: int = 720
    title: str = "Sandbox House Defense"
    target_fps: float = 60.0


class SandboxGame:
    """High level façade that glues together input, simulation and rendering."""

    def __init__(self, config: Optional[SandboxConfig] = None, *, headless: bool = False) -> None:
        self.config = config or SandboxConfig()
        self.headless = headless
        self.game_state = GameState()
        self.input = InputManager()
        self._window: Optional["glfw._GLFWwindow"] = None  # type: ignore[attr-defined]
        self._last_time: Optional[float] = None
        self._running = False

        # Spawn the three default monsters for the encounter.
        self._spawn_initial_enemies()

    # ------------------------------------------------------------------
    # Setup helpers

    def _spawn_initial_enemies(self) -> None:
        self.game_state.spawn_enemy(EnemyType.BRUTE, Vector3(-4.0, 0.5, 6.0))
        self.game_state.spawn_enemy(EnemyType.SPRINTER, Vector3(4.0, 0.5, 6.0))
        self.game_state.spawn_enemy(EnemyType.LURKER, Vector3(0.0, 3.5, -6.0))

    def initialize(self) -> None:
        if self.headless:
            logger.info("Sandbox game initialized in headless mode; rendering disabled.")
            return
        if not HAVE_GLFW or glfw is None:
            raise RuntimeError("GLFW is not available; cannot create window.")
        if not HAVE_OPENGL:
            raise RuntimeError("PyOpenGL is not available; cannot render.")

        if not glfw.init():
            raise RuntimeError("Failed to initialize GLFW.")

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

        self._window = glfw.create_window(
            self.config.width,
            self.config.height,
            self.config.title,
            None,
            None,
        )
        if not self._window:
            glfw.terminate()
            raise RuntimeError("Failed to create GLFW window.")

        glfw.make_context_current(self._window)
        glfw.swap_interval(1)
        self.input.attach(self._window)
        self._configure_opengl()

    def _configure_opengl(self) -> None:
        glClearColor(0.1, 0.1, 0.14, 1.0)
        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = self.config.width / self.config.height
        gluPerspective(60.0, aspect, 0.1, 200.0)
        glMatrixMode(GL_MODELVIEW)

    # ------------------------------------------------------------------
    # Main loop

    def run(self) -> None:
        self.initialize()
        self._running = True
        self._last_time = time.perf_counter()

        while self._running:
            if not self.headless:
                assert glfw is not None and self._window is not None
                if glfw.window_should_close(self._window):
                    break

            current = time.perf_counter()
            dt = current - (self._last_time or current)
            self._last_time = current

            self._tick(dt)

            if self.headless:
                # In headless mode ``run`` performs a single simulation tick.
                self._running = False
                continue

            self._render_scene()
            glfw.swap_buffers(self._window)

        if not self.headless and glfw is not None:
            glfw.terminate()

    def _tick(self, dt: float) -> None:
        if not self.headless:
            self.input.poll()

        movement = self.input.movement_vector()
        look = self.input.look_vector()
        fire = self.input.wants_to_fire()
        reload = self.input.wants_to_reload()

        self.game_state.update(
            dt,
            movement=movement,
            aim_direction=look,
            fire=fire,
            reload=reload,
        )

        if self.game_state.is_game_over():
            logger.info("Player defeated - exiting main loop.")
            self._running = False

    # ------------------------------------------------------------------
    # Rendering helpers

    def _render_scene(self) -> None:
        if self.headless:
            return

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        player_pos = self.game_state.player.position
        camera_pos = Vector3(player_pos.x, player_pos.y + 8.0, player_pos.z + 14.0)
        gluLookAt(
            camera_pos.x,
            camera_pos.y,
            camera_pos.z,
            player_pos.x,
            player_pos.y,
            player_pos.z,
            0.0,
            1.0,
            0.0,
        )

        self._draw_house()
        self._draw_player()
        self._draw_enemies()
        self._draw_bullets()

    def _draw_house(self) -> None:
        glColor3f(0.35, 0.35, 0.4)
        for room in self.game_state.layout.rooms:
            y = room.floor * self.game_state.layout.floor_height
            self._draw_quad(room.x_min, room.z_min, room.x_max, room.z_max, y)

        # Draw simple railings around the edges for visual guidance.
        glColor3f(0.2, 0.2, 0.25)
        glBegin(GL_LINES)
        for limit_x in (-self.game_state.layout.bounds_x, self.game_state.layout.bounds_x):
            glVertex3f(limit_x, 0.0, -self.game_state.layout.bounds_z)
            glVertex3f(limit_x, 0.0, self.game_state.layout.bounds_z)
        for limit_z in (-self.game_state.layout.bounds_z, self.game_state.layout.bounds_z):
            glVertex3f(-self.game_state.layout.bounds_x, 0.0, limit_z)
            glVertex3f(self.game_state.layout.bounds_x, 0.0, limit_z)
        glEnd()

    def _draw_player(self) -> None:
        pos = self.game_state.player.position
        glColor3f(0.2, 0.8, 0.3)
        self._draw_prism(pos, scale=Vector3(0.6, 1.6, 0.6))

    def _draw_enemies(self) -> None:
        for enemy in self.game_state.enemies:
            if not enemy.is_alive():
                continue
            if enemy.enemy_type is EnemyType.BRUTE:
                glColor3f(0.8, 0.2, 0.2)
            elif enemy.enemy_type is EnemyType.SPRINTER:
                glColor3f(0.9, 0.6, 0.2)
            else:
                glColor3f(0.5, 0.2, 0.8)
            self._draw_prism(enemy.position, scale=Vector3(0.7, 1.4, 0.7))

    def _draw_bullets(self) -> None:
        glColor3f(1.0, 0.9, 0.3)
        glBegin(GL_LINES)
        for bullet in self.game_state.bullets:
            start = bullet.position
            end = start + bullet.velocity.normalized() * 0.4
            glVertex3f(start.x, start.y, start.z)
            glVertex3f(end.x, end.y, end.z)
        glEnd()

    def _draw_quad(self, x_min: float, z_min: float, x_max: float, z_max: float, y: float) -> None:
        glBegin(GL_QUADS)
        glVertex3f(x_min, y, z_min)
        glVertex3f(x_max, y, z_min)
        glVertex3f(x_max, y, z_max)
        glVertex3f(x_min, y, z_max)
        glEnd()

    def _draw_prism(self, position: Vector3, scale: Vector3) -> None:
        glPushMatrix()
        glTranslatef(position.x, position.y, position.z)
        glScalef(scale.x, scale.y, scale.z)
        # Simple column represented by 6 quads
        glBegin(GL_QUADS)
        # Front
        glVertex3f(-0.5, 0.0, 0.5)
        glVertex3f(0.5, 0.0, 0.5)
        glVertex3f(0.5, 1.0, 0.5)
        glVertex3f(-0.5, 1.0, 0.5)
        # Back
        glVertex3f(-0.5, 0.0, -0.5)
        glVertex3f(0.5, 0.0, -0.5)
        glVertex3f(0.5, 1.0, -0.5)
        glVertex3f(-0.5, 1.0, -0.5)
        # Left
        glVertex3f(-0.5, 0.0, -0.5)
        glVertex3f(-0.5, 0.0, 0.5)
        glVertex3f(-0.5, 1.0, 0.5)
        glVertex3f(-0.5, 1.0, -0.5)
        # Right
        glVertex3f(0.5, 0.0, -0.5)
        glVertex3f(0.5, 0.0, 0.5)
        glVertex3f(0.5, 1.0, 0.5)
        glVertex3f(0.5, 1.0, -0.5)
        # Top
        glVertex3f(-0.5, 1.0, -0.5)
        glVertex3f(0.5, 1.0, -0.5)
        glVertex3f(0.5, 1.0, 0.5)
        glVertex3f(-0.5, 1.0, 0.5)
        # Bottom
        glVertex3f(-0.5, 0.0, -0.5)
        glVertex3f(0.5, 0.0, -0.5)
        glVertex3f(0.5, 0.0, 0.5)
        glVertex3f(-0.5, 0.0, 0.5)
        glEnd()
        glPopMatrix()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    game = SandboxGame()
    game.run()


__all__ = ["SandboxGame", "SandboxConfig", "main"]

