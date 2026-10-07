"""The player's settings, kept between games in ~/.crowns/settings.json; and the saved games beside them."""

import json
import os
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path

RESOLUTIONS = ["auto", "1280x720", "1366x768", "1600x900", "1920x1080", "2560x1440"]
QUALITIES = ["low", "high"]
DIFFICULTIES = ["easy", "normal", "hard"]
AUTOSAVES = 3


def home():
    return Path(os.environ.get("CROWNS_HOME", Path.home() / ".crowns"))


def saves_dir():
    return home() / "saves"


@dataclass
class Settings:
    music: float = 0.6
    sounds: float = 0.8
    quality: str = "high"
    resolution: str = "auto"
    fullscreen: bool = False
    difficulty: str = "normal"
    autosave: bool = True

    @classmethod
    def load(cls):
        path = home() / "settings.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            names = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in names})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self):
        path = home() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @property
    def size(self):
        if self.resolution == "auto":
            return None
        w, h = self.resolution.split("x")
        return int(w), int(h)


def list_saves():
    """[(name, path, info)] newest first; info: {"realm", "date", "saved"} read from the save's head."""
    out = []
    folder = saves_dir()
    if not folder.exists():
        return out
    for path in folder.glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
            info = {"realm": data.get("player"), "date": data.get("date"), "saved": path.stat().st_mtime,
                    "label": data.get("label")}
        except (OSError, ValueError):
            continue
        out.append((path.stem, path, info))
    out.sort(key=lambda s: -s[2]["saved"])
    return out


def write_save(name, data):
    folder = saves_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)            # never leave a half-written save behind
    return path


def autosave_name():
    """The autosave slot to write next: the oldest of the few kept."""
    folder = saves_dir()
    slots = [f"autosave_{k}" for k in range(1, AUTOSAVES + 1)]
    times = [(folder / f"{s}.json").stat().st_mtime if (folder / f"{s}.json").exists() else 0 for s in slots]
    return slots[times.index(min(times))]


def stamp(seconds):
    return time.strftime("%d %b %Y, %H:%M", time.localtime(seconds))
