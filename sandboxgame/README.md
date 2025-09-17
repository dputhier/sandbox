# Sandbox Game

## Prerequisites
- Operating system with OpenGL-capable GPU drivers.
- System packages: `python3`, `python3-pip`, and OpenGL dependencies (e.g., `mesa-utils`, `libgl1`, `libglfw3` on Debian/Ubuntu; `glfw` on macOS via Homebrew; `freeglut` on Windows via package manager).
- Ensure that your graphics drivers are up-to-date and that OpenGL 3.3 or higher is supported.

## Python Installation
You can install the package directly from the repository root:

```bash
pip install .
```

Once the project is published to PyPI, install it with:

```bash
pip install sandboxgame
```

If you plan to contribute, use an editable install with extras:

```bash
pip install -e .[dev]
```

## Running the Game
Run the game module directly using Python:

```bash
python -m sandboxgame.game
```

If a console entry point is available after installation, run:

```bash
sandboxgame
```

## Troubleshooting
- **GLFW import failure**: Install `glfw` via `pip install glfw` and ensure system libraries are available (`sudo apt install libglfw3` on Debian/Ubuntu).
- **PyOpenGL import failure**: Install via `pip install PyOpenGL PyOpenGL_accelerate`.
- **OpenGL context errors**: Confirm that your environment supports OpenGL; virtual machines may require enabling 3D acceleration.

## Running Tests
Install the testing extra and run `pytest`:

```bash
pip install .[tests]
pytest
```

