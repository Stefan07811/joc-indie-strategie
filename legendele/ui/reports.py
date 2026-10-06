"""Pop-up windows over the map: battle reports, captures and the end of the war."""

import pygame

from ..game import (Abduction, Battle, Captured, DiplomacyChange, Eliminated, GeneralFell, Proposal, Rebellion,
                    Tale, Victory, events)
from ..game.state import SEASONS
from . import theme

BOX = pygame.Rect(0, 0, 560, 340)
BOX.center = theme.MAP_RECT.center


def concerns_player(game, event):
    """Does the player need a pop-up for this event? (Everything else only goes to the chronicle.)"""
    if isinstance(event, Battle):
        return game.player in (event.result.attacker.faction, event.result.defender.faction)
    if isinstance(event, Captured):
        return event.previous == game.player
    if isinstance(event, Rebellion):
        return event.faction == game.player
    if isinstance(event, Abduction):
        return game.player in (event.faction, event.victim)
    if isinstance(event, DiplomacyChange):
        return game.player in (event.faction, event.other)
    if isinstance(event, Proposal):
        return event.other == game.player
    if isinstance(event, GeneralFell):
        return event.faction == game.player
    if isinstance(event, Tale):
        return event.faction == game.player and event in game.pending_events
    return isinstance(event, (Eliminated, Victory))


def _shade(surface):
    veil = pygame.Surface(theme.MAP_RECT.size, pygame.SRCALPHA)
    veil.fill((10, 8, 6, 150))
    surface.blit(veil, theme.MAP_RECT)


def _frame(surface, rect, color):
    theme.frame(surface, rect, accent=color)


ACCEPT_RECT = pygame.Rect(0, 0, 160, 40)
DECLINE_RECT = pygame.Rect(0, 0, 160, 40)
ACCEPT_RECT.midbottom = (BOX.centerx - 90, BOX.bottom - 44)
DECLINE_RECT.midbottom = (BOX.centerx + 90, BOX.bottom - 44)


def draw_report(surface, game, assets, event, mouse=(0, 0)):
    _shade(surface)
    if isinstance(event, Battle):
        _battle(surface, game, assets, event.result)
    elif isinstance(event, Proposal):
        _proposal(surface, game, event, mouse)
        return
    elif isinstance(event, Tale):
        _tale(surface, game, event, mouse)
        return
    else:
        _notice(surface, game, event)
    theme.text(surface, "Click or press Enter to continue", (BOX.centerx, BOX.bottom - 22), 17, theme.TEXT_DIM,
               anchor="center")


def _proposal(surface, game, offer, mouse):
    color = theme.faction_color(game, offer.faction)
    _frame(surface, BOX, color)
    theme.ribbon(surface, (BOX.centerx, BOX.y + 4), f"Envoys from {game.faction_name(offer.faction, True)}", 24,
                 color=color)
    if offer.kind == "peace":
        body = "They are tired of this war and offer peace."
        if offer.gold:
            body += f" They will pay {offer.gold} gold."
    else:
        body = "They propose an alliance: open roads between us, and each defends the other."
    y = BOX.y + 110
    for line in theme.wrap(body, 24, BOX.width - 80):
        theme.text(surface, line, (BOX.centerx, y), 24, theme.PARCHMENT, anchor="midtop")
        y += 28
    theme.button(surface, ACCEPT_RECT, "Accept  (Y)", ACCEPT_RECT.collidepoint(mouse))
    theme.button(surface, DECLINE_RECT, "Decline  (N)", DECLINE_RECT.collidepoint(mouse))


TALE_BOX = pygame.Rect(0, 0, 640, 430)
TALE_BOX.center = theme.MAP_RECT.center


def tale_choice_rects(n):
    """Where the answers to a tale are, top to bottom."""
    return [pygame.Rect(TALE_BOX.x + 40, TALE_BOX.bottom - 30 - (n - i) * 62, TALE_BOX.width - 80, 54)
            for i in range(n)]


