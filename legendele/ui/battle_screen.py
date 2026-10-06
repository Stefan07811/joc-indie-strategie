"""The real-time battle screen, and the question "lead it yourself, or auto-resolve?".

Both run their own small loop on top of the campaign (the campaign's rules call fight() in the
middle of a march or an assault), and return a BattleResult to the campaign.

Controls: left-click or drag a box to select your regiments (A selects all), right-click the
ground to march there or an enemy to attack it, H halts, Space pauses (the battle starts paused,
so you can give your first orders), F changes the speed.
"""

import math
import random

import pygame

from ..game import battle
from ..game.realtime import FIELD_H, FIELD_W, Battlefield
from . import theme

HUD = pygame.Rect(0, FIELD_H, theme.WINDOW_SIZE[0], theme.WINDOW_SIZE[1] - FIELD_H)
STEP = 1 / 30
SPEEDS = (1, 2, 4)
MEN = 16  # soldiers drawn per full-strength regiment
GRID = 4


def fight(app, game, attackers, defenders, pid, kind):
    """The campaign's fight_hook: ask (or follow the settings), then fight in real time or not at all."""
    mode = app.settings.get("battles", "ask")
    if mode == "auto" or not app.running:
        return None
    if mode == "ask" and not BattleQuestion(app, game, attackers, defenders, pid, kind).run():
        return None
    player_side = 0 if attackers.faction == game.player else 1
    field = Battlefield(attackers, defenders, game.data.units, game.provinces[pid].terrain, kind, game.rng,
                        province=pid, player_side=player_side)
    return BattleScreen(app, game, field).run()


def _title(game, pid, kind):
    return f"{'Assault on' if kind == 'assault' else 'Battle of'} {game.provinces[pid].name}"


