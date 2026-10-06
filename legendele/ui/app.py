"""Window, main loop and the campaign screens (faction selection and the campaign map).

The menus (title screen, save/load, settings, pause) live in menus.py.
"""

import pygame

from .. import profile
from ..game import (Abduction, Battle, Captured, DiplomacyChange, Eliminated, Game, GameData, MoveError, Proposal,
                    Raid, Rebellion, SiegeStarted, Tale, Victory, diplomacy,
                    agents, foreign)
from ..game import achievements, start
from ..game.economy import DIFFICULTY
from ..game.state import Reach
from ..game.save import load_game
from . import icon, map_view, theme, tips
from .assets import Assets
from .audio import Audio
from .battle_screen import fight
from .diplomacy_dialog import DiplomacyDialog
from .foreign_dialog import ForeignDialog
from .map_view import MapView
from .legends_dialog import LegendsDialog
from .menus import MainMenu, PauseMenu
from .panel import Panel
from .province_dialog import ProvinceDialog
from .reports import (ACCEPT_RECT, DECLINE_RECT, EndScreen, TurnSummary, concerns_player, draw_game_over, draw_report,
                      tale_choice_rects)
from .techs_dialog import TechsDialog
from .tutorial import Tutorial

TITLE = "Legends of the Carpathians"
TOAST_MS = 5000  # how long an achievement stays announced