def _tale(surface, game, tale, mouse):
    e = game.data.events[tale.event]
    theme.frame(surface, TALE_BOX, kind="parchment")
    theme.ribbon(surface, (TALE_BOX.centerx, TALE_BOX.y + 4), e["title"], 24)
    y = TALE_BOX.y + 54
    for line in theme.wrap(events.text(game, tale, e["text"]), 20, TALE_BOX.width - 90):
        theme.text(surface, line, (TALE_BOX.x + 45, y), 20, theme.INK, lift=False)
        y += 23
    for i, (rect, choice) in enumerate(zip(tale_choice_rects(len(e["choices"])), e["choices"])):
        hovered = rect.collidepoint(mouse)
        theme.row(surface, rect, hovered)
        theme.text(surface, f"{i + 1}.  {choice['label']}", (rect.x + 14, rect.y + 7), 20,
                   theme.HIGHLIGHT if hovered else theme.PARCHMENT)
        theme.text(surface, events.summary(game, choice.get("effects", {})), (rect.x + 34, rect.y + 31), 16,
                   theme.GOLD)


def _battle(surface, game, assets, result):
    place = game.provinces[result.province].name
    player_won = result.winning_faction == game.player
    _frame(surface, BOX, theme.GOOD if player_won else theme.DANGER)
    title = f"{'Assault on' if result.kind == 'assault' else 'Battle of'} {place}"
    theme.ribbon(surface, (BOX.centerx, BOX.y + 4), title, 24)
    theme.outlined(surface, "Victory!" if player_won else "Defeat", (BOX.centerx, BOX.y + 58), 34,
                   theme.GOOD if player_won else theme.DANGER, anchor="midtop")

    column = BOX.width // 2
    for i, (side, label) in enumerate(((result.attacker, "Attacker"), (result.defender, "Defender"))):
        x = BOX.x + i * column + 30
        y = BOX.y + 110
        color = theme.faction_color(game, side.faction)
        banner = assets.get(f"army_{side.faction}", color)
        surface.blit(banner, (x, y))
        theme.text(surface, label, (x + 44, y), 18, theme.TEXT_DIM)
        theme.outlined(surface, game.faction_name(side.faction), (x + 44, y + 17), 19, color, anchor="topleft",
                       width=1)
        y += 50
        theme.text(surface, side.leader or "Garrison", (x, y), 20)
        y += 26
        lost = side.start_regiments - side.end_regiments
        theme.text(surface, f"Regiments: {side.end_regiments} of {side.start_regiments}"
                            + (f"  ({lost} lost)" if lost else ""), (x, y), 18)
        y += 24
        bar = pygame.Rect(x, y, column - 60, 12)
        share = side.end_hp / side.start_hp if side.start_hp else 0
        theme.gauge(surface, bar, share, theme.GOOD if share > 0.5 else theme.HIGHLIGHT if share > 0.25 else theme.DANGER)
        theme.text(surface, f"{round(share * 100)}% strength left", (x, y + 18), 17, theme.TEXT_DIM)
    footer = [f"The fighting lasted {result.rounds} round{'s' if result.rounds != 1 else ''}.", *result.notes]
    for i, line in enumerate(reversed(footer)):
        theme.text(surface, line, (BOX.centerx, BOX.bottom - 52 - 20 * i), 18,
                   theme.GOLD if line in result.notes else theme.TEXT_DIM, anchor="center")


