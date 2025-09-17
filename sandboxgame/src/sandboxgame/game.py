"""PyOpenGL powered runtime loop for the sandbox house defense game."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from typing import Optional, Sequence

from .core import EnemyType, GameState, Vector3
from .utils.io import InputManager
from .utils.messages import print_message

logger = logging.getLogger(__name__)

DEFAULT_VERBOSITY = 1
VERBOSITY_LEVELS = {
    0: logging.WARNING,
    1: logging.INFO,
    2: logging.DEBUG,
}


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
        layout = self.game_state.layout

        perimeter_ratio_ground = 0.85
        perimeter_ratio_upper = 0.9

        ground_y = 0.5
        upper_y = layout.floor_height + 0.5

        brute_position = layout.constrain(
            Vector3(-layout.bounds_x * perimeter_ratio_ground, ground_y, layout.bounds_z * perimeter_ratio_ground)
        )
        sprinter_position = layout.constrain(
            Vector3(layout.bounds_x * perimeter_ratio_ground, ground_y, layout.bounds_z * perimeter_ratio_ground)
        )
        lurker_position = layout.constrain(
            Vector3(0.0, upper_y, layout.bounds_z * perimeter_ratio_upper)
        )

        self.game_state.spawn_enemy(EnemyType.BRUTE, brute_position)
        self.game_state.spawn_enemy(EnemyType.SPRINTER, sprinter_position)
        self.game_state.spawn_enemy(EnemyType.LURKER, lurker_position)

    def initialize(self) -> None:
        if self.headless:
            logger.info("Sandbox game initialized in headless mode; rendering disabled.")
            print_message(
                "Headless mode active - skipping window/context initialization.",
                level=1,
            )
            return
        if not HAVE_GLFW or glfw is None:
            raise RuntimeError("GLFW is not available; cannot create window.")
        if not HAVE_OPENGL:
            raise RuntimeError("PyOpenGL is not available; cannot render.")

        if not glfw.init():
            raise RuntimeError("Failed to initialize GLFW.")

        self._configure_window_hints()

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

    def _configure_window_hints(self) -> None:
        """Request an OpenGL context compatible with the fixed-function pipeline."""

        # Reset hints to their defaults so repeated initialization attempts remain
        # deterministic.
        glfw.default_window_hints()

        # The renderer relies heavily on immediate-mode and other deprecated
        # fixed-function APIs. Request a compatibility context so these entry points
        # remain available. macOS in particular needs to fall back to OpenGL 2.1 to
        # access the legacy pipeline without triggering GL_INVALID_OPERATION errors.
        if sys.platform == "darwin":
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 2)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_ANY_PROFILE)
        else:
            # Other platforms typically support a compatibility profile at higher
            # versions, but we avoid requesting a core profile until the renderer is
            # upgraded.
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
            glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_COMPAT_PROFILE)

        # Explicitly request a non-forward-compatible context to ensure deprecated
        # entry points remain available.
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.FALSE)

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
        print_message("Initializing sandbox game...", level=1)
        self.initialize()
        self._running = True
        self._last_time = time.perf_counter()

        print_message("Starting main loop.", level=1)

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
                print_message("Headless tick complete.", level=2)
                continue

            self._render_scene()
            glfw.swap_buffers(self._window)

        if not self.headless and glfw is not None:
            glfw.terminate()
        print_message("Sandbox game loop terminated.", level=1)

    def _tick(self, dt: float) -> None:
        if not self.headless:
            self.input.poll()

        movement = self.input.movement_vector()
        look = self.input.view_direction()
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
            print_message("Player defeated - exiting main loop.", level=1)
            self._running = False

    # ------------------------------------------------------------------
    # Rendering helpers

    def _render_scene(self) -> None:
        if self.headless:
            return

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        player = self.game_state.player
        view_direction = player.view_direction
        if view_direction.length() == 0:
            view_direction = Vector3(0.0, 0.0, -1.0)
        view_direction = view_direction.normalized()

        eye_position = player.eye_position()
        camera_pos = eye_position - view_direction * 0.1
        target = eye_position + view_direction
        gluLookAt(
            camera_pos.x,
            camera_pos.y,
            camera_pos.z,
            target.x,
            target.y,
            target.z,
            0.0,
            1.0,
            0.0,
        )

        self._draw_house()
        self._draw_enemies()
        self._draw_bullets()
        self._draw_weapon(camera_pos, view_direction)

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

    def _draw_weapon(self, camera_position: Vector3, view_direction: Vector3) -> None:
        glColor3f(0.3, 0.32, 0.36)

        forward = view_direction.normalized() if view_direction.length() else Vector3(0.0, 0.0, -1.0)
        up_world = Vector3(0.0, 1.0, 0.0)
        right = up_world.cross(forward)
        if right.length() == 0:
            right = Vector3(1.0, 0.0, 0.0)
        right = right.normalized()
        up = right.cross(forward).normalized()

        half_width = 0.075
        half_height = 0.06
        half_length = 0.25

        center = camera_position + forward * (half_length + 0.1) - up * 0.12 + right * 0.12

        def vertex(sign_x: float, sign_y: float, sign_z: float) -> Vector3:
            return (
                center
                + right * (sign_x * half_width)
                + up * (sign_y * half_height)
                + forward * (sign_z * half_length)
            )

        front_top_right = vertex(1.0, 1.0, 1.0)
        front_top_left = vertex(-1.0, 1.0, 1.0)
        front_bottom_left = vertex(-1.0, -1.0, 1.0)
        front_bottom_right = vertex(1.0, -1.0, 1.0)
        back_top_right = vertex(1.0, 1.0, -1.0)
        back_top_left = vertex(-1.0, 1.0, -1.0)
        back_bottom_left = vertex(-1.0, -1.0, -1.0)
        back_bottom_right = vertex(1.0, -1.0, -1.0)

        glBegin(GL_QUADS)
        # Front face
        glVertex3f(front_top_right.x, front_top_right.y, front_top_right.z)
        glVertex3f(front_top_left.x, front_top_left.y, front_top_left.z)
        glVertex3f(front_bottom_left.x, front_bottom_left.y, front_bottom_left.z)
        glVertex3f(front_bottom_right.x, front_bottom_right.y, front_bottom_right.z)
        # Back face
        glVertex3f(back_top_left.x, back_top_left.y, back_top_left.z)
        glVertex3f(back_top_right.x, back_top_right.y, back_top_right.z)
        glVertex3f(back_bottom_right.x, back_bottom_right.y, back_bottom_right.z)
        glVertex3f(back_bottom_left.x, back_bottom_left.y, back_bottom_left.z)
        # Left face
        glVertex3f(back_top_left.x, back_top_left.y, back_top_left.z)
        glVertex3f(front_top_left.x, front_top_left.y, front_top_left.z)
        glVertex3f(front_bottom_left.x, front_bottom_left.y, front_bottom_left.z)
        glVertex3f(back_bottom_left.x, back_bottom_left.y, back_bottom_left.z)
        # Right face
        glVertex3f(front_top_right.x, front_top_right.y, front_top_right.z)
        glVertex3f(back_top_right.x, back_top_right.y, back_top_right.z)
        glVertex3f(back_bottom_right.x, back_bottom_right.y, back_bottom_right.z)
        glVertex3f(front_bottom_right.x, front_bottom_right.y, front_bottom_right.z)
        # Top face
        glVertex3f(back_top_right.x, back_top_right.y, back_top_right.z)
        glVertex3f(back_top_left.x, back_top_left.y, back_top_left.z)
        glVertex3f(front_top_left.x, front_top_left.y, front_top_left.z)
        glVertex3f(front_top_right.x, front_top_right.y, front_top_right.z)
        # Bottom face
        glVertex3f(front_bottom_right.x, front_bottom_right.y, front_bottom_right.z)
        glVertex3f(front_bottom_left.x, front_bottom_left.y, front_bottom_left.z)
        glVertex3f(back_bottom_left.x, back_bottom_left.y, back_bottom_left.z)
        glVertex3f(back_bottom_right.x, back_bottom_right.y, back_bottom_right.z)
        glEnd()

        # Simple muzzle flash guide rail
        muzzle_start = front_top_right + forward * 0.05
        muzzle_end = muzzle_start + forward * 0.2
        glColor3f(0.8, 0.8, 0.85)
        glBegin(GL_LINES)
        glVertex3f(muzzle_start.x, muzzle_start.y, muzzle_start.z)
        glVertex3f(muzzle_end.x, muzzle_end.y, muzzle_end.z)
        glEnd()

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


def apply_cli_verbosity(verbosity: int) -> logging.Logger:
    """Configure logging for the CLI based on the requested verbosity."""

    level = VERBOSITY_LEVELS.get(verbosity, logging.INFO)
    from sandboxgame.utils.messages import set_verbosity

    set_verbosity(verbosity)
    logging.basicConfig(level=level)

    cli_logger = logging.getLogger("sandboxgame.cli")
    message_level = logging.INFO if level <= logging.INFO else level
    cli_logger.log(
        message_level,
        "Sandbox House Defense CLI starting (verbosity=%s)",
        verbosity,
    )
    return cli_logger


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Sandbox House Defense CLI")
    parser.add_argument(
        "--verbosity",
        choices=tuple(VERBOSITY_LEVELS.keys()),
        default=DEFAULT_VERBOSITY,
        type=int,
        help="Control CLI logging verbosity (0=warnings, 1=info, 2=debug).",
    )
    args = parser.parse_args(argv)

    apply_cli_verbosity(args.verbosity)

    game = SandboxGame()
    game.run()


__all__ = ["SandboxGame", "SandboxConfig", "main"]


if __name__ == "__main__":
    main()

