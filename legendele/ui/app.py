"""Window, main loop and the two screens: faction selection and the campaign map."""

import pygame

from ..game import Game, GameData, MoveError
from . import theme
from .assets import Assets
from .map_view import MapView
from .panel import Panel
from .reports import concerns_player, draw_game_over, draw_report

TITLE = "Legends of the Carpathians"


class FactionSelect:
    """Opening screen: the map in the background and one card per playable faction."""

    def __init__(self, app):
        self.app = app
        data = app.data
        self.background = MapView(Game.new(data, self._playable()[0]), app.assets)
        self.cards = []
        width, gap = 280, 20
        left = (theme.WINDOW_SIZE[0] - (4 * width + 3 * gap)) // 2
        for i, fid in enumerate(self._playable()):
            self.cards.append((pygame.Rect(left + i * (width + gap), 250, width, 300), fid))

    def _playable(self):
        return [f for f, d in self.app.data.factions.items() if d["playable"]]

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, fid in self.cards:
                if rect.collidepoint(event.pos):
                    self.app.start_campaign(fid)

    def draw(self, surface):
        data = self.app.data
        surface.fill(theme.PANEL_BG)
        backdrop = pygame.Surface(self.background.size)
        self.background.draw(backdrop)
        surface.blit(backdrop, backdrop.get_rect(centerx=theme.WINDOW_SIZE[0] // 2))
        shade = pygame.Surface(theme.WINDOW_SIZE, pygame.SRCALPHA)
        shade.fill((20, 14, 10, 170))
        surface.blit(shade, (0, 0))
        cx = theme.WINDOW_SIZE[0] // 2
        theme.text(surface, TITLE, (cx, 120), 72, theme.GOLD, anchor="center", shadow=theme.INK)
        theme.text(surface, "Choose the legend you will lead", (cx, 180), 28, theme.PARCHMENT, anchor="center")
        mouse = pygame.mouse.get_pos()
        for rect, fid in self.cards:
            f = data.factions[fid]
            color = tuple(f["color"])
            hovered = rect.collidepoint(mouse)
            pygame.draw.rect(surface, (58, 46, 36) if hovered else theme.PANEL_BG, rect, border_radius=6)
            pygame.draw.rect(surface, color, rect, 3 if hovered else 2, border_radius=6)
            banner = self.app.assets.get(f"army_{fid}", color)
            surface.blit(banner, banner.get_rect(midtop=(rect.centerx, rect.y + 18)))
            theme.text(surface, f["name"], (rect.centerx, rect.y + 70), 30, color, anchor="midtop")
            y = rect.y + 104
            for line in theme.wrap(f["description"], 19, rect.width - 32):
                theme.text(surface, line, (rect.x + 16, y), 19)
                y += 20
            mastery = ", ".join(data.terrain[t]["name"] for t in f["terrain_mastery"]) or "none (strong cities)"
            theme.text(surface, f"At home in: {mastery}", (rect.x + 16, rect.bottom - 52), 18, theme.TEXT_DIM)
            theme.text(surface, f"Capital: {next(p['name'] for p in data.provinces if p['id'] == f['capital'])}",
                       (rect.x + 16, rect.bottom - 30), 18, theme.TEXT_DIM)


class Campaign:
    def __init__(self, app, faction, seed=None):
        self.app = app
        self.game = Game.new(app.data, faction, seed=seed)
        self.map = MapView(self.game, app.assets)
        self.panel = Panel(self.game, app.assets)
        self.selected_army = None
        self.selected_province = None
        self.hovered = None
        self.reports = []  # pop-ups waiting to be read, oldest first
        self.menu_rect = pygame.Rect(theme.MAP_RECT.right - 180, 10, 164, 36)

    # --- input -----------------------------------------------------------------------------

    def handle(self, event):
        if self.reports:
            closes = (event.type == pygame.MOUSEBUTTONDOWN or
                      event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                                                                     pygame.K_SPACE, pygame.K_ESCAPE))
            if closes:
                self.reports.pop(0)
            return
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.map.province_at(event.pos) if theme.MAP_RECT.collidepoint(event.pos) else None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.game.over and self.menu_rect.collidepoint(event.pos):
                self.app.scene = FactionSelect(self.app)
            elif self.panel.end_turn_rect.collidepoint(event.pos):
                self.end_turn()
            elif self.panel.assault_rect and self.panel.assault_rect.collidepoint(event.pos):
                self.assault()
            elif theme.MAP_RECT.collidepoint(event.pos):
                self.click_map(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.deselect()
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.end_turn()
            elif event.key == pygame.K_ESCAPE:
                self.deselect()
            elif event.key == pygame.K_TAB:
                self.select_next_army()

    def click_map(self, pos):
        game = self.game
        army_id = self.map.army_at(pos)
        province = self.map.province_at(pos)
        army = game.armies.get(self.selected_army)
        if army and army.faction == game.player and province in self.reach():
            self._act(lambda: game.move_army(army.id, province))
            self.selected_province = None
            return
        if army_id is not None:
            self.selected_army = army_id
            self.selected_province = game.armies[army_id].province
        else:
            self.selected_army = None
            self.selected_province = province

    def assault(self):
        army = self.game.armies.get(self.selected_army)
        if army is not None:
            self._act(lambda: self.game.assault(army.id))

    def _act(self, action):
        try:
            events = action()
        except MoveError:
            return
        self._report(events)
        if self.selected_army not in self.game.armies:
            self.deselect()

    def _report(self, events):
        self.reports += [e for e in events if concerns_player(self.game, e)]

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

    def end_turn(self):
        if self.game.over:
            return
        start = len(self.game.events)
        self.game.end_turn()
        self._report(self.game.events[start:])
        if self.selected_army not in self.game.armies:
            self.deselect()

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
        if self.reports:
            draw_report(surface, self.game, self.app.assets, self.reports[0])
        elif self.game.over:
            draw_game_over(surface, self.game, self.menu_rect, mouse)


class App:
    def __init__(self, data=None):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode(theme.WINDOW_SIZE)
        self.data = data or GameData.load()
        self.assets = Assets()
        self.scene = FactionSelect(self)
        self.clock = pygame.time.Clock()

    def start_campaign(self, faction, seed=None):
        self.scene = Campaign(self, faction, seed)

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                self.scene.handle(event)
            self.scene.draw(self.screen)
            pygame.display.flip()
            self.clock.tick(60)

    def screenshot(self, path):
        self.scene.draw(self.screen)
        pygame.image.save(self.screen, str(path))