def _notice(surface, game, event):
    if isinstance(event, Captured):
        title, color = f"{game.provinces[event.province].name} has fallen", theme.DANGER
        body = f"{game.faction_name(event.faction)} have taken it from us."
    elif isinstance(event, DiplomacyChange):
        other = event.other if event.faction == game.player else event.faction
        name = game.faction_name(other, True)
        mine = event.faction == game.player
        title, color, body = {
            "war": ((f"War with {name}", theme.DANGER,
                     ("We have declared war." if mine else f"{game.faction_name(other)} have declared war on us!")
                     + (" It is treachery, and it will not be forgotten." if event.treachery else ""))),
            "peace": (f"Peace with {name}", theme.GOOD, "The borders between us are closed to armies."),
            "alliance": (f"Alliance with {name}", theme.GOOD, "Our armies may cross each other's land, "
                                                             "and we stand together if attacked."),
            "break": (f"The alliance with {name} is over", theme.GOLD, "We are merely at peace now."),
        }[event.kind]
    elif isinstance(event, Rebellion):
        title, color = f"{game.provinces[event.province].name} rises up!", theme.DANGER
        body = ("Unpaid, hungry or freshly conquered, the people have had enough: Outlaws take up arms. "
                "Keep troops in restless provinces and build to calm them.")
    elif isinstance(event, Abduction):
        place = game.provinces[event.province].name
        if event.faction == game.player:
            title, color = (("The heir is ours!", theme.GOOD) if event.success
                            else ("The abduction failed", theme.DANGER))
            body = (f"{game.faction_name(event.victim)} paid {event.ransom} gold to get their heir back from {place}."
                    if event.success else f"The guards of {place} fought us off.")
        else:
            title, color = (("Our heir has been taken!", theme.DANGER) if event.success
                            else ("A Dragonkin raid was driven off", theme.GOOD))
            body = (f"The Dragonkin carried off the heir from {place}. We paid {event.ransom} gold in ransom."
                    if event.success else f"The guards of {place} drove the Dragonkin away.")
    elif isinstance(event, GeneralFell):
        title, color = f"{event.general} has fallen", theme.DANGER
        body = (f"He died at the head of his men near {game.provinces[event.province].name}. "
                f"{event.successor} takes command of the army; he will have to earn his own name.")
    elif isinstance(event, Eliminated):
        mine = event.faction == game.player
        title, color = ("Your realm is lost" if mine else f"{game.faction_name(event.faction)} are no more",
                        theme.DANGER if mine else theme.GOLD)
        body = ("The legends will forget your name." if mine
                else "Their last province has fallen; their armies scatter into the mist.")
    else:  # Victory
        mine = event.faction == game.player
        title, color = (("Victory!" if mine else "Defeat"), theme.GOOD if mine else theme.DANGER)
        how = {"conquest": f"conquered {game.victory_rules['conquest_provinces']} provinces",
               "legend": "held the Heart of the Mountains and their capital through the seasons",
               "last_standing": "outlasted every rival"}[event.kind]
        body = f"{game.faction_name(event.faction)} {how}."
    _frame(surface, BOX, color)
    theme.ribbon(surface, (BOX.centerx, BOX.y + 4), title, 24, color=color)
    y = BOX.y + 130
    for line in theme.wrap(body, 24, BOX.width - 80):
        theme.text(surface, line, (BOX.centerx, y), 24, theme.PARCHMENT, anchor="midtop")
        y += 28


def draw_game_over(surface, game, button_rect, mouse):
    """A strip at the top of the map once the war is decided, with a way back to the menu."""
    strip = pygame.Rect(theme.MAP_RECT.x, 0, theme.MAP_RECT.width, 56)
    theme.frame(surface, strip, corners=False)
    won = game.winner is not None and game.winner.faction == game.player
    text = "You are master of the Carpathians!" if won else "The war is lost."
    theme.outlined(surface, text, (strip.x + 20, strip.centery), 26, theme.GOOD if won else theme.DANGER,
                   anchor="midleft")
    theme.button(surface, button_rect, "Main menu", button_rect.collidepoint(mouse))


