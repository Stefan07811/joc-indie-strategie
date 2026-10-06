"""The real-time battle screen, and the question "lead it yourself, or auto-resolve?".

Both run their own small loop on top of the campaign (the campaign's rules call fight() in the
middle of a march or an assault), and return a BattleResult to the campaign.

Controls: first place your regiments in your deployment zone (drag them, or right-click to set the
selected ones down), then start the battle. Left-click or drag a box to select your regiments
(A selects all), right-click the ground to march there or an enemy to attack it, Q gives the
selected regiments their special order, H halts, Space pauses, F changes the speed. The mouse wheel
zooms in and out; the arrow keys, the mouse at the edge or the middle button move the view.
"""

import math
import random

import pygame

from ..game import battle
from ..game.realtime import FIELD_H, FIELD_W, GATES, WALL_X, WEATHER, Battlefield
from . import battle_art, painter, theme, tips

HUD = pygame.Rect(0, FIELD_H, theme.WINDOW_SIZE[0], theme.WINDOW_SIZE[1] - FIELD_H)
VIEW = pygame.Rect(0, 0, FIELD_W, FIELD_H)  # where the field is shown on the screen
STEP = 1 / 30
SPEEDS = (1, 2, 4)
SOUND_GAP = {"volley": 0.7, "gunshot": 0.35, "spell": 0.5, "thunder": 2.5}  # battle seconds between repeats
ZOOMS = (1.0, 1.5, 2.0)
PAN_SPEED = 600


def conditions(game, kind, rng=None):
    """The weather and the hour of a battle: (weather, night)."""
    rng = rng or random.Random()
    season = game.season
    roll = rng.random()
    if season == "Winter":
        weather = "snow" if roll < 0.7 else "fog" if roll < 0.8 else "clear"
    elif season in ("Spring", "Autumn"):
        weather = "rain" if roll < 0.25 else "fog" if roll < 0.4 else "clear"
    else:
        weather = "rain" if roll < 0.1 else "fog" if roll < 0.15 else "clear"
    night = rng.random() < (0.3 if kind == "assault" else 0.15)
    return weather, night


def describe(weather, night):
    return WEATHER[weather]["name"] + ("  ·  night" if night else "")


def fight(app, game, attackers, defenders, pid, kind):
    """The campaign's fight_hook: ask (or follow the settings), then fight in real time or not at all."""
    mode = app.settings.get("battles", "ask")
    if mode == "auto" or not app.running:
        return None
    weather, night = conditions(game, kind, game.rng)
    if mode == "ask" and not BattleQuestion(app, game, attackers, defenders, pid, kind, weather, night).run():
        return None
    player_side = 0 if attackers.faction == game.player else 1
    field = Battlefield(attackers, defenders, game.data.units, game.provinces[pid].terrain, kind, game.rng,
                        province=pid, player_side=player_side, weather=weather, night=night)
    result = BattleScreen(app, game, field).run()
    if result.winning_faction == game.player and not field.auto:
        app.achieve(["lead"])
    return result


def _title(game, pid, kind):
    name = game.provinces[pid].name if pid in game.provinces else pid
    return f"{'Assault on' if kind == 'assault' else 'Battle of'} {name}"