class FactionSelect:
    """New campaign: the map in the background, one card per playable faction and the start options."""

    music = "menu"
    CARD_W, CARD_H, GAP = 400, 200, 14

    def __init__(self, app):
        self.app = app
        self.cards = []
        cols = 3
        left = (theme.WINDOW_SIZE[0] - (cols * self.CARD_W + (cols - 1) * self.GAP)) // 2
        for i, fid in enumerate(self._playable()):
            col, row = i % cols, i // cols
            self.cards.append((pygame.Rect(left + col * (self.CARD_W + self.GAP), 150 + row * (self.CARD_H + self.GAP),
                                           self.CARD_W, self.CARD_H), fid))
        widths, gap = [120] + [210] * 5, 10
        x = (theme.WINDOW_SIZE[0] - sum(widths) - gap * (len(widths) - 1)) // 2
        self.option_rects = []  # Back, then the options (see _option_list)
        for w in widths:
            self.option_rects.append(pygame.Rect(x, 640, w, 44))
            x += w + gap
        self.back_rect = self.option_rects[0]

    def _playable(self):
        return [f for f, d in self.app.data.factions.items() if d["playable"]]

    @property
    def start(self):
        return {**start.DEFAULTS, **self.app.settings.get("start", {})}

    def _set(self, key, value):
        settings = self.app.settings
        settings["start"] = {**self.start, key: value}
        profile.store_settings(settings)

    def _cycle(self, values, current):
        values = list(values)
        return values[(values.index(current) + 1) % len(values)] if current in values else values[0]

    def _difficulty(self):
        settings = self.app.settings
        settings["difficulty"] = self._cycle(DIFFICULTY, settings.get("difficulty", "normal"))
        profile.store_settings(settings)

    def handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.app.main_menu()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, (_, action, _) in zip(self.option_rects, self._option_list()):
                if rect.collidepoint(event.pos):
                    self.app.audio.play("click")
                    action()
                    return
            for rect, fid in self.cards:
                if rect.collidepoint(event.pos):
                    self.app.audio.play("recruit")
                    self.app.start_campaign(fid, options=self.start)

    def _option_list(self):
        o = self.start
        level = DIFFICULTY[self.app.settings.get("difficulty", "normal")]
        rivals = len(self._playable()) - 1
        era = start.ERAS[o["era"]]
        name, share = start.VICTORY[o["victory"]]
        need = round(len(self.app.data.provinces) * share)
        return [
            ("Back", self.app.main_menu, None),
            (f"Difficulty: {level['name']}", self._difficulty,
             ["Difficulty", "Click to change.",
              (f"The other legends earn {round(level['ai_income'] * 100)}% of their taxes and start with "
               f"{level['ai_gold']} gold; you start with {level['player_gold']}.", theme.TEXT_DIM)]),
            (f"Rivals: {o['rivals']}", lambda: self._set("rivals", o["rivals"] % rivals + 1),
             ["Rivals", "How many other legends take part (chosen at random).",
              ("The lands of those who sit the war out are held by the Rebels.", theme.TEXT_DIM)]),
            ("Homelands: " + ("shuffled" if o["shuffle"] else "historic"), lambda: self._set("shuffle", not o["shuffle"]),
             ["Homelands", "Historic: every legend starts in its own lands.",
              ("Shuffled: the legends draw lots for the homelands, capitals and all.", theme.TEXT_DIM)]),
            (f"Start: {o['era']}", lambda: self._set("era", self._cycle(start.ERAS, o["era"])),
             [era["name"], era["summary"]]),
            (name, lambda: self._set("victory", self._cycle(start.VICTORY, o["victory"])),
             ["Length of the war", f"Conquest needs {need} of {len(self.app.data.provinces)} provinces.",
              ("Holding the Heart of the Mountains still wins too.", theme.TEXT_DIM)]),
        ]

    def draw(self, surface):
        data = self.app.data
        surface.fill(theme.PANEL_BG)
        backdrop = self.app.backdrop()
        surface.blit(backdrop, backdrop.get_rect(centerx=theme.WINDOW_SIZE[0] // 2))
        shade = pygame.Surface(theme.WINDOW_SIZE, pygame.SRCALPHA)
        shade.fill((20, 14, 10, 170))
        surface.blit(shade, (0, 0))
        cx = theme.WINDOW_SIZE[0] // 2
        theme.outlined(surface, TITLE, (cx, 62), 52, theme.GOLD, width=3)
        theme.outlined(surface, "Choose the legend you will lead", (cx, 114), 24, theme.PARCHMENT, style="italic")
        mouse = pygame.mouse.get_pos()
        shuffled = self.start["shuffle"]
        for rect, fid in self.cards:
            f = data.factions[fid]
            color = tuple(f["color"])
            hovered = rect.collidepoint(mouse)
            inner = theme.frame(surface, rect, accent=color)
            if hovered:
                pygame.draw.rect(surface, theme.GOLD_LIGHT, rect.inflate(4, 4), 2)
            banner = self.app.assets.get(f"army_{fid}", color, 3)
            surface.blit(banner, banner.get_rect(midtop=(inner.x + 36, inner.y + 10)))
            x, width = inner.x + 76, inner.right - inner.x - 86
            theme.outlined(surface, f["name"], (x, inner.y + 4), 24, color, anchor="topleft")
            y = inner.y + 34
            for line in theme.wrap(f["description"], 16, width)[:3]:
                theme.text(surface, line, (x, y), 16)
                y += 17
            y += 4
            for line in theme.wrap(f["legend"], 16, width)[:4]:
                theme.text(surface, line, (x, y), 16, theme.GOLD)
                y += 17
            mastery = ", ".join(data.terrain[t]["name"] for t in f["terrain_mastery"]) or "none"
            home = "drawn by lot" if shuffled else next(p["name"] for p in data.provinces if p["id"] == f["capital"])
            theme.text(surface, f"At home in: {mastery}  ·  Capital: {home}", (inner.x + 10, inner.bottom - 20), 15,
                       theme.TEXT_DIM)
            theme.tip(rect, [f["name"], f["description"], (f["legend"], theme.GOLD),
                             (f"Rival character: {f['ai']['personality']}. {f['ai']['summary']}", theme.TEXT_DIM)])
        for rect, (label, _, tip) in zip(self.option_rects, self._option_list()):
            theme.button(surface, rect, label, rect.collidepoint(mouse))
            if tip:
                theme.tip(rect, tip)


# Which sound a batch of events makes (the first match wins, so a battle drowns out a siege).
def event_sound(game, events):
    for kind, sound in ((Victory, None), (Eliminated, None), (Battle, "battle"), (Rebellion, "alarm"), (Raid, "alarm"),
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
    def __init__(self, app, faction=None, seed=None, game=None, options=None):
        self.app = app
        self.game = game or Game.new(app.data, faction, seed=seed,
                                     difficulty=app.settings.get("difficulty", "normal"), options=options)
        self.game.fight_hook = lambda g, attackers, defenders, pid, kind: fight(app, g, attackers, defenders, pid, kind)
        self.music = self.game.player
        self.map = MapView(self.game, app.assets)
        self.panel = Panel(self.game, app.assets)
        self.selected_army = None
        self.selected_agent = None
        self.selected_province = None
        self.hovered = None
        # pop-ups waiting to be read (envoys and tales from a loaded game too)
        self.reports = list(self.game.proposals) + list(self.game.pending_events)
        self.dialog = None  # the province or diplomacy window, while open
        self._dialog_from = 0
        self.pause = None  # the pause menu, while open
        self.menu_rect = pygame.Rect(theme.MAP_RECT.right - 180, 10, 164, 36)
        self.dragging = None  # "map" (middle button) or "minimap" (left button) while the view is dragged
        self.summary = None  # the season's news, shown once the pop-ups are read
        self.ending = None  # the chronicle of the war, once it is decided
        self.ending_seen = False
        self.tutorial = Tutorial(self) if game is None and app.settings.get("tutorial", True) else None
        self.chronicle_rect = pygame.Rect(theme.MAP_RECT.right - 360, 10, 164, 36)

    # --- input -----------------------------------------------------------------------------

    def handle(self, event):
        if self.reports:
            if isinstance(self.reports[0], Proposal):
                self._answer(event)
                return
            if isinstance(self.reports[0], Tale):
                self._choose(event)
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
        if self.ending:
            answer = self.ending.handle(event)
            if answer == "menu":
                self.app.main_menu()
            elif answer == "map":
                self.ending = None
            return
        if self.summary:
            answer = self.summary.handle(event)
            if answer:
                self.summary = None
                if answer != "close":
                    self.selected_army = None
                    self.selected_province = answer
                    self.center_on(answer)
            return
        if self.tutorial and not self.summary and not self.ending and self.tutorial.handle(event):
            self._tutorial_progress()
            return
        if self.dialog:
            if self.dialog.handle(event):
                switch = getattr(self.dialog, "switch", None)
                self.dialog = None
                if switch == "foreign":
                    self.open_foreign()
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
            elif event.key == pygame.K_f:
                self.open_foreign()
            elif event.key == pygame.K_t:
                self.open_traditions()
            elif event.key == pygame.K_l:
                self.open_legends()

    def _click(self, pos):
        panel = self.panel
        if self.game.over and self.menu_rect.collidepoint(pos):
            self.app.main_menu()
        elif self.game.over and self.chronicle_rect.collidepoint(pos):
            self.ending = EndScreen(self.game)
        elif panel.menu_rect.collidepoint(pos):
            self.open_pause()
        elif panel.end_turn_rect.collidepoint(pos):
            self.end_turn()
        elif panel.diplomacy_rect.collidepoint(pos):
            self.open_diplomacy()
        elif panel.traditions_rect.collidepoint(pos):
            self.open_traditions()
        elif panel.legends_rect.collidepoint(pos):
            self.open_legends()
        elif any(rect.collidepoint(pos) for rect, _ in panel.actions):
            next(action for rect, action in panel.actions if rect.collidepoint(pos))()
            self.app.audio.play("click")
            if self.selected_agent not in self.game.agents:
                self.selected_agent = None
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
        agent_id = self.map.agent_at(pos)
        army_id = self.map.army_at(pos)
        province = self.map.province_at(pos)
        agent = game.agents.get(self.selected_agent)
        if agent and agent.faction == game.player and province in self.reach() and agent_id is None:
            agents.move(game, agent.id, province)
            self.selected_province = province
            self.app.audio.play("march")
            return
        self.panel.feedback = None
        if agent_id is not None:
            self.selected_agent, self.selected_army = agent_id, None
            self.selected_province = game.agents[agent_id].province
            self.app.audio.play("select")
            return
        self.selected_agent = None
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
        self.app.achieve(achievements.campaign(self.game, events, profile.load_achievements()))

    def open_pause(self):
        self.pause = PauseMenu(self.app, self)

    def open_diplomacy(self):
        if not self.game.over:
            self.dialog = DiplomacyDialog(self.game, self.app.assets)
            self._dialog_from = len(self.game.events)

    def open_legends(self):
        if not self.game.over:
            self.dialog = LegendsDialog(self.game, self.app.assets)
            self._dialog_from = len(self.game.events)

    def open_traditions(self):
        if not self.game.over:
            self.dialog = TechsDialog(self.game, self.app.audio)
            self._dialog_from = len(self.game.events)

    def open_foreign(self):
        if not self.game.over:
            self.dialog = ForeignDialog(self.game, self.app.assets)
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

    def _choose(self, event):
        tale = self.reports[0]
        choices = self.game.data.events[tale.event]["choices"]
        index = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            index = next((i for i, r in enumerate(tale_choice_rects(len(choices))) if r.collidepoint(event.pos)), None)
        elif event.type == pygame.KEYDOWN and pygame.K_1 <= event.key < pygame.K_1 + len(choices):
            index = event.key - pygame.K_1
        if index is None:
            return
        self.reports.pop(0)
        if tale in self.game.pending_events:
            self._report(self.game.choose_event(tale, index))
            self.app.audio.play("click")

    def open_province(self):
        p = self.game.provinces.get(self.selected_province)
        if p is not None and p.owner == self.game.player and not self.game.over:
            self.dialog = ProvinceDialog(self.game, p.id, self.app.audio, self.app.assets)
            self._dialog_from = len(self.game.events)

    def deselect(self):
        self.selected_army = None
        self.selected_agent = None
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
        capital = self.game.capital_of(self.game.player)
        if capital in self.game.provinces:
            self.center_on(capital)

    def _tutorial_progress(self):
        self.tutorial.update()
        if self.tutorial.finished:
            self.tutorial = None
            self.app.settings["tutorial"] = False  # once is enough; the settings can bring it back
            profile.store_settings(self.app.settings)

    def update(self, dt):
        """Scroll the map with the arrow keys or with the mouse at its edges."""
        if self.reports or self.pause or self.dialog or self.dragging or self.summary:
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
        chronicle = len(self.game.log)
        self.game.end_turn()
        self.app.audio.play("turn")
        self._report(self.game.events[start:])
        if self.selected_army not in self.game.armies:
            self.deselect()
        news = [line for line in self.game.log[chronicle:] if not line.endswith(" begins.")]
        if news and not self.game.over and self.app.settings.get("turn_summary", True):
            self.summary = TurnSummary(self.game, news)
        if not self.game.over:
            try:
                profile.save(self.game, profile.AUTOSAVE)
            except OSError:
                pass  # a full disk must not stop the war

    # --- drawing ---------------------------------------------------------------------------

    def reach(self):
        agent = self.game.agents.get(self.selected_agent)
        if agent is not None:
            if agent.faction != self.game.player or self.game.over:
                return {}
            return {pid: Reach(cost, [pid]) for pid, cost in agents.reachable(self.game, agent).items()}
        army = self.game.armies.get(self.selected_army)
        if army is None or army.faction != self.game.player or self.game.over:
            return {}
        return self.game.reachable(army)

    def draw(self, surface):
        reach = self.reach()
        path = None
        target = self.hovered if self.hovered in reach else None
        if target and self.selected_agent in self.game.agents:
            path = [self.game.agents[self.selected_agent].province, target]
        elif target:
            army = self.game.armies[self.selected_army]
            path = [army.province, *reach[target].path]
        self.map.draw(surface, hovered=self.hovered, selected_province=self.selected_province,
                      selected_army=self.selected_army, reach=reach, path=path, selected_agent=self.selected_agent)
        for rect, army_id in self.map.army_rects:
            screen_rect = rect.move(self.map.to_screen((0, 0)))
            if self.map.rect.contains(screen_rect) and army_id in self.game.armies:
                theme.tip(screen_rect, tips.army(self.game, self.game.armies[army_id]))
        for land in self.game.data.map.get("foreign", []):
            power = next((fid for fid in foreign.powers(self.game)
                          if land["name"] in self.game.data.factions[fid]["foreign"]["lands"]), None)
            if power:
                f = self.game.data.factions[power]
                spot = pygame.Rect(0, 0, 380, 70)
                spot.center = self.map.to_screen((land["x"], land["y"]))
                theme.tip(spot.clip(self.map.rect), [land["name"], f["description"],
                                                     (f"Raids on you so far: {self.game.raided.get(power, {}).get(self.game.player, 0)}"
                                                      "  ·  Foreign courts: F", theme.TEXT_DIM)])
        theme.tip(self.map.minimap_rect, ["The whole map", "Click or drag here to look elsewhere. "
                                          "Arrows or the mouse at the edge scroll the map; Home returns to your capital."])
        info = self.hovered if self.selected_army is None and self.hovered else self.selected_province
        mouse = pygame.mouse.get_pos()
        self.panel.draw(surface, province=info, army=self.game.armies.get(self.selected_army), target=target,
                        mouse=mouse, agent=self.game.agents.get(self.selected_agent))
        if self.dialog:
            self.dialog.draw(surface, mouse)
        if self.pause:
            self.pause.draw(surface, mouse)
        elif self.reports:
            draw_report(surface, self.game, self.app.assets, self.reports[0], mouse)
        elif self.summary:
            self.summary.draw(surface, mouse)
        elif self.tutorial and not self.game.over:
            self._tutorial_progress()
            if self.tutorial:
                self.tutorial.draw(surface, mouse)
        elif self.game.over:
            if not self.ending_seen:
                self.ending_seen = True
                self.ending = EndScreen(self.game)
            draw_game_over(surface, self.game, self.menu_rect, mouse)
            theme.button(surface, self.chronicle_rect, "Chronicle", self.chronicle_rect.collidepoint(mouse))
            if self.ending:
                self.ending.draw(surface, mouse)


class App:
    def __init__(self, data=None):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption(TITLE)
        pygame.display.set_icon(icon.draw(64))
        self.settings = profile.load_settings()
        self.screen = None
        self.apply_display()
        self.data = data or GameData.load()
        self.assets = Assets()
        self.audio = Audio(self.settings)
        self._backdrop = None
        self.running = True
        self.toasts = []  # [Achievement, ms when it went up]: the achievements just earned
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

    def start_campaign(self, faction, seed=None, options=None):
        self.scene = Campaign(self, faction, seed, options=options)

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
            self.present(self.scene.draw)
            self.clock.tick(60)
        pygame.quit()

    def present(self, draw):
        """Draw a frame (with the achievements just earned and the tooltip under the mouse) and show it."""
        theme.clear_tips()
        draw(self.screen)
        self._draw_toasts(self.screen)
        if pygame.mouse.get_focused():
            theme.draw_tip(self.screen, pygame.mouse.get_pos())
        pygame.display.flip()

    # --- achievements ------------------------------------------------------------------------

    def achieve(self, ids):
        """Remember these achievements; the new ones are announced with a fanfare."""
        new = profile.unlock(ids)
        if new:
            by_id = {a.id: a for a in achievements.every(self.data)}
            now = pygame.time.get_ticks()
            self.toasts += [[by_id[i], now] for i in new if i in by_id]
            self.audio.play("fanfare")
        return new

    def _draw_toasts(self, surface):
        now = pygame.time.get_ticks()
        self.toasts = [t for t in self.toasts if now - t[1] < TOAST_MS]
        y = 14
        for achievement, since in self.toasts[:3]:
            box = pygame.Rect(0, 0, 440, 64)
            box.midtop = (theme.WINDOW_SIZE[0] // 2, y)
            inner = theme.frame(surface, box, accent=theme.GOLD)
            theme.star(surface, (inner.x + 24, inner.centery), 12)
            theme.text(surface, "Achievement: " + achievement.name, (inner.x + 48, inner.y + 6), 19, theme.GOLD)
            theme.text(surface, achievement.description, (inner.x + 48, inner.y + 30), 16, theme.PARCHMENT)
            y += box.height + 8

    def screenshot(self, path, tip_at=None):
        """Save the current screen; `tip_at` shows the tooltip at that point straight away."""
        theme.clear_tips()
        self.scene.draw(self.screen)
        if tip_at:
            theme.draw_tip(self.screen, tip_at, now=float("inf"))
        pygame.image.save(self.screen, str(path))
