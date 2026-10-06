"""Menus: the title screen, save/load slots, settings and the in-game pause menu."""

import time

import pygame

from .. import profile
from ..game.save import SaveError
from . import theme

VERSION = "0.6"


def _button_column(labels, top, width=320, height=46, gap=14):
    cx = theme.WINDOW_SIZE[0] // 2
    return [(pygame.Rect(cx - width // 2, top + i * (height + gap), width, height), label)
            for i, label in enumerate(labels)]


def _backdrop(app, surface, darkness=170):
    surface.fill(theme.PANEL_BG)
    view = app.backdrop()
    surface.blit(view, view.get_rect(centerx=theme.WINDOW_SIZE[0] // 2))
    veil = pygame.Surface(theme.WINDOW_SIZE, pygame.SRCALPHA)
    veil.fill((20, 14, 10, darkness))
    surface.blit(veil, (0, 0))


def _clicked(event):
    return event.type == pygame.MOUSEBUTTONDOWN and event.button == 1


def _escape(event):
    return event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE


class MainMenu:
    music = "menu"

    def __init__(self, app):
        self.app = app
        self.continue_slot = profile.latest_slot()
        labels = (["Continue"] if self.continue_slot else []) + ["New Campaign", "Load Game", "Settings", "Quit"]
        self.buttons = _button_column(labels, 330)

    def handle(self, event):
        if not _clicked(event):
            return
        for rect, label in self.buttons:
            if rect.collidepoint(event.pos):
                self.app.audio.play("click")
                if label == "Continue":
                    self.app.load_slot(self.continue_slot)
                elif label == "New Campaign":
                    self.app.new_campaign()
                elif label == "Load Game":
                    self.app.scene = SlotScreen(self.app, "load", back=self)
                elif label == "Settings":
                    self.app.scene = SettingsScreen(self.app, back=self)
                else:
                    self.app.quit()

    def draw(self, surface):
        _backdrop(self.app, surface)
        cx = theme.WINDOW_SIZE[0] // 2
        emblems = ("voievodat", "zmei", "iele", "strigoi")
        for i, fid in enumerate(emblems):
            color = tuple(self.app.data.factions[fid]["color"])
            banner = self.app.assets.get(f"army_{fid}", color, 5)
            x = cx + (i - 1.5) * 90
            surface.blit(banner, banner.get_rect(midbottom=(x, 150)))
        theme.outlined(surface, "Legends of the Carpathians", (cx, 200), 66, theme.GOLD, width=3)
        theme.outlined(surface, "Four legends. One Heart of the Mountains.", (cx, 256), 26, theme.PARCHMENT,
                       style="italic")
        mouse = pygame.mouse.get_pos()
        box = self.buttons[0][0].unionall([r for r, _ in self.buttons]).inflate(70, 50)
        theme.frame(surface, box)
        for rect, label in self.buttons:
            theme.button(surface, rect, label, rect.collidepoint(mouse))
        if self.continue_slot:
            info = profile.slot_info(self.continue_slot)
            faction = self.app.data.factions[info["player"]]["name"]
            theme.text(surface, f"{faction}, {_date(self.app, info['round'])}",
                       (cx, self.buttons[0][0].bottom + 2), 16, theme.TEXT_DIM, anchor="midtop")
        theme.text(surface, f"v{VERSION}", (theme.WINDOW_SIZE[0] - 12, theme.WINDOW_SIZE[1] - 10), 16,
                   theme.TEXT_DIM, anchor="bottomright")


def _date(app, round_no):
    seasons = ("Spring", "Summer", "Autumn", "Winter")
    return f"{seasons[round_no % 4]} {app.data.map['start_year'] + round_no // 4}"


class SlotScreen:
    """Pick a slot to save the current campaign in, or a save to load."""

    music = None  # keep whatever is playing

    def __init__(self, app, mode, back):
        self.app = app
        self.mode = mode
        self.back = back
        self.flash = None
        slots = list(profile.SLOTS) if mode == "save" else [profile.AUTOSAVE, *profile.SLOTS]
        self.rows = [(pygame.Rect(theme.WINDOW_SIZE[0] // 2 - 320, 200 + i * 86, 640, 72), slot)
                     for i, slot in enumerate(slots)]
        self.back_rect = pygame.Rect(theme.WINDOW_SIZE[0] // 2 - 100, 200 + len(slots) * 86 + 20, 200, 44)

    def handle(self, event):
        if _escape(event) or (_clicked(event) and self.back_rect.collidepoint(event.pos)):
            self.app.audio.play("click")
            self.app.scene = self.back
            return
        if not _clicked(event):
            return
        for rect, slot in self.rows:
            if rect.collidepoint(event.pos):
                if self.mode == "save":
                    try:
                        profile.save(self.back.game, slot)
                        self.flash = (f"Saved in {_slot_name(slot)}.", theme.GOOD, time.time())
                        self.app.audio.play("build")
                    except OSError as e:
                        self.flash = (f"Could not save: {e}", theme.DANGER, time.time())
                else:
                    info = profile.slot_info(slot)
                    if info and "error" not in info:
                        self.app.audio.play("click")
                        try:
                            self.app.load_slot(slot)
                        except SaveError as e:
                            self.flash = (str(e), theme.DANGER, time.time())

    def draw(self, surface):
        _backdrop(self.app, surface, 200)
        cx = theme.WINDOW_SIZE[0] // 2
        box = self.rows[0][0].unionall([r for r, _ in self.rows]).inflate(60, 80).move(0, -22)
        theme.frame(surface, box)
        theme.ribbon(surface, (cx, box.y + 2), "Save Game" if self.mode == "save" else "Load Game", 30, width=320)
        mouse = pygame.mouse.get_pos()
        for rect, slot in self.rows:
            info = profile.slot_info(slot)
            usable = self.mode == "save" or (info and "error" not in info)
            hovered = usable and rect.collidepoint(mouse)
            theme.row(surface, rect, hovered, usable)
            theme.outlined(surface, _slot_name(slot), (rect.x + 18, rect.y + 8), 22, theme.PARCHMENT, anchor="topleft",
                           width=1)
            if info is None:
                theme.text(surface, "Empty", (rect.x + 18, rect.y + 42), 19, theme.TEXT_DIM)
            elif "error" in info:
                theme.text(surface, "Unreadable save", (rect.x + 18, rect.y + 42), 19, theme.DANGER)
            else:
                f = self.app.data.factions[info["player"]]
                theme.text(surface, f"{f['name']}  ·  {_date(self.app, info['round'])}  ·  "
                                    f"{info['provinces']} provinces" + ("  ·  war over" if info["over"] else ""),
                           (rect.x + 18, rect.y + 42), 19, tuple(f["color"]))
                stamp = time.strftime("%d %b %Y, %H:%M", time.localtime(info["saved_at"]))
                theme.text(surface, stamp, (rect.right - 18, rect.y + 14), 17, theme.TEXT_DIM, anchor="topright")
        theme.button(surface, self.back_rect, "Back", self.back_rect.collidepoint(mouse))
        if self.flash and time.time() - self.flash[2] < 3:
            theme.text(surface, self.flash[0], (cx, self.back_rect.bottom + 30), 22, self.flash[1], anchor="center")


def _slot_name(slot):
    return "Autosave" if slot == profile.AUTOSAVE else f"Slot {slot[-1]}"


class SettingsScreen:
    music = None

    def __init__(self, app, back):
        self.app = app
        self.back = back
        cx = theme.WINDOW_SIZE[0] // 2
        self.controls = {}
        for i, key in enumerate(("sound", "music")):
            y = 240 + i * 80
            self.controls[f"{key}-"] = pygame.Rect(cx + 40, y, 44, 40)
            self.controls[f"{key}+"] = pygame.Rect(cx + 196, y, 44, 40)
        self.controls["fullscreen"] = pygame.Rect(cx + 40, 400, 200, 40)
        self.controls["battles"] = pygame.Rect(cx + 40, 470, 200, 40)
        self.back_rect = pygame.Rect(cx - 100, 580, 200, 44)

    def handle(self, event):
        if _escape(event) or (_clicked(event) and self.back_rect.collidepoint(event.pos)):
            self.app.scene = self.back
            return
        if not _clicked(event):
            return
        settings = self.app.settings
        for name, rect in self.controls.items():
            if not rect.collidepoint(event.pos):
                continue
            if name == "fullscreen":
                settings["fullscreen"] = not settings["fullscreen"]
                self.app.apply_display()
            elif name == "battles":
                modes = profile.BATTLE_MODES
                settings["battles"] = modes[(modes.index(settings["battles"]) + 1) % len(modes)]
            else:
                key, sign = name[:-1], name[-1]
                settings[key] = round(min(1.0, max(0.0, settings[key] + (0.1 if sign == "+" else -0.1))), 1)
            profile.store_settings(settings)
            self.app.audio.play("click")

    def draw(self, surface):
        _backdrop(self.app, surface, 200)
        cx = theme.WINDOW_SIZE[0] // 2
        theme.frame(surface, pygame.Rect(cx - 330, 150, 660, 414))
        theme.ribbon(surface, (cx, 152), "Settings", 30, width=300)
        mouse = pygame.mouse.get_pos()
        settings = self.app.settings
        for i, (key, label) in enumerate((("sound", "Sound effects"), ("music", "Music"))):
            y = 240 + i * 80
            theme.text(surface, label, (cx - 40, y + 20), 28, theme.PARCHMENT, anchor="midright")
            theme.button(surface, self.controls[f"{key}-"], "-", self.controls[f"{key}-"].collidepoint(mouse))
            theme.text(surface, f"{round(settings[key] * 100)}%", (cx + 140, y + 20), 28, theme.GOLD, anchor="center")
            theme.button(surface, self.controls[f"{key}+"], "+", self.controls[f"{key}+"].collidepoint(mouse))
        theme.text(surface, "Fullscreen", (cx - 40, 420), 28, theme.PARCHMENT, anchor="midright")
        rect = self.controls["fullscreen"]
        theme.button(surface, rect, "On" if settings["fullscreen"] else "Off", rect.collidepoint(mouse))
        theme.text(surface, "Your battles", (cx - 40, 490), 28, theme.PARCHMENT, anchor="midright")
        rect = self.controls["battles"]
        label = {"ask": "Ask each time", "fight": "Always lead", "auto": "Always auto"}[settings["battles"]]
        theme.button(surface, rect, label, rect.collidepoint(mouse))
        if not self.app.audio.enabled:
            theme.text(surface, "No sound device was found: the game is silent.", (cx, 540), 18, theme.TEXT_DIM,
                       anchor="center")
        theme.button(surface, self.back_rect, "Back", self.back_rect.collidepoint(mouse))


class PauseMenu:
    """Shown over the campaign: resume, save, load, settings, main menu, quit."""

    LABELS = ("Resume", "Save Game", "Load Game", "Settings", "Main Menu", "Quit to Desktop")

    def __init__(self, app, campaign):
        self.app = app
        self.campaign = campaign
        self.buttons = _button_column(self.LABELS, 200, width=300, height=44, gap=12)
        self.buttons = [(rect.move(-(theme.WINDOW_SIZE[0] - theme.MAP_RECT.width) // 2, 0), label)
                        for rect, label in self.buttons]

    def handle(self, event):
        """Returns True when the menu should close."""
        if _escape(event):
            return True
        if not _clicked(event):
            return False
        for rect, label in self.buttons:
            if rect.collidepoint(event.pos):
                self.app.audio.play("click")
                if label == "Resume":
                    return True
                if label == "Save Game":
                    self.app.scene = SlotScreen(self.app, "save", back=self.campaign)
                elif label == "Load Game":
                    self.app.scene = SlotScreen(self.app, "load", back=self.campaign)
                elif label == "Settings":
                    self.app.scene = SettingsScreen(self.app, back=self.campaign)
                elif label == "Main Menu":
                    self.app.main_menu()
                else:
                    self.app.quit()
                return False
        return False

    def draw(self, surface, mouse):
        veil = pygame.Surface(theme.MAP_RECT.size, pygame.SRCALPHA)
        veil.fill((10, 8, 6, 170))
        surface.blit(veil, theme.MAP_RECT)
        box = self.buttons[0][0].unionall([r for r, _ in self.buttons]).inflate(60, 110).move(0, -20)
        theme.frame(surface, box)
        theme.ribbon(surface, (box.centerx, box.y + 4), "Paused", 28, width=240)
        for rect, label in self.buttons:
            theme.button(surface, rect, label, rect.collidepoint(mouse))