class BattleQuestion:
    BOX = pygame.Rect(0, 0, 620, 330)

    def __init__(self, app, game, attackers, defenders, pid, kind, weather="clear", night=False):
        self.app, self.game = app, game
        self.attackers, self.defenders, self.pid, self.kind = attackers, defenders, pid, kind
        self.weather, self.night = weather, night
        self.box = self.BOX.copy()
        self.box.center = theme.MAP_RECT.center
        self.lead_rect = pygame.Rect(self.box.x + 60, self.box.bottom - 80, 220, 46)
        self.auto_rect = pygame.Rect(self.box.right - 280, self.box.bottom - 80, 220, 46)
        self.backdrop = app.screen.copy()
        self.answer = None

    def handle(self, event):
        if event.type == pygame.KEYDOWN:
            self.answer = {pygame.K_b: True, pygame.K_RETURN: True, pygame.K_a: False, pygame.K_ESCAPE: False}.get(
                event.key, self.answer)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.lead_rect.collidepoint(event.pos):
                self.answer = True
            elif self.auto_rect.collidepoint(event.pos):
                self.answer = False

    def draw(self, surface):
        game = self.game
        surface.blit(self.backdrop, (0, 0))
        veil = pygame.Surface(theme.WINDOW_SIZE, pygame.SRCALPHA)
        veil.fill((10, 8, 6, 150))
        surface.blit(veil, (0, 0))
        box = self.box
        theme.frame(surface, box, accent=theme.DANGER)
        theme.ribbon(surface, (box.centerx, box.y + 4), _title(game, self.pid, self.kind), 26)
        a, d = self.attackers, self.defenders
        line = (f"{game.faction_name(a.faction)} ({len(a.regiments)} regiments)  against  "
                f"{game.faction_name(d.faction, True)} ({len(d.regiments)})")
        theme.text(surface, line, (box.centerx, box.y + 76), 20, theme.PARCHMENT, anchor="midtop")
        extra = [describe(self.weather, self.night)]
        for side, who in ((a, "Your" if a.faction == game.player else "Their"),
                          (d, "Your" if d.faction == game.player else "Their")):
            if side.late:
                extra.append(f"{who} reinforcements: {len(side.late)} regiments")
        if a.river:
            extra.append(f"across the {a.river}")
        if self.kind == "assault" and a.equipment:
            works = [w for w in ("ladders", "ram") if a.equipment.get(w)]
            extra.append("siege works: " + (" and ".join(works) if works else "none yet"))
        theme.text(surface, "  ·  ".join(extra), (box.centerx, box.y + 106), 18, theme.GOLD, anchor="midtop")
        wins, share = battle.predict(a, d, game.data.units, kind=self.kind)
        player_attacks = a.faction == game.player
        good = wins == player_attacks
        verdict = ("Forecast: " + ("victory" if good else "defeat") + " if the battle is auto-resolved")
        theme.text(surface, verdict, (box.centerx, box.y + 140), 20, theme.GOOD if good else theme.DANGER,
                   anchor="midtop")
        theme.text(surface, "Lead it yourself, or let your generals decide?", (box.centerx, box.y + 180), 20,
                   theme.TEXT_DIM, anchor="midtop")
        mouse = pygame.mouse.get_pos()
        theme.button(surface, self.lead_rect, "Lead the battle (B)", self.lead_rect.collidepoint(mouse))
        theme.button(surface, self.auto_rect, "Auto-resolve (A)", self.auto_rect.collidepoint(mouse))

    def run(self):
        self.app.audio.play("alarm")
        clock = pygame.time.Clock()
        while self.answer is None:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.app.quit()
                    return False
                self.handle(event)
            self.app.audio.update()
            self.app.present(self.draw)
            clock.tick(60)
        return self.answer


