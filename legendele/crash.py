"""When the game crashes: write what happened to crash.log in the player's folder and say so in a window.

The Windows program has no console, so without this a crash would simply close the game and leave
nothing to send back. The log keeps the newest reports at the end and is trimmed when it grows large.
"""

import os
import platform
import sys
import time
import traceback

from . import profile

LOG_NAME = "crash.log"
MAX_BYTES = 200_000
CHRONICLE_LINES = 20


def log_path():
    return profile.home() / LOG_NAME


def write(exc, app=None):
    """Append a report of `exc` to the crash log; returns the log's path (None if it cannot be written)."""
    from .ui.menus import VERSION
    lines = [
        "=" * 72,
        time.strftime("%Y-%m-%d %H:%M:%S"),
        f"Legends of the Carpathians {VERSION}  ·  Python {platform.python_version()}  ·  "
        f"{platform.platform()}  ·  {'packaged' if getattr(sys, 'frozen', False) else 'from source'}",
    ]
    try:
        import pygame
        lines.append(f"pygame-ce {pygame.version.ver}  ·  SDL {'.'.join(map(str, pygame.get_sdl_version()))}")
    except Exception:  # noqa: BLE001 - the report must not fail because of the report
        pass
    lines += _where(app)
    lines += ["", "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip(), ""]
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        text = (old + "\n".join(lines) + "\n")[-MAX_BYTES:]
        path.write_text(text, encoding="utf-8")
    except OSError:
        return None
    return path


def _where(app):
    """What the player was doing: the screen, and in a campaign the legend, date and latest news."""
    if app is None:
        return []
    scene = getattr(app, "scene", None)
    out = [f"Screen: {type(scene).__name__}"]
    game = getattr(scene, "game", None)
    if game is not None:
        try:
            out.append(f"Campaign: {game.player}, {game.date}, difficulty {game.difficulty}, options {game.options}")
            out += ["Latest news:"] + [f"  {line}" for line in game.log[-CHRONICLE_LINES:]]
        except Exception:  # noqa: BLE001
            pass
    return out


def headless():
    """No one to read a window (tests, screenshots, the build machine): a message box would only block."""
    return os.environ.get("SDL_VIDEODRIVER") == "dummy"


def handle(exc, app=None):
    """Log the crash and tell the player where the log is. Returns the log's path."""
    path = write(exc, app)
    where = f"The details were written to:\n{path}" if path else "The details could not be written to disk."
    message = (f"Sorry, the game has crashed.\n\n{type(exc).__name__}: {exc}\n\n{where}\n\n"
               "Please send that file to the developer. Your campaign was autosaved at the start of the season "
               "(Continue in the main menu).")
    if sys.stderr:  # the packaged Windows program has none
        print(message, file=sys.stderr)
    if headless():
        return path
    try:
        import pygame
        pygame.display.message_box("Legends of the Carpathians", message, message_type="error")
    except Exception:  # noqa: BLE001 - no display: the message above and the log will do
        pass
    return path
