"""Window, main loop and the campaign screens (faction selection and the campaign map).

The menus (title screen, save/load, settings, pause) live in menus.py.
"""

import pygame

from .. import profile
from ..game import (Abduction, Battle, Captured, DiplomacyChange, Eliminated, Game, GameData, MoveError, Proposal,
                    Rebellion, SiegeStarted, Victory, diplomacy)
from ..game.save import load_game
from . import map_view, theme
from .assets import Assets
from .audio import Audio
from .battle_screen import fight
from .diplomacy_dialog import DiplomacyDialog
from .map_view import MapView
from .menus import MainMenu, PauseMenu
from .panel import Panel
from .province_dialog import ProvinceDialog
from .reports import ACCEPT_RECT, DECLINE_RECT, concerns_player, draw_game_over, draw_report

TITLE = "Legends of the Carpathians"


class FactionSelect:
    """New campaign: the map in the background and one card per playable faction."""

    music = "menu"

    def __init__(self, app):
        self.app = app
        self.cards = []
        width, gap = 280, 20
        left = (theme.WINDOW_SIZE[0] - (4 * width + 3 * gap)) // 2
        for i, fid in enumerate(self._playable()):
            self.cards.append((pygame.Rect(left + i * (width + gap), 200, width, 410), fid))
        self.back_rect = pygame.Rect(theme.WINDOW_SIZE[0] // 2 - 100, 640, 200, 44)

    def _playable(self):
        return [f for f, d in self.app.data.factions.items() if d["playable"]]

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.main_menu()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_rect.collidepoint(event.pos):
                self.app.audio.play("click")
                self.app.main_menu()
            for rect, fid in self.cards:
                if rect.collidepoint(event.pos):
                    self.app.audio.play("recruit")
                    self.app.start_campaign(fid)

    def draw(self, surface):
        data = self.app.data
        surface.fill(theme.PANEL_BG)
        backdrop = self.app.backdrop()
        surface.blit(backdrop, backdrop.get_rect(centerx=theme.WINDOW_SIZE[0] // 2))
        shade = pygame.Surface(theme.WINDOW_SIZE, pygame.SRCALPHA)
        shade.fill((20, 14, 10, 170))
        surface.blit(shade, (0, 0))
        cx = theme.WINDOW_SIZE[0] // 2
        theme.text(surface, TITLE, (cx, 90), 72, theme.GOLD, anchor="center", shadow=theme.INK)
        theme.text(surface, "Choose the legend you will lead", (cx, 150), 28, theme.PARCHMENT, anchor="center")
        mouse = pygame.mouse.get_pos()
        for rect, fid in self.cards:
            f = data.factions[fid]
            color = tuple(f["color"])
            hovered = rect.collidepoint(mouse)
            pygame.draw.rect(surface, (58, 46, 36) if hovered else theme.PANEL_BG, rect, border_radius=6)
            pygame.draw.rect(surface, color, rect, 3 if hovered else 2, border_radius=6)
            banner = self.app.assets.get(f"army_{fid}", color, 4)
            surface.blit(banner, banner.get_rect(midtop=(rect.centerx, rect.y + 14)))
            theme.text(surface, f["name"], (rect.centerx, rect.y + 76), 30, color, anchor="midtop")
            y = rect.y + 110
            for line in theme.wrap(f["description"], 19, rect.width - 32):
                theme.text(surface, line, (rect.x + 16, y), 19)
                y += 20
            y += 10
            for line in theme.wrap(f["legend"], 18, rect.width - 32):
                theme.text(surface, line, (rect.x + 16, y), 18, theme.GOLD)
                y += 19
            mastery = ", ".join(data.terrain[t]["name"] for t in f["terrain_mastery"]) or "none (strong cities)"
            theme.text(surface, f"At home in: {mastery}", (rect.x + 16, rect.bottom - 52), 18, theme.TEXT_DIM)
            theme.text(surface, f"Capital: {next(p['name'] for p in data.provinces if p['id'] == f['capital'])}",
                       (rect.x + 16, rect.bottom - 30), 18, theme.TEXT_DIM)
        theme.button(surface, self.back_rect, "Back", self.back_rect.collidepoint(mouse))


# Which sound a batch of events makes (the first match wins, so a battle drowns out a siege).
def event_sound(game, events):
    for kind, sound in ((Victory, None), (Eliminated, None), (Battle, "battle"), (Rebellion, "alarm"),
                        (DiplomacyChange, None), (Abduction, "coins"), (Captured, None), (Proposal, "select"),
                        (SiegeStarted, "march")):
        for e in events:
            if not isinstance(e, kind):
                continue
            if isinstance(e, Victory):
                return "victory" if e.faction == game.player else "defeat"
            if isinstance(e, Eliminated):
                return "defeat" if e.faction == game.player else "alarm"
            if isinstance(e, DiplomacyChange):
                return "alarm" if e.kind in ("war", "break") else "peace"
            if isinstance(e, Captured):
                return "alarm" if e.previous == game.player else "recruit"
            return sound
    return None


class Campaign:
    def __init__(self, app, faction=None, seed=None, game=None):
        self.app = app
        self.game = game or Game.new(app.data, faction, seed=seed)
        self.game.fight_hook = lambda g, attackers, defenders, pid, kind: fight(app, g, attackers, defenders, pid, kind)
        self.music = self.game.player
        self.map = MapView(self.game, app.assets)
        self.panel = Panel(self.game, app.assets)
        self.selected_army = None
        self.selected_province = None
        self.hovered = None
        self.reports = list(self.game.proposals)  # pop-ups waiting to be read (envoys from a loaded game too)
        self.dialog = None  # the province or diplomacy window, while open
        self._dialog_from = 0
        self.pause = None  # the pause menu, while open
        self.menu_rect = pygame.Rect(theme.MAP_RECT.right - 180, 10, 164, 36)
        self.dragging = None  # "map" (middle button) or "minimap" (left button) while the view is dragged

    # --- input -----------------------------------------------------------------------------

    def handle(self, event):
        if self.reports:
            if isinstance(self.reports[0], Proposal):
                self._answer(event)
                return
            closes = (event.type == pygame.MOUSEBUTTONDOWN or
                      event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                                                     pygame.K_SPACE, pygame.K_ESCAPE))
            if closes:
                self.reports.pop(0)
            return
        if self.pause:
            if self.pause.handle(event):
                self.pause = None
            return
        if self.dialog:
            if self.dialog.handle(event):
                self.dialog = None
                self._report(self.game.events[self._dialog_from:])  # what we did in there
            return
        if event.type == pygame.MOUSEMOTION:
            if self.dragging == "map":
                self.map.scroll(-event.rel[0], -event.rel[1])
            elif self.dragging == "minimap":
                self.map.center_on(*self.map.minimap_to_world(event.pos))
            self.hovered = self.map.province_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button in (1, 2):
            self.dragging = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            self.dragging = "map"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.map.on_minimap(event.pos):
            self.dragging = "minimap"
            self.map.center_on(*self.map.minimap_to_world(event.pos))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._click(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.deselect()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.end_turn()
            elif event.key == pygame.K_ESCAPE:
                if self.selected_army is None and self.selected_province is None:
                    self.open_pause()
                self.deselect()
            elif event.key == pygame.K_TAB:
                self.select_next_army()
            elif event.key in (pygame.K_HOME, pygame.K_c):
                self.center_on_capital()
            elif event.key == pygame.K_m:
                self.open_province()
            elif event.key == pygame.K_d:
                self.open_diplomacy()

    def _click(self, pos):
        panel = self.panel
        if self.game.over and self.menu_rect.collidepoint(pos):
            self.app.main_menu()
        elif panel.menu_rect.collidepoint(pos):
            self.open_pause()
        elif panel.end_turn_rect.collidepoint(pos):
            self.end_turn()
        elif panel.diplomacy_rect.collidepoint(pos):
            self.open_diplomacy()
        elif panel.assault_rect and panel.assault_rect.collidepoint(pos):
            self.assault()
        elif panel.abduct_rect and panel.abduct_rect.collidepoint(pos):
            army_id = self.selected_army
            self._act(lambda: self.game.abduct(army_id))
        elif panel.merge_rect and panel.merge_rect.collidepoint(pos):
            self.game.merge(self.selected_army)
            self.app.audio.play("click")
        elif panel.manage_rect and panel.manage_rect.collidepoint(pos):
            self.open_province()
        elif theme.MAP_RECT.collidepoint(pos):
            self.click_map(pos)

    def click_map(self, pos):
        game = self.game
        army_id = self.map.army_at(pos)
        province = self.map.province_at(pos)
        army = game.armies.get(self.selected_army)
        reach = self.reach()
        if army and army.faction == game.player and province in reach:
            route = [army.province, *reach[province].path]
            events = self._act(lambda: game.move_army(army.id, province))
            if events is not None and army.id in game.armies:
                # slide the banner to where it ended up (a beaten army falls back along the road)
                end = route.index(army.province) + 1 if army.province in route else len(route)
                self.map.march(army.id, route[:end])
                if not events:
                    self.app.audio.play("march")
            self.selected_province = None
            return
        if army_id is not None:
            self.selected_army = army_id
            self.selected_province = game.armies[army_id].province
            self.app.audio.play("select")
        else:
            self.selected_army = None
            self.selected_province = province

    def assault(self):
        army = self.game.armies.get(self.selected_army)
        if army is not None:
            self._act(lambda: self.game.assault(army.id))

    def _act(self, action):
        """Run a game action; returns its events (None if it was refused)."""
        try:
            events = action()
        except MoveError:
            return None
        self._report(events)
        if self.selected_army not in self.game.armies:
            self.deselect()
        return events

    def _report(self, events):
        self.reports += [e for e in events if concerns_player(self.game, e)]
        sound = event_sound(self.game, events)
        if sound:
            self.app.audio.play(sound)

    def open_pause(self):
        self.pause = PauseMenu(self.app, self)

    def open_diplomacy(self):
        if not self.game.over:
            self.dialog = DiplomacyDialog(self.game, self.app.assets)
            self._dialog_from = len(self.game.events)

    def _answer(self, event):
        offer = self.reports[0]
        accept = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            accept = True if ACCEPT_RECT.collidepoint(event.pos) else False if DECLINE_RECT.collidepoint(event.pos) else None
        elif event.type == pygame.KEYDOWN:
            accept = {pygame.K_y: True, pygame.K_n: False}.get(event.key)
        if accept is None:
            return
        self.reports.pop(0)
        if offer in self.game.proposals:
            start = len(self.game.events)
            diplomacy.answer(self.game, offer, accept)
            self._report(self.game.events[start:])

    def open_province(self):
        p = self.game.provinces.get(self.selected_province)
        if p is not None and p.owner == self.game.player and not self.game.over:
            self.dialog = ProvinceDialog(self.game, p.id, self.app.audio, self.app.assets)
            self._dialog_from = len(self.game.events)

    def deselect(self):
        self.selected_army = None
        self.selected_province = None

    def select_next_army(self):
        mine = [a for a in self.game.armies_of(self.game.player) if a.moves_left > 0] or \
            self.game.armies_of(self.game.player)
        if not mine:
            return
        ids = [a.id for a in mine]
        nxt = ids[(ids.index(self.selected_army) + 1) % len(ids)] if self.selected_army in ids else ids[0]
        self.selected_army = nxt
        self.selected_province = self.game.armies[nxt].province
        self.center_on(self.selected_province)

    def center_on(self, pid):
        p = self.game.provinces[pid]
        self.map.center_on(p.x, p.y + 20)

    def center_on_capital(self):
        capital = self.game.data.factions[self.game.player]["capital"]
        if capital in self.game.provinces:
            self.center_on(capital)

    def update(self, dt):
        """Scroll the map with the arrow keys or with the mouse at its edges."""
        if self.reports or self.pause or self.dialog or self.dragging:
            return
        keys = pygame.key.get_pressed()
        dx = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
        dy = keys[pygame.K_DOWN] - keys[pygame.K_UP]
        if pygame.mouse.get_focused():
            x, y = pygame.mouse.get_pos()
            area = self.map.rect
            if area.collidepoint(x, y) and not self.map.on_minimap((x, y)):
                dx += (x >= area.right - map_view.EDGE) - (x < area.left + map_view.EDGE)
                dy += (y >= area.bottom - map_view.EDGE) - (y < area.top + map_view.EDGE)
        dx, dy = max(-1, min(1, dx)), max(-1, min(1, dy))
        if dx or dy:
            step = map_view.SCROLL_SPEED * dt
            self.map.scroll(dx * step, dy * step)
            self.hovered = self.map.province_at(pygame.mouse.get_pos())

    def end_turn(self):
        if self.game.over:
            return
        start = len(self.game.events)
        self.game.end_turn()
        self.app.audio.play("turn")
        self._report(self.game.events[start:])
        if self.selected_army not in self.game.armies:
            self.deselect()
        if not self.game.over:
            try:
                profile.save(self.game, profile.AUTOSAVE)
            except OSError:
                pass  # a full disk must not stop the war

    # --- drawing ---------------------------------------------------------------------------

    def reach(self):
        army = self.game.armies.get(self.selected_army)
        if army is None or army.faction != self.game.player or self.game.over:
            return {}
        return self.game.reachable(army)

    def draw(self, surface):
        reach = self.reach()
        path = None
        target = self.hovered if self.hovered in reach else None
        if target:
            army = self.game.armies[self.selected_army]
            path = [army.province, *reach[target].path]
        self.map.draw(surface, hovered=self.hovered, selected_province=self.selected_province,
                      selected_army=self.selected_army, reach=reach, path=path)
        info = self.hovered if self.selected_army is None and self.hovered else self.selected_province
        mouse = pygame.mouse.get_pos()
        self.panel.draw(surface, province=info, army=self.game.armies.get(self.selected_army), target=target,
                        mouse=mouse)
        if self.dialog:
            self.dialog.draw(surface, mouse)
        if self.pause:
            self.pause.draw(surface, mouse)
        elif self.reports:
            draw_report(surface, self.game, self.app.assets, self.reports[0], mouse)
        elif self.game.over:
            draw_game_over(surface, self.game, self.menu_rect, mouse)


class App:
    def __init__(self, data=None):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption(TITLE)
        self.settings = profile.load_settings()
        self.screen = None
        self.apply_display()
        self.data = data or GameData.load()
        self.assets = Assets()
        self.audio = Audio(self.settings)
        self._backdrop = None
        self.running = True
        self.scene = MainMenu(self)
        self.clock = pygame.time.Clock()

    # --- scenes ----------------------------------------------------------------------------

    @property
    def scene(self):
        return self._scene

    @scene.setter
    def scene(self, scene):
        self._scene = scene
        if getattr(scene, "music", None):
            self.audio.music(scene.music)

    def main_menu(self):
        self.scene = MainMenu(self)

    def new_campaign(self):
        self.scene = FactionSelect(self)

    def start_campaign(self, faction, seed=None):
        self.scene = Campaign(self, faction, seed)

    def load_slot(self, slot):
        game = load_game(self.data, profile.save_path(slot))
        self.scene = Campaign(self, game=game)

    def quit(self):
        self.running = False

    def backdrop(self):
        """The bare map, drawn once, behind the menus."""
        if self._backdrop is None:
            first = next(f for f, d in self.data.factions.items() if d["playable"])
            view = MapView(Game.new(self.data, first, seed=0), self.assets)
            world = pygame.Surface(view.size)
            view.draw_world(world)
            scale = max(w / s for w, s in zip(theme.WINDOW_SIZE, view.size))
            world = pygame.transform.smoothscale(world, [round(s * scale) for s in view.size])
            self._backdrop = pygame.Surface(theme.WINDOW_SIZE)
            self._backdrop.blit(world, world.get_rect(center=self._backdrop.get_rect().center))
        return self._backdrop

    def apply_display(self):
        flags = pygame.FULLSCREEN | pygame.SCALED if self.settings["fullscreen"] else 0
        self.screen = pygame.display.set_mode(theme.WINDOW_SIZE, flags)

    # --- loop ------------------------------------------------------------------------------

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                self.scene.handle(event)
            self.audio.update()
            dt = self.clock.get_time() / 1000
            if hasattr(self.scene, "update"):
                self.scene.update(min(dt, 0.1))
            self.scene.draw(self.screen)
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()

    def screenshot(self, path):
        self.scene.draw(self.screen)
        pygame.image.save(self.screen, str(path))