class BattleScreen:
    def __init__(self, app, game, field, title=None):
        self.app, self.game, self.field = app, game, field
        self.title = title or _title(game, field.province, field.kind)
        self.me = field.player_side
        self.deploying = self.me is not None
        self.selected = set()
        self.paused = True
        self.speed = 0
        self.drag = None  # where a selection box began (field coordinates)
        self.moving = None  # while deploying: (regiment ids, last field point) being dragged
        self.panning = False
        self.mouse = (0, 0)
        self.result = None
        self.clash_at = 0.0
        self.heard = {}  # sound -> battle time it was last played (so a volley is not a hundred volleys)
        self.notes_heard = 0
        self.shouts = []  # (unit id, words, until): special orders called out
        self.zoom = 1.0
        self.cam = [0.0, 0.0]  # the field point at the view's top-left corner
        self._carry = 0.0  # unspent time, simulated in fixed steps
        self.ground = battle_art.paint_field(field)  # the fallen are painted onto it as they fall
        self.canvas = pygame.Surface((FIELD_W, FIELD_H))
        names = [game.faction_name(s.faction) for s in field.sides]
        self.colors = [theme.faction_color(game, s.faction) for s in field.sides]
        self.troops = battle_art.Troops(field, game.data.units, self.colors, self.ground)
        self.effects = battle_art.Effects(field, game.data.units, self.troops)
        self.troops.update(0, self.effects)
        self.clouds = battle_art.clouds()
        self.sky = battle_art.Sky(field)
        self.vignette = painter._vignette(FIELD_W, FIELD_H)
        self._banners = {}
        self.names = names
        x = HUD.right - 16
        self.buttons = {}
        for name, width in (("withdraw", 120), ("auto", 140), ("speed", 70), ("pause", 110), ("ability", 190)):
            self.buttons[name] = pygame.Rect(x - width, HUD.y + 64, width, 36)
            x -= width + 8
        self.continue_rect = pygame.Rect(0, 0, 240, 50)
        self.continue_rect.center = (FIELD_W // 2, FIELD_H // 2 + 70)

    # --- the view ----------------------------------------------------------------------------

    def to_field(self, pos):
        return (self.cam[0] + pos[0] / self.zoom, self.cam[1] + pos[1] / self.zoom)

    def to_screen(self, pos):
        return ((pos[0] - self.cam[0]) * self.zoom, (pos[1] - self.cam[1]) * self.zoom)

    def _clamp_view(self):
        self.cam[0] = max(0.0, min(self.cam[0], FIELD_W - FIELD_W / self.zoom))
        self.cam[1] = max(0.0, min(self.cam[1], FIELD_H - FIELD_H / self.zoom))

    def zoom_at(self, pos, steps):
        """Zoom in (steps > 0) or out around a screen point."""
        i = max(0, min(len(ZOOMS) - 1, ZOOMS.index(self.zoom) + steps))
        anchor = self.to_field(pos)
        self.zoom = ZOOMS[i]
        self.cam = [anchor[0] - pos[0] / self.zoom, anchor[1] - pos[1] / self.zoom]
        self._clamp_view()

    def pan(self, dx, dy):
        self.cam[0] += dx / self.zoom
        self.cam[1] += dy / self.zoom
        self._clamp_view()

    # --- input -------------------------------------------------------------------------------

    def handle(self, event):
        f = self.field
        if f.over:
            if (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE)) or \
                    (event.type == pygame.MOUSEBUTTONDOWN and self.continue_rect.collidepoint(event.pos)):
                self.result = f.result
            return
        on_field = hasattr(event, "pos") and VIEW.collidepoint(event.pos)
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
            if self.panning:
                self.pan(-event.rel[0], -event.rel[1])
            elif self.moving:
                ids, _ = self.moving
                f.place(ids, *self.to_field(event.pos))
        elif event.type == pygame.MOUSEWHEEL:
            self.zoom_at(pygame.mouse.get_pos(), 1 if event.y > 0 else -1)
        elif event.type == pygame.KEYDOWN:
            self._key(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, rect in self.buttons.items():
                if rect.collidepoint(event.pos):
                    self._button(name)
                    return
            if on_field:
                spot = self.to_field(event.pos)
                mine = self._unit_at(spot, self.me)
                if self.deploying and mine is not None:
                    ids = self.selected if mine.id in self.selected else {mine.id}
                    self.selected = set(ids)
                    self.moving = (ids, spot)
                else:
                    self.drag = spot
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.moving:
                self.moving = None
            elif self.drag:
                self._select(self.drag, self.to_field(event.pos), pygame.key.get_mods() & pygame.KMOD_SHIFT)
                self.drag = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            self.panning = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self.panning = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and on_field:
            self._command(self.to_field(event.pos))

    def _key(self, key):
        f = self.field
        if key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER) and self.deploying:
            self.start()
        elif key == pygame.K_SPACE:
            self.paused = not self.paused
        elif key == pygame.K_f:
            self.speed = (self.speed + 1) % len(SPEEDS)
        elif key == pygame.K_h:
            f.order_halt(self.selected)
        elif key == pygame.K_q:
            self.special()
        elif key == pygame.K_a:
            self.selected = {u.id for u in f.standing(self.me)}
        elif key == pygame.K_ESCAPE:
            self.selected = set()
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.zoom_at(VIEW.center, 1)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.zoom_at(VIEW.center, -1)

    def start(self):
        """The regiments are in place: let battle begin."""
        self.deploying = False
        self.paused = False
        self.app.audio.play("horn")

    def special(self):
        used = self.field.use_ability(self.selected)
        for uid in used:
            u = self.field.unit(uid)
            self.shouts.append((uid, self.field.ability(u)["name"], self.field.time + 2.0))
        if used:
            self.app.audio.play("horn")

    def _button(self, name):
        f = self.field
        self.app.audio.play("click")
        if name == "pause":
            if self.deploying:
                self.start()
            else:
                self.paused = not self.paused
        elif name == "speed":
            self.speed = (self.speed + 1) % len(SPEEDS)
        elif name == "ability":
            self.special()
        elif name == "auto":
            self.deploying = False
            f.finish()
            self.troops.update(0.0, self.effects)  # the fallen of the rest of the fight
        elif name == "withdraw":
            self.deploying = False
            f.withdraw(self.me)
            self.paused = False

    def _unit_at(self, pos, side=None):
        best = None
        for u in self.field.units:
            if u.state not in ("ready", "routing") or (side is not None and u.side != side):
                continue
            d = math.hypot(u.x - pos[0], u.y - pos[1])
            if d <= 26 and (best is None or d < best[0]):
                best = (d, u)
        return best[1] if best else None

    def _select(self, start, end, add):
        rect = pygame.Rect(min(start[0], end[0]), min(start[1], end[1]), abs(end[0] - start[0]), abs(end[1] - start[1]))
        if rect.width < 6 and rect.height < 6:
            u = self._unit_at(end, self.me)
            chosen = {u.id} if u and u.ready else set()
        else:
            chosen = {u.id for u in self.field.standing(self.me) if rect.collidepoint(u.x, u.y)}
        self.selected = (self.selected | chosen) if add else chosen
        if chosen:
            self.app.audio.play("select")

    def _command(self, pos):
        if not self.selected:
            return
        if self.deploying:
            self.field.place(self.selected, *pos)
            return
        enemy = self._unit_at(pos, 1 - self.me)
        if enemy is not None:
            self.field.order_attack(self.selected, enemy.id)
        else:
            self.field.order_move(self.selected, *pos)
        self.app.audio.play("click")

    # --- time --------------------------------------------------------------------------------

    def update(self, dt):
        f = self.field
        self._scroll(dt)
        self.sky.update(dt)
        if f.over or self.paused or self.deploying:
            return
        self._carry += min(dt, 0.1) * SPEEDS[self.speed]
        before = f.time
        while self._carry >= STEP and not f.over:
            f.step(STEP)
            self._carry -= STEP
        self.troops.update(f.time - before, self.effects)
        self.effects.update(self.ground)
        self.selected = {i for i in self.selected if f.unit(i).ready}
        self.shouts = [s for s in self.shouts if s[2] > f.time]
        if any(u.fighting is not None for u in f.units) and f.time - self.clash_at > 2.5:
            self.clash_at = f.time
            self.app.audio.play("battle")
        for name in self.effects.sounds:
            if f.time - self.heard.get(name, -99) >= SOUND_GAP.get(name, 0.6):
                self.heard[name] = f.time
                self.app.audio.play(name)
        self.effects.sounds.clear()
        if len(f.notes) > self.notes_heard:
            if any("breaks a gate" in n for n in f.notes[self.notes_heard:]):
                self.app.audio.play("gate")
            self.notes_heard = len(f.notes)
        if f.over:
            won = (f.result.winner == "attacker") == (self.me == 0)
            self.app.audio.play("victory" if won else "defeat")

    def _scroll(self, dt):
        if self.zoom == 1.0:
            return
        keys = pygame.key.get_pressed()
        dx = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
        dy = keys[pygame.K_DOWN] - keys[pygame.K_UP]
        if pygame.mouse.get_focused():
            x, y = pygame.mouse.get_pos()
            if VIEW.collidepoint(x, y):
                dx += (x >= VIEW.right - 12) - (x < VIEW.left + 12)
                dy += (y >= VIEW.bottom - 12) - (y < VIEW.top + 12)
        if dx or dy:
            self.pan(max(-1, min(1, dx)) * PAN_SPEED * dt, max(-1, min(1, dy)) * PAN_SPEED * dt)

    def run(self):
        clock = pygame.time.Clock()
        self.app.audio.play("alarm")
        before = self.app.audio.wanted
        self.app.audio.music("battle")
        while self.result is None:
            dt = clock.tick(60) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.app.quit()
                    self.result = self.field.finish()
                    break
                self.handle(event)
            self.update(dt)
            self.app.audio.update()
            self.app.present(self.draw)
        if before:
            self.app.audio.music(before)
        return self.result

    # --- drawing -----------------------------------------------------------------------------

    def draw(self, surface):
        f = self.field
        c = self.canvas
        c.blit(self.ground, (0, 0))
        if self.deploying:
            self._zone(c)
        self._gates(c)
        for uid in self.selected:
            u = f.unit(uid)
            ring = pygame.Rect(0, 0, 64, 40)
            ring.center = (u.x, u.y + 2)
            pygame.draw.ellipse(c, theme.INK, ring.inflate(4, 4), 3)
            pygame.draw.ellipse(c, theme.HIGHLIGHT, ring, 2)
        self.effects.draw_shadows(c)
        sprites = self.troops.sprites(f.time)
        if f.ram and f.ram.alive:
            sprites.append(battle_art.ram_sprite(f.ram, self.colors[0]))
        for _, image, rect in sorted(sprites, key=lambda s: s[0]):
            c.blit(image, rect)
        self.effects.draw(c)
        self.sky.draw(c, f.time, [u for u in f.units if u.state in ("ready", "routing")])
        drift = int(f.time * 6) % FIELD_W
        c.blit(self.clouds, (drift - FIELD_W, 0))
        c.blit(self.clouds, (drift, 0))
        c.blit(self.vignette, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        for u in f.units:
            if u.state in ("ready", "routing"):
                self._banner(c, u)
        for uid, words, until in self.shouts:
            u = f.unit(uid)
            if u.state in ("ready", "routing"):
                theme.outlined(c, words, (u.x, u.y - 62 - (until - f.time) * 6), 18, theme.HIGHLIGHT)
        if self.drag:
            end = self.to_field(self.mouse)
            rect = pygame.Rect(min(self.drag[0], end[0]), min(self.drag[1], end[1]),
                               abs(end[0] - self.drag[0]), abs(end[1] - self.drag[1]))
            pygame.draw.rect(c, theme.HIGHLIGHT, rect, 1)
        if self.zoom == 1.0:
            surface.blit(c, VIEW)
        else:
            view = pygame.Rect(round(self.cam[0]), round(self.cam[1]), round(FIELD_W / self.zoom),
                               round(FIELD_H / self.zoom)).clip(c.get_rect())
            surface.blit(pygame.transform.smoothscale(c.subsurface(view), VIEW.size), VIEW)
        self._tips()
        self._hud(surface)
        if f.over:
            self._outcome(surface)
        elif self.deploying:
            theme.outlined(surface, "Place your regiments in the lit ground, then press Space to begin",
                           (FIELD_W // 2, 24), 22, theme.HIGHLIGHT)
        elif self.paused:
            theme.outlined(surface, "Paused: give your orders, then press Space", (FIELD_W // 2, 24), 24,
                           theme.HIGHLIGHT)

    def _tips(self):
        for u in self.field.units:
            if u.state not in ("ready", "routing"):
                continue
            x, y = self.to_screen((u.x - 26, u.y - 50))
            rect = pygame.Rect(x, y, 52 * self.zoom, 76 * self.zoom).clip(VIEW)
            if not rect.width:
                continue
            lines = tips.unit(self.game, u.regiment.unit, u.regiment)
            if u.state == "routing":
                lines.insert(1, ("Fleeing the field!", theme.DANGER))
            a = self.field.ability(u)
            wait = max(0, u.ready_at - self.field.time)
            lines.append((f"Special order: {a['name']}" + (f" (ready in {wait:.0f}s)" if wait else " (Q)"),
                          theme.HIGHLIGHT))
            theme.tip(rect, lines)

    def _zone(self, surface):
        x, y, w, h = self.field.deploy_zone(self.me)
        lit = pygame.Surface((w, h), pygame.SRCALPHA)
        lit.fill((255, 236, 160, 40))
        surface.blit(lit, (x, y))
        pygame.draw.rect(surface, theme.HIGHLIGHT, (x, y, w, h), 2)

    def _gates(self, surface):
        """Shut gates are drawn as oak doors bound with iron; a broken gate shows its splinters."""
        if self.field.kind != "assault":
            return
        for g in GATES:
            gate = self.field.gate(g)
            rect = pygame.Rect(WALL_X - 9, g - 44, 18, 88)
            if gate:
                pygame.draw.rect(surface, (40, 28, 18), rect.move(3, 3))
                pygame.draw.rect(surface, (112, 76, 44), rect)
                for k in range(rect.y + 10, rect.bottom, 18):
                    pygame.draw.line(surface, (60, 60, 64), (rect.x, k), (rect.right, k), 2)
                pygame.draw.rect(surface, theme.INK, rect, 2)
                if gate.hp < 100:
                    bar = pygame.Rect(rect.x - 10, rect.y - 10, 38, 5)
                    theme.gauge(surface, bar, gate.hp / 100, theme.GOLD)
            else:
                for k in range(5):
                    pygame.draw.line(surface, (96, 66, 40), (WALL_X - 20 + k * 9, g - 30 + k * 13),
                                     (WALL_X - 8 + k * 9, g - 24 + k * 13), 3)

    def _banner(self, surface, u):
        """The regiment's standard above its ranks: its colours, what it is, how strong it still is."""
        unit = self.game.data.units[u.regiment.unit]
        x, y = u.x - math.cos(u.facing) * 10, u.y - 44
        pygame.draw.line(surface, theme.INK, (x, y), (x, y + 18), 3)
        pygame.draw.line(surface, (196, 170, 120), (x, y), (x, y + 18), 1)
        key = (u.side, unit["icon"], u.state == "routing")
        if key not in self._banners:
            color = self.colors[u.side]
            if u.state == "routing":
                color = tuple(min(255, c + 90) for c in color)
            flag = pygame.Surface((20, 17), pygame.SRCALPHA)
            pygame.draw.polygon(flag, theme.INK, [(0, 0), (20, 0), (20, 17), (10, 13), (0, 17)])
            pygame.draw.polygon(flag, color, [(1, 1), (19, 1), (19, 15), (10, 11), (1, 15)])
            icon = self.app.assets.get(f"unit_{unit['icon']}", theme.PARCHMENT, 1)
            flag.blit(icon, icon.get_rect(center=(10, 7)))
            self._banners[key] = flag
        flag = self._banners[key]
        surface.blit(flag, (x + 1, y - 1 + math.sin(self.field.time * 4 + u.id)))
        if u.regiment.rank:
            theme.chevrons(surface, (x + 23, y + 16), u.regiment.rank)
        bar = pygame.Rect(x - 10, y - 7, 22, 3)
        pygame.draw.rect(surface, theme.INK, bar.inflate(2, 2))
        pygame.draw.rect(surface, theme.GOOD if u.side == self.me else theme.DANGER,
                         (bar.x, bar.y, round(bar.width * min(1.0, u.regiment.hp / unit["hp"])), bar.height))
        if u.side == self.me and self.field.can_use(u) and not self.deploying:
            pygame.draw.circle(surface, theme.INK, (x + 16, y - 6), 4)
            pygame.draw.circle(surface, theme.HIGHLIGHT, (x + 16, y - 6), 3)  # its special order is ready

    def _hud(self, surface):
        f = self.field
        theme.frame(surface, HUD, corners=False)
        theme.outlined(surface, self.title, (16, HUD.y + 10), 24, theme.GOLD, anchor="topleft")
        minutes, seconds = divmod(int(f.time), 60)
        status = f"{minutes}:{seconds:02d}  ·  x{SPEEDS[self.speed]}  ·  {describe(f.weather, f.night)}"
        if self.zoom != 1.0:
            status += f"  ·  zoom x{self.zoom:g}"
        coming = [u for u in f.units if u.state == "waiting"]
        if coming:
            wait = max(0, min(u.arrive_at for u in coming) - f.time)
            status += f"  ·  reinforcements in {wait:.0f}s"
        theme.text(surface, status, (16, HUD.y + 42), 18, theme.TEXT_DIM)
        for side in (0, 1):
            y = HUD.y + 72 + side * 22
            share = f.strength(side) / f.start_hp[side] if f.start_hp[side] else 0
            standing = len(f.standing(side))
            theme.text(surface, f"{self.names[side]}: {standing} standing", (16, y), 18, self.colors[side])
            theme.gauge(surface, pygame.Rect(260, y + 4, 180, 10), share, self.colors[side])
        x = 470
        for uid in sorted(self.selected)[:4]:
            u = f.unit(uid)
            unit = self.game.data.units[u.regiment.unit]
            icon = self.app.assets.get(f"unit_{unit['icon']}", self.colors[u.side], 3)
            surface.blit(icon, icon.get_rect(center=(x + 16, HUD.y + 30)))
            theme.text(surface, unit["name"], (x + 34, HUD.y + 14), 16)
            theme.gauge(surface, pygame.Rect(x + 34, HUD.y + 34, 70, 6), u.regiment.hp / unit["hp"], theme.GOOD)
            x += 150
        if not self.selected:
            hint = ("Drag your regiments into place  ·  Right-click: set the selected ones down" if self.deploying
                    else "Left-click or drag: select  ·  Right-click: march / attack  ·  Q: special order  ·  "
                         "Wheel: zoom")
            theme.text(surface, hint, (470, HUD.y + 20), 16, theme.TEXT_DIM)
        mouse = pygame.mouse.get_pos()
        ready = [f.unit(i) for i in self.selected if f.can_use(f.unit(i))]
        order = f.ability(ready[0])["name"] if ready else "Special order"
        labels = {"pause": "Begin!" if self.deploying else "Resume" if self.paused else "Pause",
                  "speed": f"x{SPEEDS[self.speed]}", "auto": "Auto-resolve", "withdraw": "Withdraw",
                  "ability": f"{order}  (Q)"}
        for name, rect in self.buttons.items():
            enabled = not f.over and (name != "ability" or (bool(ready) and not self.deploying))
            theme.button(surface, rect, labels[name], rect.collidepoint(mouse) and enabled, enabled=enabled)

    def _outcome(self, surface):
        f = self.field
        won = (f.result.winner == "attacker") == (self.me == 0)
        veil = pygame.Surface((FIELD_W, FIELD_H), pygame.SRCALPHA)
        veil.fill((10, 8, 6, 140))
        surface.blit(veil, (0, 0))
        theme.outlined(surface, "Victory!" if won else "Defeat", (FIELD_W // 2, FIELD_H // 2 - 30), 72,
                       theme.GOOD if won else theme.DANGER, width=3)
        theme.button(surface, self.continue_rect, "Continue (Enter)", self.continue_rect.collidepoint(pygame.mouse.get_pos()))
