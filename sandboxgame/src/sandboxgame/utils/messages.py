"""Lightweight verbosity-aware messaging helpers."""

from __future__ import annotations

from typing import Final

_DEFAULT_VERBOSITY: Final[int] = 0
_current_verbosity: int = _DEFAULT_VERBOSITY


def set_verbosity(level: int) -> None:
    """Set the active verbosity level for sandboxgame CLI feedback."""
    global _current_verbosity
    _current_verbosity = max(0, int(level))


def print_message(message: str, *, level: int = 1) -> None:
    """Print *message* when the configured verbosity permits it."""
    if level <= _current_verbosity:
        print(message)


__all__ = ["print_message", "set_verbosity"]