class BattleQuestion:
    BOX = pygame.Rect(0, 0, 600, 300)

    def __init__(self, app, game, attackers, defenders, pid, kind):
        self.app, self.game = app, game
        self.attackers, self.defenders, self.pid, self.kind = attackers, defenders, pid, kind
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
        pygame.draw.rect(surface, theme.PANEL_BG, box, border_radius=8)
        pygame.draw.rect(surface, theme.GOLD, box, 3, border_radius=8)
        theme.text(surface, _title(game, self.pid, self.kind), (box.centerx, box.y + 26), 34, theme.GOLD,
                   anchor="midtop")
        a, d = self.attackers, self.defenders
        line = (f"{game.faction_name(a.faction)} ({len(a.regiments)} regiments)  against  "
                f"{game.faction_name(d.faction, True)} ({len(d.regiments)})")
        theme.text(surface, line, (box.centerx, box.y + 80), 20, theme.PARCHMENT, anchor="midtop")
        wins, share = battle.predict(a, d, game.data.units, kind=self.kind)
        player_attacks = a.faction == game.player
        good = wins == player_attacks
        verdict = ("Forecast: " + ("victory" if good else "defeat") + " if the battle is auto-resolved")
        theme.text(surface, verdict, (box.centerx, box.y + 116), 20, theme.GOOD if good else theme.DANGER,
                   anchor="midtop")
        theme.text(surface, "Lead it yourself, or let your generals decide?", (box.centerx, box.y + 160), 20,
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
            self.draw(self.app.screen)
            pygame.display.flip()
            clock.tick(60)
        return self.answer


class BattleScreen:
    def __init__(self, app, game, field):
        self.app, self.game, self.field = app, game, field
        self.me = field.player_side
        self.selected = set()
        self.paused = True
        self.speed = 0
        self.drag = None
        self.mouse = (0, 0)
        self.result = None
        self.clash_at = 0.0
        self._carry = 0.0  # unspent time, simulated in fixed steps
        self.ground = self._paint_ground()
        names = [game.faction_name(s.faction) for s in field.sides]
        self.colors = [theme.faction_color(game, s.faction) for s in field.sides]
        self.names = names
        x = HUD.right - 16
        self.buttons = {}
        for name, width in (("withdraw", 130), ("auto", 150), ("speed", 90), ("pause", 110)):
            self.buttons[name] = pygame.Rect(x - width, HUD.y + 64, width, 36)
            x -= width + 10
        self.continue_rect = pygame.Rect(0, 0, 240, 50)
        self.continue_rect.center = (FIELD_W // 2, FIELD_H // 2 + 70)

    # --- input -----------------------------------------------------------------------------

    def handle(self, event):
        f = self.field
        if f.over:
            if (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE)) or \
                    (event.type == pygame.MOUSEBUTTONDOWN and self.continue_rect.collidepoint(event.pos)):
                self.result = f.result
            return
        if event.type == pygame.MOUSEMOTION:
            self.mouse = event.pos
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.paused = not self.paused
            elif event.key == pygame.K_f:
                self.speed = (self.speed + 1) % len(SPEEDS)
            elif event.key == pygame.K_h:
                f.order_halt(self.selected)
            elif event.key == pygame.K_a:
                self.selected = {u.id for u in f.standing(self.me)}
            elif event.key == pygame.K_ESCAPE:
                self.selected = set()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, rect in self.buttons.items():
                if rect.collidepoint(event.pos):
                    self._button(name)
                    return
            if event.pos[1] < FIELD_H:
                self.drag = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.drag:
            self._select(self.drag, event.pos, pygame.key.get_mods() & pygame.KMOD_SHIFT)
            self.drag = None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and event.pos[1] < FIELD_H:
            self._command(event.pos)

    def _button(self, name):
        f = self.field
        self.app.audio.play("click")
        if name == "pause":
            self.paused = not self.paused
        elif name == "speed":
            self.speed = (self.speed + 1) % len(SPEEDS)
        elif name == "auto":
            f.finish()
        elif name == "withdraw":
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
        enemy = self._unit_at(pos, 1 - self.me)
        if enemy is not None:
            self.field.order_attack(self.selected, enemy.id)
        else:
            self.field.order_move(self.selected, *pos)
        self.app.audio.play("click")

    # --- time ------------------------------------------------------------------------------

    def update(self, dt):
        f = self.field
        if f.over or self.paused:
            return
        self._carry += min(dt, 0.1) * SPEEDS[self.speed]
        while self._carry >= STEP and not f.over:
            f.step(STEP)
            self._carry -= STEP
        self.selected = {i for i in self.selected if f.unit(i).ready}
        if any(u.fighting is not None for u in f.units) and f.time - self.clash_at > 2.5:
            self.clash_at = f.time
            self.app.audio.play("battle")
        if f.over:
            won = (f.result.winner == "attacker") == (self.me == 0)
            self.app.audio.play("victory" if won else "defeat")

    def run(self):
        clock = pygame.time.Clock()
        self.app.audio.play("alarm")
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
            self.draw(self.app.screen)
            pygame.display.flip()
        return self.result

    # --- drawing ---------------------------------------------------------------------------

    def _paint_ground(self):
        f = self.field
        base = self.game.data.terrain[f.terrain]["color"]
        ground = pygame.Surface((FIELD_W, FIELD_H))
        ground.fill(base)
        rng = random.Random(7)  # the same speckles every time
        for _ in range(1800):
            x, y = rng.randrange(FIELD_W), rng.randrange(FIELD_H)
            shade = rng.choice((-14, -8, 8, 12))
            ground.fill(tuple(max(0, min(255, c + shade)) for c in base), (x - x % 4, y - y % 4, 4, 4))
        for z in f.zones:
            if z.kind == "hill":
                for i, r in enumerate((z.r, z.r * 0.7, z.r * 0.4)):
                    pygame.draw.ellipse(ground, tuple(min(255, c + 10 + 8 * i) for c in (176, 150, 100)),
                                        pygame.Rect(z.x - r, z.y - r * 0.75, 2 * r, 1.5 * r))
            elif z.kind == "marsh":
                pygame.draw.ellipse(ground, (74, 104, 112), pygame.Rect(z.x - z.r, z.y - z.r * 0.6, 2 * z.r, 1.2 * z.r))
                for k in range(8):
                    a = k * 0.8
                    x, y = z.x + math.cos(a) * z.r * 0.8, z.y + math.sin(a) * z.r * 0.5
                    pygame.draw.line(ground, (60, 92, 54), (x, y), (x, y - 8), 2)
        for z in f.zones:
            if z.kind == "forest":
                floor = tuple(max(0, c - 22) for c in base)
                pygame.draw.circle(ground, floor, (z.x, z.y), z.r)
                for k in range(int(z.r / 6)):
                    a = rng.uniform(0, 2 * math.pi)
                    d = z.r * math.sqrt(rng.random())
                    x, y = z.x + math.cos(a) * d, z.y + math.sin(a) * d
                    pygame.draw.polygon(ground, (36, 78, 42), [(x - 8, y + 6), (x, y - 12), (x + 8, y + 6)])
                    pygame.draw.rect(ground, (90, 60, 36), (x - 1, y + 6, 3, 4))
        for b in f.blocks:
            rect = pygame.Rect(b.x, b.y, b.w, b.h)
            if b.kind == "rocks":
                pygame.draw.rect(ground, (112, 106, 102), rect, border_radius=10)
                pygame.draw.rect(ground, (84, 78, 74), rect, 3, border_radius=10)
            else:
                pygame.draw.rect(ground, (170, 160, 146), rect)
                for yy in range(int(b.y), int(b.y + b.h), 12):
                    pygame.draw.rect(ground, (130, 120, 108), (b.x - 3, yy, 26, 6))
        return ground

    def draw(self, surface):
        f = self.field
        surface.blit(self.ground, (0, 0))
        for u in f.units:
            if u.shooting is not None:
                self._arrows(surface, u, f.unit(u.shooting))
        for u in sorted(f.units, key=lambda u: u.y):
            if u.state in ("ready", "routing"):
                self._regiment(surface, u)
        for u in f.units:
            if u.fighting is not None:
                t = f.unit(u.fighting)
                mx, my = (u.x + t.x) / 2, (u.y + t.y) / 2
                phase = int(f.time * 10 + u.id) % 3
                pygame.draw.circle(surface, (255, 240, 180), (mx + phase * 3 - 3, my - phase * 2), 2)
        if self.drag:
            rect = pygame.Rect(min(self.drag[0], self.mouse[0]), min(self.drag[1], self.mouse[1]),
                               abs(self.mouse[0] - self.drag[0]), abs(self.mouse[1] - self.drag[1]))
            pygame.draw.rect(surface, theme.HIGHLIGHT, rect, 1)
        self._hud(surface)
        if f.over:
            self._outcome(surface)
        elif self.paused:
            theme.text(surface, "Paused: give your orders, then press Space", (FIELD_W // 2, 24), 26,
                       theme.HIGHLIGHT, anchor="center", shadow=theme.INK)

    def _regiment(self, surface, u):
        unit = self.game.data.units[u.regiment.unit]
        color = self.colors[u.side]
        if u.state == "routing":
            color = tuple(min(255, c + 90) for c in color)
        men = max(1, math.ceil(MEN * u.regiment.hp / unit["hp"]))
        cos, sin = math.cos(u.facing), math.sin(u.facing)
        jitter = (math.sin(self.field.time * 20 + u.id) * 2) if u.state == "routing" else 0
        for k in range(men):
            row, col = divmod(k, GRID)
            fx = (GRID / 2 - row - 0.5) * 9  # front rank faces forward
            fy = (col - GRID / 2 + 0.5) * 9
            x = u.x + fx * cos - fy * sin + jitter
            y = u.y + fx * sin + fy * cos
            pygame.draw.rect(surface, theme.INK, (x - 3, y - 3, 7, 7))
            pygame.draw.rect(surface, color, (x - 2, y - 2, 5, 5))
        if u.id in self.selected:
            pygame.draw.circle(surface, theme.HIGHLIGHT, (u.x, u.y), 27, 2)
        icon = self.app.assets.get(f"unit_{unit['icon']}", self.colors[u.side], 2)
        surface.blit(icon, icon.get_rect(midbottom=(u.x, u.y - 22)))
        bar = pygame.Rect(u.x - 16, u.y + 22, 32, 4)
        pygame.draw.rect(surface, theme.INK, bar)
        pygame.draw.rect(surface, theme.GOOD if u.side == self.me else theme.DANGER,
                         (bar.x, bar.y, round(bar.width * min(1.0, u.regiment.hp / unit["hp"])), bar.height))
        if u.ready and u.order and u.side == self.me and u.id in self.selected:
            if u.order[0] == "move":
                pygame.draw.line(surface, theme.HIGHLIGHT, (u.x, u.y), u.order[1:], 1)
            else:
                t = self.field.unit(u.order[1])
                pygame.draw.line(surface, theme.DANGER, (u.x, u.y), (t.x, t.y), 1)

    def _arrows(self, surface, u, t):
        dist = math.hypot(t.x - u.x, t.y - u.y) or 1
        dx, dy = (t.x - u.x) / dist, (t.y - u.y) / dist
        for k in range(3):
            p = ((self.field.time * 1.6 + k / 3 + u.id * 0.17) % 1.0)
            x, y = u.x + dx * dist * p, u.y + dy * dist * p - math.sin(p * math.pi) * min(60, dist / 4)
            pygame.draw.line(surface, (60, 44, 30), (x, y), (x - dx * 8, y - dy * 8), 2)

    def _hud(self, surface):
        f = self.field
        pygame.draw.rect(surface, theme.PANEL_BG, HUD)
        pygame.draw.line(surface, theme.PANEL_LINE, HUD.topleft, HUD.topright, 3)
        theme.text(surface, _title(self.game, f.province, f.kind), (16, HUD.y + 10), 28, theme.GOLD)
        minutes, seconds = divmod(int(f.time), 60)
        theme.text(surface, f"{minutes}:{seconds:02d}   speed x{SPEEDS[self.speed]}", (16, HUD.y + 42), 20,
                   theme.TEXT_DIM)
        for side in (0, 1):
            y = HUD.y + 72 + side * 22
            share = f.strength(side) / f.start_hp[side] if f.start_hp[side] else 0
            standing = len(f.standing(side))
            theme.text(surface, f"{self.names[side]}: {standing} standing", (16, y), 18, self.colors[side])
            bar = pygame.Rect(260, y + 4, 200, 10)
            pygame.draw.rect(surface, theme.PANEL_LINE, bar)
            pygame.draw.rect(surface, self.colors[side], (bar.x, bar.y, round(bar.width * share), bar.height))
        x = 490
        for uid in sorted(self.selected)[:5]:
            u = f.unit(uid)
            unit = self.game.data.units[u.regiment.unit]
            icon = self.app.assets.get(f"unit_{unit['icon']}", self.colors[u.side], 3)
            surface.blit(icon, icon.get_rect(center=(x + 16, HUD.y + 30)))
            theme.text(surface, unit["name"], (x + 34, HUD.y + 14), 16)
            pygame.draw.rect(surface, theme.PANEL_LINE, (x + 34, HUD.y + 34, 70, 6))
            pygame.draw.rect(surface, theme.GOOD, (x + 34, HUD.y + 34, round(70 * u.regiment.hp / unit["hp"]), 6))
            x += 150
        if not self.selected:
            theme.text(surface, "Left-click or drag: select  ·  Right-click: march / attack  ·  A: all  ·  H: halt",
                       (490, HUD.y + 20), 17, theme.TEXT_DIM)
        mouse = pygame.mouse.get_pos()
        labels = {"pause": "Resume" if self.paused else "Pause", "speed": f"x{SPEEDS[self.speed]}",
                  "auto": "Auto-resolve", "withdraw": "Withdraw"}
        for name, rect in self.buttons.items():
            theme.button(surface, rect, labels[name], rect.collidepoint(mouse) and not f.over, enabled=not f.over)

    def _outcome(self, surface):
        f = self.field
        won = (f.result.winner == "attacker") == (self.me == 0)
        veil = pygame.Surface((FIELD_W, FIELD_H), pygame.SRCALPHA)
        veil.fill((10, 8, 6, 140))
        surface.blit(veil, (0, 0))
        theme.text(surface, "Victory!" if won else "Defeat", (FIELD_W // 2, FIELD_H // 2 - 30), 72,
                   theme.GOOD if won else theme.DANGER, anchor="center", shadow=theme.INK)
        theme.button(surface, self.continue_rect, "Continue (Enter)", self.continue_rect.collidepoint(pygame.mouse.get_pos()))
