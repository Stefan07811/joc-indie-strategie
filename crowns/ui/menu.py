"""The game's menus on parchment: the title page, the pause menu, the saved games and the settings."""

from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode

from ..settings import DIFFICULTIES, QUALITIES, RESOLUTIONS, stamp
from .theme import FADED


class Menus:
    def __init__(self, theme, parent, aspect):
        self.theme, self.parent, self.aspect = theme, parent, aspect
        self.frame = None
        self.shade = None

    @property
    def open(self):
        return self.frame is not None

    def close(self):
        for w in (self.frame, self.shade):
            if w is not None:
                w.destroy()
        self.frame = self.shade = None

    def _sheet(self, title, height, subtitle=None, dim=0.45):
        self.close()
        a = self.aspect
        self.shade = DirectFrame(parent=self.parent, frameColor=(0.12, 0.08, 0.04, dim), frameSize=(-a, a, -1, 1),
                                 state="normal")      # catches the clicks meant for the map below
        top = height / 2
        self.frame = self.theme.panel(self.parent, -0.55, 0.55, -top, top)
        self.theme.heading(self.frame, title, 0, top - 0.1, scale=0.065, align=TextNode.ACenter)
        if subtitle:
            self.theme.label(self.frame, subtitle, 0, top - 0.17, scale=0.034, align=TextNode.ACenter,
                             font=self.theme.italic, color=FADED)
        return top - (0.27 if subtitle else 0.2)

    def _buttons(self, y, items, width=0.8):
        for label, command, *rest in items:
            enabled = rest[0] if rest else True
            self.theme.button(self.frame, label, 0, y, command, width=width, scale=0.04, enabled=enabled)
            y -= 0.1
        return y

    # --- the title page -------------------------------------------------------------------------------

    def main(self, actions, can_continue):
        y = self._sheet("Crowns of the Balkans", 0.82, "The Balkans in the year 1402, after Ankara", dim=0.25)
        self._buttons(y - 0.02, [("New campaign", actions["new"]),
                                 ("Continue", actions["continue"], can_continue),
                                 ("Load a saved game", actions["load"], can_continue),
                                 ("Settings", actions["settings"]),
                                 ("Quit", actions["quit"])])

    def pause(self, actions):
        y = self._sheet("The game waits", 0.86)
        self._buttons(y - 0.02, [("Return to the game", actions["resume"]),
                                 ("Save the game", actions["save"]),
                                 ("Load a saved game", actions["load"]),
                                 ("Settings", actions["settings"]),
                                 ("Leave for the title page", actions["title"]),
                                 ("Quit", actions["quit"])])

    # --- saved games ----------------------------------------------------------------------------------

    def saves(self, title, saves, describe, on_pick, on_back, on_new=None):
        """saves: from settings.list_saves(); describe(info) -> text."""
        rows = saves[:9]
        height = 0.5 + 0.1 * (len(rows) + (1 if on_new else 0))
        y = self._sheet(title, max(0.7, height))
        if on_new:
            self.theme.button(self.frame, "A new save", 0, y, on_new, width=0.9, scale=0.036)
            y -= 0.1
        if not rows and not on_new:
            self.theme.label(self.frame, "No saved games yet.", 0, y, scale=0.036, align=TextNode.ACenter,
                             font=self.theme.italic)
            y -= 0.1
        for name, path, info in rows:
            self.theme.button(self.frame, describe(name, info), 0, y, on_pick, [name], width=0.98, scale=0.028)
            y -= 0.1
        self.theme.button(self.frame, "Back", 0, y - 0.02, on_back, width=0.4, scale=0.036)

    @staticmethod
    def describe(realm_name):
        def text(name, info):
            when = "?" if not info.get("date") else f"{_MONTHS[info['date'][1] - 1]} {info['date'][0]}"
            kind = "Autosave" if name.startswith("autosave") else ("Quick save" if name == "quick" else "Saved")
            return f"{realm_name(info.get('realm'))}, {when}  —  {kind}, {stamp(info['saved'])}"
        return text

    # --- settings -------------------------------------------------------------------------------------------

    def settings(self, settings, on_change, on_back):
        y = self._sheet("Settings", 1.05)
        rows = [("Music", f"{round(settings.music * 100)}%", "music"),
                ("Sounds", f"{round(settings.sounds * 100)}%", "sounds"),
                ("Picture", {"high": "high (shadows, smoothing)", "low": "low (for weak cards)"}[settings.quality],
                 "quality"),
                ("Window", "fit the screen" if settings.resolution == "auto" else settings.resolution, "resolution"),
                ("Full screen", "yes" if settings.fullscreen else "no", "fullscreen"),
                ("Difficulty", settings.difficulty, "difficulty"),
                ("Save every January", "yes" if settings.autosave else "no", "autosave")]
        for label, value, key in rows:
            self.theme.label(self.frame, label, -0.47, y - 0.01, scale=0.034)
            self.theme.button(self.frame, "<", 0.0, y, on_change, [key, -1], width=0.07, scale=0.034, align="left")
            self.theme.label(self.frame, value, 0.235, y - 0.01, scale=0.03, align=TextNode.ACenter)
            self.theme.button(self.frame, ">", 0.4, y, on_change, [key, 1], width=0.07, scale=0.034, align="left")
            y -= 0.095
        self.theme.label(self.frame, "The window takes the new size at once; the picture's quality applies "
                         "to the next battle.", 0, y - 0.01, scale=0.025, align=TextNode.ACenter, color=FADED,
                         wrap=1.0 / 0.025)
        self.theme.button(self.frame, "Back", 0, y - 0.11, on_back, width=0.4, scale=0.036)


_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"]


def step(settings, key, direction):
    """Move one setting one notch up or down."""
    if key in ("music", "sounds"):
        value = getattr(settings, key) + 0.1 * direction
        setattr(settings, key, round(min(1.0, max(0.0, value)), 2))
    elif key in ("fullscreen", "autosave"):
        setattr(settings, key, not getattr(settings, key))
    else:
        options = {"quality": QUALITIES, "resolution": RESOLUTIONS, "difficulty": DIFFICULTIES}[key]
        current = getattr(settings, key)
        index = options.index(current) if current in options else 0
        setattr(settings, key, options[(index + direction) % len(options)])
