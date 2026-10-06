"""The real-time battle screen, and the question "lead it yourself, or auto-resolve?".

Both run their own small loop on top of the campaign (the campaign's rules call fight() in the
middle of a march or an assault), and return a BattleResult to the campaign.

Controls: left-click or drag a box to select your regiments (A selects all), right-click the
ground to march there or an enemy to attack it, H halts, Space pauses (the battle starts paused,
so you can give your first orders), F changes the speed.
"""

import math

import pygame

from ..game import battle
from ..game.realtime import FIELD_H, FIELD_W, Battlefield
from . import battle_art, painter, theme

HUD = pygame.Rect(0, FIELD_H, theme.WINDOW_SIZE[0], theme.WINDOW_SIZE[1] - FIELD_H)
STEP = 1 / 30
SPEEDS = (1, 2, 4)


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
        theme.frame(surface, box, accent=theme.DANGER)
        theme.ribbon(surface, (box.centerx, box.y + 4), _title(game, self.pid, self.kind), 26)
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
        self.ground = battle_art.paint_field(field)  # the fallen are painted onto it as they fall
        names = [game.faction_name(s.faction) for s in field.sides]
        self.colors = [theme.faction_color(game, s.faction) for s in field.sides]
        self.troops = battle_art.Troops(field, game.data.units, self.colors, self.ground)
        self.effects = battle_art.Effects(field, game.data.units, self.troops)
        self.troops.update(0, self.effects)
        self.clouds = battle_art.clouds()
        self.vignette = painter._vignette(FIELD_W, FIELD_H)
        self._banners = {}
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
            self.troops.update(0.0, self.effects)  # the fallen of the rest of the fight
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
        before = f.time
        while self._carry >= STEP and not f.over:
            f.step(STEP)
            self._carry -= STEP
        self.troops.update(f.time - before, self.effects)
        self.effects.update(self.ground)
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

    def draw(self, surface):
        f = self.field
        surface.blit(self.ground, (0, 0))
        for uid in self.selected:
            u = f.unit(uid)
            ring = pygame.Rect(0, 0, 64, 40)
            ring.center = (u.x, u.y + 2)
            pygame.draw.ellipse(surface, theme.INK, ring.inflate(4, 4), 3)
            pygame.draw.ellipse(surface, theme.HIGHLIGHT, ring, 2)
        self.effects.draw_shadows(surface)
        for _, image, rect in sorted(self.troops.sprites(f.time), key=lambda s: s[0]):
            surface.blit(image, rect)
        self.effects.draw(surface)
        drift = int(f.time * 6) % FIELD_W
        surface.blit(self.clouds, (drift - FIELD_W, 0))
        surface.blit(self.clouds, (drift, 0))
        surface.blit(self.vignette, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        for u in f.units:
            if u.state in ("ready", "routing"):
                self._banner(surface, u)
        if self.drag:
            rect = pygame.Rect(min(self.drag[0], self.mouse[0]), min(self.drag[1], self.mouse[1]),
                               abs(self.mouse[0] - self.drag[0]), abs(self.mouse[1] - self.drag[1]))
            pygame.draw.rect(surface, theme.HIGHLIGHT, rect, 1)
        self._hud(surface)
        if f.over:
            self._outcome(surface)
        elif self.paused:
            theme.outlined(surface, "Paused: give your orders, then press Space", (FIELD_W // 2, 24), 24,
                           theme.HIGHLIGHT)

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
        bar = pygame.Rect(x - 10, y - 7, 22, 3)
        pygame.draw.rect(surface, theme.INK, bar.inflate(2, 2))
        pygame.draw.rect(surface, theme.GOOD if u.side == self.me else theme.DANGER,
                         (bar.x, bar.y, round(bar.width * min(1.0, u.regiment.hp / unit["hp"])), bar.height))

    def _hud(self, surface):
        f = self.field
        theme.frame(surface, HUD, corners=False)
        theme.outlined(surface, _title(self.game, f.province, f.kind), (16, HUD.y + 10), 24, theme.GOLD,
                       anchor="topleft")
        minutes, seconds = divmod(int(f.time), 60)
        theme.text(surface, f"{minutes}:{seconds:02d}   speed x{SPEEDS[self.speed]}", (16, HUD.y + 42), 20,
                   theme.TEXT_DIM)
        for side in (0, 1):
            y = HUD.y + 72 + side * 22
            share = f.strength(side) / f.start_hp[side] if f.start_hp[side] else 0
            standing = len(f.standing(side))
            theme.text(surface, f"{self.names[side]}: {standing} standing", (16, y), 18, self.colors[side])
            theme.gauge(surface, pygame.Rect(260, y + 4, 200, 10), share, self.colors[side])
        x = 490
        for uid in sorted(self.selected)[:5]:
            u = f.unit(uid)
            unit = self.game.data.units[u.regiment.unit]
            icon = self.app.assets.get(f"unit_{unit['icon']}", self.colors[u.side], 3)
            surface.blit(icon, icon.get_rect(center=(x + 16, HUD.y + 30)))
            theme.text(surface, unit["name"], (x + 34, HUD.y + 14), 16)
            theme.gauge(surface, pygame.Rect(x + 34, HUD.y + 34, 70, 6), u.regiment.hp / unit["hp"], theme.GOOD)
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
        theme.outlined(surface, "Victory!" if won else "Defeat", (FIELD_W // 2, FIELD_H // 2 - 30), 72,
                       theme.GOOD if won else theme.DANGER, width=3)
        theme.button(surface, self.continue_rect, "Continue (Enter)", self.continue_rect.collidepoint(pygame.mouse.get_pos()))
