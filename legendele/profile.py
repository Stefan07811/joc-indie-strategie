"""The player's own files: settings and saved campaigns.

They live in ~/.legendele (or wherever LEGENDELE_HOME points, e.g. for tests).
"""

import json
import os
import time
from pathlib import Path

from .game.save import SaveError, read_save, save_game, summary

SLOTS = ("slot1", "slot2", "slot3")
AUTOSAVE = "autosave"
DEFAULT_SETTINGS = {"sound": 0.7, "music": 0.4, "fullscreen": False, "battles": "ask"}
BATTLE_MODES = ("ask", "fight", "auto")


def home():
    return Path(os.environ.get("LEGENDELE_HOME", Path.home() / ".legendele"))


def save_path(slot):
    return home() / "saves" / f"{slot}.json"


# --- settings --------------------------------------------------------------------------------

def load_settings():
    try:
        saved = json.loads((home() / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    return {**DEFAULT_SETTINGS, **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}


def store_settings(settings):
    path = home() / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


# --- saves -----------------------------------------------------------------------------------

def save(game, slot):
    save_game(game, save_path(slot), extra={"saved_at": time.time()})


def slot_info(slot):
    """None for an empty slot, else a summary plus "saved_at" (or "error" for a broken file)."""
    path = save_path(slot)
    if not path.exists():
        return None
    try:
        d = read_save(path)
        return {**summary(d), "saved_at": d.get("saved_at", path.stat().st_mtime)}
    except (SaveError, KeyError) as e:
        return {"error": str(e)}


def latest_slot():
    """The most recently saved slot (the autosave included) that can be continued, or None."""
    best = None
    for slot in (AUTOSAVE, *SLOTS):
        info = slot_info(slot)
        if info and "error" not in info and not info["over"]:
            if best is None or info["saved_at"] > best[1]:
                best = (slot, info["saved_at"])
    return best[0] if best else None