class TurnSummary:
    """The season's news, after the other legends have moved: every line of the chronicle written
    since we ended our turn, each one a way to look at the place it happened."""

    ROW = 24
    VISIBLE = 15

    def __init__(self, game, lines):
        self.game = game
        names = sorted(((p.name, p.id) for p in game.provinces.values()), key=lambda n: -len(n[0]))
        factions = sorted(((game.faction_name(f), f) for f in game.data.factions), key=lambda n: -len(n[0]))
        self.rows = []
        for line in lines:
            place = next((pid for name, pid in names if name in line), None)
            who = min(((line.find(name), fid) for name, fid in factions if name in line), default=(0, None))[1]
            self.rows.append((line, place, who))
        shown = max(5, min(self.VISIBLE, len(self.rows)))
        self.box = pygame.Rect(0, 0, 720, 130 + shown * self.ROW)
        self.box.center = theme.MAP_RECT.center
        self.continue_rect = pygame.Rect(0, 0, 220, 40)
        self.continue_rect.midbottom = (self.box.centerx, self.box.bottom - 16)
        self.top = 0
        self.row_rects = []

    def handle(self, event):
        """None while open; "close" to just close it; a province id to close it and look there."""
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE,
                                                          pygame.K_ESCAPE):
            return "close"
        if event.type == pygame.MOUSEWHEEL:
            self.top = max(0, min(len(self.rows) - self.VISIBLE, self.top - event.y))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.continue_rect.collidepoint(event.pos):
                return "close"
            for rect, place in self.row_rects:
                if place and rect.collidepoint(event.pos):
                    return place
        return None

    def draw(self, surface, mouse):
        _shade(surface)
        game = self.game
        theme.frame(surface, self.box)
        theme.ribbon(surface, (self.box.centerx, self.box.y + 4), f"Tidings of {game.date}", 24)
        x, y = self.box.x + 28, self.box.y + 48
        mine = game.faction_name(game.player)
        self.row_rects = []
        for line, place, who in self.rows[self.top:self.top + self.VISIBLE]:
            rect = pygame.Rect(x - 6, y - 2, self.box.width - 44, self.ROW - 2)
            hovered = place is not None and rect.collidepoint(mouse)
            if hovered:
                theme.row(surface, rect, True)
            color = theme.PARCHMENT if mine in line else theme.TEXT_DIM
            shown = line
            while theme.font(18).size(shown)[0] > rect.width - 70 and len(shown) > 10:
                shown = shown[:-4] + "..."
            if who:
                shield = [(x, y + 3), (x + 10, y + 3), (x + 10, y + 10), (x + 5, y + 15), (x, y + 10)]
                pygame.draw.polygon(surface, theme.faction_color(game, who), shield)
                pygame.draw.polygon(surface, theme.GOLD_DARK, shield, 1)
            theme.text(surface, shown, (x + 18, y), 18, theme.HIGHLIGHT if hovered else color)
            if place:
                theme.text(surface, "show" if hovered else "·", (rect.right - 8, y), 16, theme.GOLD, anchor="topright")
                theme.tip(rect, [game.provinces[place].name, line, ("Click to look there.", theme.TEXT_DIM)])
            self.row_rects.append((rect, place))
            y += self.ROW
        if not self.rows:
            theme.text(surface, "A quiet season.", (x, y), 18, theme.TEXT_DIM)
        if len(self.rows) > self.VISIBLE:
            theme.text(surface, f"{self.top + 1}-{min(len(self.rows), self.top + self.VISIBLE)} of {len(self.rows)}"
                                "  ·  scroll for more", (self.box.right - 28, self.continue_rect.y - 22), 16,
                       theme.TEXT_DIM, anchor="topright")
        theme.button(surface, self.continue_rect, "Continue  (Enter)", self.continue_rect.collidepoint(mouse))


