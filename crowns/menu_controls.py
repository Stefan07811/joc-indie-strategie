"""The game around the campaign: the title page, the pause menu, saving and loading in slots, the yearly
autosave, and the settings applied as they change. Mixed into the app."""

import json
import sys

from .settings import autosave_name, list_saves, saves_dir, write_save
from .ui.menu import Menus, step


class MenuControls:
    """Needs: self.theme, self.aspect2d, self.campaign, self.settings, self.audio, self.dialog."""

    def init_menus(self):
        self.menus = Menus(self.theme, self.aspect2d, self.getAspectRatio())
        self.menu_back = None
        self.apply_settings(first=True)

    # --- the title page and the pause menu ---------------------------------------------------------------

    def show_title(self):
        self.menu_back = self.show_title
        self.menus.main({"new": self.new_campaign, "continue": self.continue_game, "load": self.show_load,
                         "settings": self.show_settings, "quit": self.quit_game}, can_continue=bool(list_saves()))

    def show_pause(self):
        self.menu_back = self.show_pause
        self.menus.pause({"resume": self.menus.close, "save": self.show_save, "load": self.show_load,
                          "settings": self.show_settings, "title": self.to_title, "quit": self.quit_game})

    def toggle_pause(self):
        if self.menus.open:
            self.menus.close()
            if self.campaign.player is None:
                self.show_title()
        else:
            self.show_pause() if self.campaign.player is not None else self.show_title()

    def new_campaign(self):
        """Back to the map of 1402 with no realm chosen: the player picks one."""
        self.menus.close()
        if self.campaign.player is not None:
            self.restart_campaign()
        self.campaign.difficulty = self.settings.difficulty
        self.dialog.show("A new campaign",
                         "Choose a realm on the map: great or small, every one of them has its own road. "
                         "Click a land to see who holds it, then take its crown.", [("To the map", None)])

    def to_title(self):
        self.menus.close()
        self.restart_campaign()
        self.show_title()

    def quit_game(self):
        sys.exit()

    # --- saving and loading ------------------------------------------------------------------------------

    def _realm_name(self, tag):
        return self.campaign.info[tag]["name"] if tag in self.campaign.info else "No realm"

    def show_save(self):
        saves = [s for s in list_saves() if not s[0].startswith("autosave")]
        self.menus.saves("Save the game", saves, Menus.describe(self._realm_name), self._save_over,
                         self.menu_back or self.show_pause, on_new=self._save_new)

    def show_load(self):
        self.menus.saves("Load a saved game", list_saves(), Menus.describe(self._realm_name), self._load_named,
                         self.menu_back or self.show_title)

    def _save_new(self):
        c = self.campaign
        name = f"{c.player}_{c.date.year}_{c.date.month:02d}"
        self.save_game(name)
        self.menus.close()

    def _save_over(self, name):
        self.save_game(name)
        self.menus.close()

    def _load_named(self, name):
        self.menus.close()
        self.load_game(name)

    def continue_game(self):
        saves = list_saves()
        if saves:
            self._load_named(saves[0][0])

    def save_game(self, name="quick"):
        c = self.campaign
        if c.player is None:
            return
        data = c.to_dict()
        data["label"] = f"{self._realm_name(c.player)}, {c.date}"
        path = write_save(name, data)
        self.chronicle.add(str(c.date), [f"Saved ({path.stem})."])
        self.chronicle.show()

    def autosave(self):
        if self.settings.autosave and self.campaign.player is not None and self.campaign.date.month == 1:
            self.save_game(autosave_name())

    def read_save(self, name):
        path = saves_dir() / f"{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    # --- settings ---------------------------------------------------------------------------------------

    def show_settings(self):
        back = self.menu_back or self.show_title
        self.menus.settings(self.settings, self._change_setting, back)

    def _change_setting(self, key, direction):
        step(self.settings, key, direction)
        self.settings.save()
        self.apply_settings(changed=key)
        self.show_settings()

    def apply_settings(self, first=False, changed=None):
        from panda3d.core import WindowProperties
        s = self.settings
        self.audio.volume = s.music
        self.audio.sfx_volume = s.sounds
        if self.campaign is not None and self.campaign.player is None or changed == "difficulty":
            self.campaign.difficulty = s.difficulty
        if changed == "quality":
            self.quality = s.quality
            if s.quality == "low" and self.post is not None:
                self.post.cleanup()
                self.post = None
            elif s.quality == "high" and self.post is None:
                try:
                    from .render.post import PostProcess
                    self.post = PostProcess(self)
                except Exception as error:   # an old card: the picture without the last pass
                    print("no post-processing:", error)
        if changed in ("resolution", "fullscreen") and self.win is not None and hasattr(self.win, "requestProperties"):
            props = WindowProperties()
            props.setFullscreen(s.fullscreen)
            if s.size:
                props.setSize(*s.size)
            elif self.pipe is not None:
                props.setSize(int(self.pipe.getDisplayWidth() * 0.9), int(self.pipe.getDisplayHeight() * 0.85))
            self.win.requestProperties(props)