class EndScreen:
    """The chronicle of the war, once it is decided: how every realm grew and shrank, season by
    season, and what each did in battle."""

    BOX = pygame.Rect(0, 0, 1200, 660)

    def __init__(self, game):
        self.game = game
        self.box = self.BOX.copy()
        self.box.center = (theme.WINDOW_SIZE[0] // 2, theme.WINDOW_SIZE[1] // 2)
        self.chart = pygame.Rect(self.box.x + 34, self.box.y + 118, 730, 420)
        self.map_rect = pygame.Rect(0, 0, 220, 44)
        self.menu_rect = pygame.Rect(0, 0, 220, 44)
        self.map_rect.bottomright = (self.box.centerx - 10, self.box.bottom - 22)
        self.menu_rect.bottomleft = (self.box.centerx + 10, self.box.bottom - 22)
        self.factions = [f for f, d in game.data.factions.items() if d["playable"]]

    def handle(self, event):
        """None while open; "map" to look at the map; "menu" for the main menu."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "map"
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return "menu"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.map_rect.collidepoint(event.pos):
                return "map"
            if self.menu_rect.collidepoint(event.pos):
                return "menu"
        return None

    def draw(self, surface, mouse):
        game = self.game
        veil = pygame.Surface(theme.WINDOW_SIZE, pygame.SRCALPHA)
        veil.fill((10, 8, 6, 190))
        surface.blit(veil, (0, 0))
        theme.frame(surface, self.box)
        won = game.winner is not None and game.winner.faction == game.player
        title = "Victory" if won else "Defeat"
        theme.ribbon(surface, (self.box.centerx, self.box.y + 4), f"{title}  ·  The Chronicle of the War", 26,
                     color=theme.GOOD if won else theme.DANGER)
        if game.winner:
            how = {"conquest": "by conquest", "legend": "by holding the Heart of the Mountains",
                   "last_standing": "as the last legend standing"}[game.winner.kind]
            line = f"{game.faction_name(game.winner.faction)} won {how}, in {game.date}."
        else:
            line = f"{game.faction_name(game.player)} were destroyed in {game.date}."
        seasons = len(game.history) - 1
        years, rest = divmod(seasons, 4)
        span = [f"{years} year{'s' if years != 1 else ''}"] if years else []
        span += [f"{rest} season{'s' if rest != 1 else ''}"] if rest or not years else []
        line += f"  The war lasted {' and '.join(span)}."
        theme.text(surface, line, (self.box.centerx, self.box.y + 66), 22, theme.PARCHMENT, anchor="midtop")
        self._chart(surface, mouse)
        self._table(surface, self.chart.right + 34, self.chart.y)
        theme.button(surface, self.map_rect, "Look at the map  (Esc)", self.map_rect.collidepoint(mouse))
        theme.button(surface, self.menu_rect, "Main menu  (Enter)", self.menu_rect.collidepoint(mouse))

    # --- provinces held, season by season ----------------------------------------------------

    def _chart(self, surface, mouse):
        game = self.game
        area = theme.frame(surface, self.chart, kind="parchment", corners=False)
        theme.text(surface, "Provinces held", (area.x + 12, area.y + 8), 20, theme.INK, lift=False)
        plot = pygame.Rect(area.x + 46, area.y + 40, area.width - 150, area.height - 76)
        history = game.history or [{"round": game.round, "factions": {}}]
        goal = game.victory_rules["conquest_provinces"]
        top = max(goal, max((row["provinces"] for snap in history for row in snap["factions"].values()), default=1))
        top = ((top + 4) // 5) * 5
        ink, faint = (70, 56, 40), (200, 186, 152)

        def at(i, value):
            x = plot.x + (plot.width * i / max(1, len(history) - 1))
            return x, plot.bottom - plot.height * value / top

        for v in range(0, top + 1, 5):  # recessive grid and the one axis
            y = at(0, v)[1]
            pygame.draw.line(surface, faint, (plot.x, y), (plot.right, y), 1)
            theme.text(surface, str(v), (plot.x - 8, y), 15, ink, anchor="midright", lift=False)
        gy = at(0, goal)[1]
        for x in range(plot.x, plot.right, 12):  # the conquest goal, dashed
            pygame.draw.line(surface, (150, 110, 60), (x, gy), (min(x + 6, plot.right), gy), 1)
        theme.text(surface, f"Conquest: {goal}", (plot.x + 6, gy - 2), 15, (120, 84, 40), anchor="bottomleft",
                   lift=False)
        first_year = game.data.map["start_year"] + history[0]["round"] // 4
        last_year = game.data.map["start_year"] + history[-1]["round"] // 4
        step = max(1, (last_year - first_year) // 6 or 1)
        for i, snap in enumerate(history):
            if snap["round"] % 4 == 0 and (game.data.map["start_year"] + snap["round"] // 4 - first_year) % step == 0:
                x = at(i, 0)[0]
                pygame.draw.line(surface, ink, (x, plot.bottom), (x, plot.bottom + 4), 1)
                theme.text(surface, str(game.data.map["start_year"] + snap["round"] // 4), (x, plot.bottom + 6), 15,
                           ink, anchor="midtop", lift=False)
        pygame.draw.line(surface, ink, plot.bottomleft, plot.bottomright, 1)

        ends = []
        for fid in self.factions:  # each realm keeps its own colour, whatever happens to the others
            points = [at(i, snap["factions"].get(fid, {}).get("provinces", 0)) for i, snap in enumerate(history)]
            color = theme.faction_color(game, fid)
            if len(points) > 1:
                pygame.draw.lines(surface, PARCHMENT_BG, False, points, 6)  # a surface ring
                pygame.draw.lines(surface, color, False, points, 3)
            x, y = points[-1]
            pygame.draw.circle(surface, PARCHMENT_BG, (x, y), 6)
            pygame.draw.circle(surface, color, (x, y), 5)
            ends.append([y, fid, x])
        ends.sort()
        for k in range(1, len(ends)):  # direct labels at the line ends, pushed apart
            ends[k][0] = max(ends[k][0], ends[k - 1][0] + 17)
        for y, fid, x in ends:
            pygame.draw.circle(surface, theme.faction_color(game, fid), (plot.right + 14, y), 4)
            theme.text(surface, game.faction_name(fid).replace("The ", ""), (plot.right + 22, y), 15, theme.INK,
                       anchor="midleft", lift=False)

        # hover: the season under the mouse, every realm's count
        if plot.inflate(0, 20).collidepoint(mouse) and len(history) > 1:
            i = round((mouse[0] - plot.x) / plot.width * (len(history) - 1))
            i = max(0, min(len(history) - 1, i))
            x = at(i, 0)[0]
            pygame.draw.line(surface, ink, (x, plot.y), (x, plot.bottom), 1)
            snap = history[i]
            lines = [f"{SEASONS[snap['round'] % 4]} {game.data.map['start_year'] + snap['round'] // 4}"]
            rows = sorted(self.factions, key=lambda f: -snap["factions"].get(f, {}).get("provinces", 0))
            for fid in rows:
                row = snap["factions"].get(fid, {})
                lines.append((f"{game.faction_name(fid)}: {row.get('provinces', 0)} provinces, "
                              f"{row.get('regiments', 0)} regiments", theme.TEXT))
            theme.tip(pygame.Rect(mouse[0] - 1, mouse[1] - 1, 3, 3), lines)

    # --- the deeds of each realm ---------------------------------------------------------------

    def _table(self, surface, x, y):
        game = self.game
        theme.outlined(surface, "Deeds of the legends", (x, y), 20, theme.GOLD, anchor="topleft", width=1)
        y += 34
        headers = (("Battles won", "won"), ("Battles lost", "lost"), ("Provinces taken", "taken"),
                   ("Provinces lost", "fallen"))
        order = sorted(self.factions, key=lambda f: (f != (game.winner.faction if game.winner else None),
                                                     -len(game.provinces_of(f))))
        for fid in order:
            color = theme.faction_color(game, fid)
            row = game.stats.get(fid, {})
            shield = [(x, y + 3), (x + 13, y + 3), (x + 13, y + 11), (x + 6.5, y + 17), (x, y + 11)]
            pygame.draw.polygon(surface, color, shield)
            pygame.draw.polygon(surface, theme.GOLD, shield, 1)
            name = game.faction_name(fid) + ("  (you)" if fid == game.player else "")
            if fid in game.eliminated:
                name += "  - destroyed"
            theme.text(surface, name, (x + 20, y), 19, theme.PARCHMENT)
            y += 24
            theme.text(surface, f"{len(game.provinces_of(fid))} provinces now", (x + 20, y), 16, theme.TEXT_DIM)
            y += 20
            for i, (label, key) in enumerate(headers):
                cx = x + 20 + (i % 2) * 180
                cy = y + (i // 2) * 19
                theme.text(surface, f"{label}: {row.get(key, 0)}", (cx, cy), 16, theme.TEXT)
            y += 46
            theme.divider(surface, x, x + 360, y)
            y += 12


PARCHMENT_BG = (226, 210, 172)  # behind the chart's lines: a thin ring keeps crossing lines apart
