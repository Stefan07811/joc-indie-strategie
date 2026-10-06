"""The right-hand side panel: date, victory progress, selection details, chronicle and buttons."""

import pygame

from ..game import agents, diplomacy, economy, generals, legends, state
from . import theme, tips

PAD = 16


class Panel:
    def __init__(self, game, assets):
        self.game = game
        self.assets = assets
        rect = theme.PANEL_RECT
        self.end_turn_rect = pygame.Rect(rect.x + PAD, rect.bottom - 64, rect.width - 2 * PAD, 44)
        third = (rect.width - 2 * PAD - 12) // 3
        self.diplomacy_rect = pygame.Rect(rect.x + PAD, rect.bottom - 132, third, 34)
        self.traditions_rect = pygame.Rect(rect.x + PAD + third + 6, rect.bottom - 132, third, 34)
        self.legends_rect = pygame.Rect(rect.x + PAD + 2 * (third + 6), rect.bottom - 132, third, 34)
        self.actions = []  # (rect, callable): agents' deeds and hiring, rebuilt every frame
        self.feedback = None  # (message, colour) after the last of those
        self.menu_rect = pygame.Rect(rect.right - PAD - 72, rect.y + PAD, 72, 28)
        self.assault_rect = None  # set while the selected army can storm walls
        self.merge_rect = None  # set while the selected army has comrades to absorb
        self.manage_rect = None  # set while one of our provinces is shown
        self.abduct_rect = None  # set while a Dragonkin army can carry off an heir

    def draw(self, surface, *, province=None, army=None, target=None, mouse=(0, 0), agent=None):
        game = self.game
        rect = theme.PANEL_RECT
        theme.frame(surface, rect, accent=theme.faction_color(game, game.player))
        x, y = rect.x + PAD, rect.y + PAD + 4
        width = rect.width - 2 * PAD
        self.assault_rect = self.merge_rect = self.manage_rect = self.abduct_rect = None
        self.actions = []

        theme.outlined(surface, game.date, (x, y - 2), 26, theme.GOLD, anchor="topleft")
        theme.button(surface, self.menu_rect, "Menu", self.menu_rect.collidepoint(mouse))
        y += 32
        y = self._progress(surface, x, y, width)
        y = self._treasury(surface, x, y, width)
        y = self._rule(surface, y)

        if agent is not None:
            y = self._agent(surface, agent, x, y, width, mouse)
        elif army is not None:
            y = self._army(surface, army, x, y, width, target, mouse)
        elif province is not None:
            y = self._province(surface, game.provinces[province], x, y, width, mouse)
        else:
            for line in ("Click one of your banners to select an army,",
                         "then click a highlighted province to march.",
                         "Red circles mean a battle or a siege."):
                theme.text(surface, line, (x, y), 18, theme.TEXT_DIM)
                y += 20
            y += 6
        y = self._rule(surface, y)

        self._chronicle(surface, x, y, width, self.diplomacy_rect.top - 8)
        theme.button(surface, self.diplomacy_rect, "Diplomacy", self.diplomacy_rect.collidepoint(mouse),
                     enabled=not game.over)
        theme.tip(self.diplomacy_rect, ["Diplomacy (D)", "War, peace, alliances, trade, marriages, vassals. "
                                                         "The foreign courts are there too (F)."])
        theme.button(surface, self.legends_rect, "Legends", self.legends_rect.collidepoint(mouse), enabled=not game.over)
        theme.tip(self.legends_rect, ["Legends (L)", "Your quests, and the heroes of the old tales they bring."])
        study = game.studying.get(game.player)
        label = "Traditions" if not study else f"Study ({study['turns_left']})"
        theme.button(surface, self.traditions_rect, label, self.traditions_rect.collidepoint(mouse),
                     enabled=not game.over)
        if study:
            theme.tip(self.traditions_rect, ["Traditions", f"Studying {game.data.techs[study['tech']]['name']}: "
                                                           f"{study['turns_left']} more seasons."])
        theme.text(surface, "Enter: end turn  ·  Tab: next army  ·  Esc: deselect", (rect.centerx, rect.bottom - 82),
                   16, theme.TEXT_DIM, anchor="center")
        theme.button(surface, self.end_turn_rect, "End Turn", self.end_turn_rect.collidepoint(mouse),
                     enabled=not game.over)

    def _progress(self, surface, x, y, width):
        game = self.game
        rules = game.victory_rules
        color = theme.faction_color(game, game.player)
        shield = [(x, y + 2), (x + 13, y + 2), (x + 13, y + 10), (x + 6.5, y + 16), (x, y + 10)]
        pygame.draw.polygon(surface, color, shield)
        pygame.draw.polygon(surface, theme.GOLD, shield, 1)
        theme.outlined(surface, game.faction_name(game.player), (x + 20, y - 1), 18, theme.PARCHMENT,
                       anchor="topleft", width=1)
        y += 22
        owned = game.realm_size(game.player)
        r = theme.text(surface, f"Provinces {owned} / {rules['conquest_provinces']}", (x, y), 18, theme.TEXT_DIM)
        theme.tip(r, tips.conquest(game))
        heart = game.heart_turns.get(game.player, 0)
        r = theme.text(surface, f"Heart held {heart} / {rules['heart_turns']}", (x + width, y), 18,
                       theme.GOLD if heart else theme.TEXT_DIM, anchor="topright")
        theme.tip(r, tips.heart(game))
        return y + 22

    def _treasury(self, surface, x, y, width):
        game = self.game
        t = game.treasury[game.player]
        bal = economy.balance(game, game.player)
        r = theme.text(surface, f"Gold {t.gold}", (x, y), 20, theme.GOLD)
        r = r.union(theme.text(surface, f"({bal.gold:+})", (x + 92, y + 2), 18,
                               theme.GOOD if bal.gold >= 0 else theme.DANGER))
        theme.tip(r, tips.gold(game))
        r = theme.text(surface, f"Food {t.food}", (x + width - 70, y), 20, theme.PARCHMENT, anchor="topright")
        r = r.union(theme.text(surface, f"({bal.food:+})", (x + width, y + 2), 18,
                               theme.GOOD if bal.food >= 0 else theme.DANGER, anchor="topright"))
        theme.tip(r, tips.food(game))
        return y + 22

    def _rule(self, surface, y):
        rect = theme.PANEL_RECT
        theme.divider(surface, rect.x + PAD, rect.right - PAD, y + 5)
        return y + 16

    def _province(self, surface, p, x, y, width, mouse):
        game = self.game
        terrain = game.data.terrain[p.terrain]
        theme.outlined(surface, p.name, (x, y), 24, theme.PARCHMENT, anchor="topleft")
        y += 30
        theme.text(surface, f"Owner: {game.faction_name(p.owner)}", (x, y), 20,
                   theme.faction_color(game, p.owner) if p.owner else theme.TEXT_DIM)
        if p.owner and p.owner != game.player:
            rel = diplomacy.relation(game, game.player, p.owner)
            label, color = {"war": ("at war", theme.DANGER), "peace": ("at peace", theme.TEXT_DIM),
                            "alliance": ("allies", theme.GOOD)}[rel]
            theme.text(surface, label, (x + width, y + 2), 18, color, anchor="topright")
        y += 22
        bonus = round((terrain["defense"] - 1) * 100)
        theme.text(surface, f"{terrain['name']}  ·  march cost {game.enter_cost(game.player, p.id)}"
                            + (f"  ·  defence +{bonus}%" if bonus else ""), (x, y), 18)
        y += 22
        if p.owner == game.player:
            y = self._holdings(surface, p, x, y, width, mouse)
        if p.special == "heart":
            for line in theme.wrap("Hold the Heart and your capital for 8 turns to win a Legendary Victory.",
                                   18, width):
                theme.text(surface, line, (x, y), 18, theme.GOLD)
                y += 19
        capital_of = [f for f in game.data.factions if game.capital_of(f) == p.id]
        if capital_of:
            theme.text(surface, f"Capital of {game.faction_name(capital_of[0])}  ·  walled", (x, y), 18, theme.GOLD)
            y += 20
        if p.garrison:
            who = "Outlaws" if p.owner is None else "Garrison"
            y = self._regiments(surface, f"{who} ({len(p.garrison)}):", p.garrison, x, y, width)
        if p.besieged_by is not None and p.besieged_by in game.armies:
            besieger = game.armies[p.besieged_by]
            theme.text(surface, f"Besieged by {besieger.general}", (x, y), 18, theme.DANGER)
            y += 20
        for a in game.armies_seen(game.player, p.id):
            theme.text(surface, f"• {a.general} ({len(a.regiments)} regiments)", (x, y), 18,
                       theme.faction_color(game, a.faction))
            y += 19
        return y + 6

    def _agent(self, surface, agent, x, y, width, mouse):
        game = self.game
        mine = agent.faction == game.player
        name = agents.name(agent.faction, agent.kind)
        theme.outlined(surface, name, (x, y), 24, theme.PARCHMENT, anchor="topleft")
        y += 30
        theme.text(surface, f"{game.faction_name(agent.faction)}  ·  in {game.provinces[agent.province].name}",
                   (x, y), 18, theme.faction_color(game, agent.faction))
        y += 22
        what = ("Sees the armies here and next door, even those hidden in the woods." if agent.kind == "spy"
                else "Calms your provinces, or stirs up your rivals'.")
        for line in theme.wrap(what, 16, width):
            theme.text(surface, line, (x, y), 16, theme.TEXT_DIM)
            y += 17
        if not mine:
            return y + 6
        theme.text(surface, f"Movement left: {agent.moves_left} / {agents.MOVES}  ·  click a lit province to go",
                   (x, y + 2), 16)
        y += 26
        for action, reason in agents.actions(game, agent):
            _, chance, risk, desc = agents.ACTIONS[action]
            label = {"sabotage": "Sabotage", "calm": "Calm the people", "unrest": "Stir up unrest"}[action]
            if chance < 1:
                label += f"  ({round(chance * 100)}%)"
            rect = pygame.Rect(x, y, width, 32)
            theme.button(surface, rect, label, rect.collidepoint(mouse) and reason is None, enabled=reason is None)
            tip = [label, desc] + ([(f"If it fails, {round(risk * 100)}% chance the agent is caught.", theme.DANGER)]
                                  if risk else []) + ([(reason, theme.DANGER)] if reason else [])
            theme.tip(rect, tip)
            if reason is None:
                self.actions.append((rect, lambda a=action: self._deed(agent.id, a)))
            y += 38
        if self.feedback:
            theme.text(surface, self.feedback[0], (x, y), 16, self.feedback[1])
            y += 20
        return y + 6

    def _deed(self, agent_id, action):
        deed = agents.act(self.game, agent_id, action)
        self.feedback = (("Done!" if deed.success else "It failed" + (", and the agent was caught." if deed.caught
                                                                       else ".")),
                         theme.GOOD if deed.success else theme.DANGER)

    def _hire(self, kind, pid):
        try:
            agents.hire(self.game, self.game.player, kind, pid)
            self.feedback = (f"A {agents.name(self.game.player, kind).lower()} waits in "
                             f"{self.game.provinces[pid].name}.", theme.GOOD)
        except ValueError as e:
            self.feedback = (str(e), theme.DANGER)

    def _holdings(self, surface, p, x, y, width, mouse):
        game = self.game
        gold, food = economy.province_yield(game, p)
        theme.text(surface, f"Yields {gold} gold and {food} food a season", (x, y), 18, theme.TEXT_DIM)
        y += 20
        built = [game.data.buildings[b]["name"] for b in p.buildings]
        if p.construction:
            c = p.construction
            built.append(f"{game.data.buildings[c['building']]['name']} ({c['turns_left']} more)")
        lines = theme.wrap("Buildings: " + (", ".join(built) or "none"), 18, width)
        if p.recruits:
            names = [game.data.units[u]["name"] for u in p.recruits]
            lines += theme.wrap("Training: " + ", ".join(names), 18, width)
        for line in lines:
            theme.text(surface, line, (x, y), 18)
            y += 19
        y = self._order(surface, p, x, y, width)
        self.manage_rect = pygame.Rect(x, y + 4, width, 32)
        theme.button(surface, self.manage_rect, "Manage province  (M)", self.manage_rect.collidepoint(mouse),
                     enabled=not game.over)
        y += 40
        half = (width - 6) // 2
        for i, kind in enumerate(agents.KINDS):
            rect = pygame.Rect(x + i * (half + 6), y, half, 28)
            reason = agents.hire_blocker(game, game.player, kind)
            label = f"Hire {agents.name(game.player, kind).lower()} ({agents.COST[kind]})"
            theme.button(surface, rect, label, rect.collidepoint(mouse) and reason is None,
                         enabled=reason is None and not game.over)
            theme.tip(rect, [label, "Agents move three provinces a season, anywhere." + (" " + reason if reason else "")])
            if reason is None:
                self.actions.append((rect, lambda k=kind, pid=p.id: self._hire(k, pid)))
        return y + 34

    def _order(self, surface, p, x, y, width):
        order, parts = legends.public_order(self.game, p)
        mood, color = (("Content", theme.GOOD) if order >= 3 else ("Uneasy", theme.HIGHLIGHT) if order >= 0
                       else ("Rebellious!", theme.DANGER))
        r = theme.text(surface, f"Order {order:+}  ·  {mood}", (x, y), 18, color)
        theme.tip(r, tips.order(self.game, p))
        y += 19
        detail = ", ".join(f"{name} {points:+}" for name, points in parts)
        for line in theme.wrap(detail, 16, width):
            theme.text(surface, line, (x, y), 16, theme.TEXT_DIM)
            y += 17
        return y

    def _army(self, surface, army, x, y, width, target, mouse):
        game = self.game
        name = theme.outlined(surface, army.general, (x, y), 24, theme.PARCHMENT, anchor="topleft")
        for k in range(army.rank):
            theme.star(surface, (name.right + 9 + k * 12, name.centery))
        theme.tip(name.union(pygame.Rect(name.right, name.y, 12 * army.rank + 8, name.height)),
                  tips.general(game, army))
        y += 30
        theme.text(surface, f"{game.faction_name(army.faction)}  ·  in {game.provinces[army.province].name}",
                   (x, y), 18, theme.faction_color(game, army.faction))
        y += 22
        mine = army.faction == game.player
        if mine:
            theme.text(surface, f"Movement left: {army.moves_left} / {generals.moves(game, army)}", (x, y), 18)
            nxt = generals.next_rank_xp(army)
            if nxt:
                low = generals.RANKS[army.rank]
                bar = pygame.Rect(x + width - 90, y + 6, 90, 6)
                theme.gauge(surface, bar, (army.xp - low) / (nxt - low), theme.GOLD)
                theme.tip(bar.inflate(0, 10), ["Experience", f"{army.xp} / {nxt} to rank {army.rank + 1}.",
                                               ("Battles teach generals: a victory more than a defeat, and most "
                                                "of all a victory against the odds.", theme.TEXT_DIM)])
            y += 22
        if army.traits:
            tx = x
            for trait in army.traits:
                t = game.data.traits[trait]
                label = t["name"] + ("  " if trait != army.traits[-1] else "")
                r = theme.text(surface, label, (tx, y), 17, theme.GOOD if t["good"] else theme.DANGER)
                theme.tip(r, [t["name"], t["description"]])
                tx = r.right + 6
            y += 20
        y = self._regiments(surface, None, army.regiments, x, y, width)
        abilities = sorted({game.data.abilities[a]["name"] for a in
                            (game.data.units[r.unit]["ability"] for r in army.regiments) if a})
        ability_ids = sorted({a for a in (game.data.units[r.unit]["ability"] for r in army.regiments) if a})
        start = y
        for line in theme.wrap("Abilities: " + ", ".join(abilities), 16, width) if abilities else ():
            theme.text(surface, line, (x, y), 16, theme.TEXT_DIM)
            y += 17
        if ability_ids:
            theme.tip((x, start, width, y - start),
                      ["Abilities"] + [(f"{game.data.abilities[a]['name']}: {game.data.abilities[a]['description']}",
                                        theme.TEXT) for a in ability_ids])
        if mine and legends.traits(game, army.faction).get("abduction"):
            y = self._abduction(surface, army, x, y + 2, width, mouse)
        comrades = [a for a in game.armies_in(army.province) if a.faction == army.faction and a.id != army.id]
        if mine and comrades and len(army.regiments) < game.rules["max_regiments"]:
            self.merge_rect = pygame.Rect(x, y, width, 30)
            theme.button(surface, self.merge_rect, "Merge the armies here", self.merge_rect.collidepoint(mouse),
                         enabled=not game.over)
            y += 36
        if mine and game.provinces[army.province].owner == game.player:
            theme.text(surface, "M: manage this province", (x, y), 17, theme.TEXT_DIM)
            y += 20

        if mine and game.besieging(army):
            p = game.provinces[army.province]
            for line in theme.wrap(f"Besieging {p.name}: the defenders starve each season.", 17, width):
                theme.text(surface, line, (x, y), 17, theme.TEXT_DIM)
                y += 18
            y += 4
            self.assault_rect = pygame.Rect(x, y, width, 34)
            theme.button(surface, self.assault_rect, "Assault the walls",
                         self.assault_rect.collidepoint(mouse), enabled=army.moves_left > 0 and not game.over)
            y += 40
            y = self._forecast(surface, game.forecast(army, army.province, seen_only=True), x, y)
        elif mine and target is not None:
            y = self._forecast(surface, game.forecast(army, target, seen_only=True), x, y,
                               game.provinces[target].name)
            reach = game.reachable(army).get(target)
            origin = ([army.province] + reach.path)[-2] if reach else army.province
            river = game.river_between(origin, target)
            if river:
                bridge = target in game.provinces[origin].roads
                malus = round((1 - state.RIVER_ATTACK.get(river, 0.9)) * 100)
                r = theme.text(surface, f"Across the {river}: -{malus}% attack" + ("" if bridge else ", no bridge"),
                               (x, y), 17, theme.HIGHLIGHT)
                theme.tip(r, [f"The {river}", "Attacking across a river is hard: the men wade in under the enemy's "
                                              "blows." + ("" if bridge else " With no road there is no bridge, and the "
                                                                            "crossing costs a movement point more.")])
                y += 20
        return y + 6

    def _abduction(self, surface, army, x, y, width, mouse):
        game = self.game
        pid, reason = legends.abduction_target(game, army)
        if reason:
            for line in theme.wrap(f"Abduct an heir: {reason[0].lower()}{reason[1:]}.", 16, width):
                theme.text(surface, line, (x, y), 16, theme.TEXT_DIM)
                y += 17
            return y + 3
        chance = round(legends.abduction_chance(game, army, pid) * 100)
        theme.text(surface, f"The heir of {game.provinces[pid].name} is within reach.", (x, y), 16, theme.GOLD)
        self.abduct_rect = pygame.Rect(x, y + 18, width, 30)
        theme.button(surface, self.abduct_rect, f"Abduct the heir  ({chance}%)",
                     self.abduct_rect.collidepoint(mouse), enabled=not game.over)
        return y + 54

    def _forecast(self, surface, forecast, x, y, place=None):
        if forecast is None:
            return y
        wins, share = forecast
        if wins and share >= 0.7:
            verdict, color = "Decisive victory", theme.GOOD
        elif wins:
            verdict, color = "Costly victory", theme.HIGHLIGHT
        else:
            verdict, color = "Likely defeat", theme.DANGER
        r = theme.text(surface, f"Forecast{' at ' + place if place else ''}: {verdict}", (x, y), 18, color)
        theme.tip(r, ["Battle forecast", f"If the battle were fought now, you would keep about {round(share * 100)}% "
                                         "of your strength." if wins else "Your army would most likely be beaten.",
                      ("Only what your scouts can see is counted.", theme.TEXT_DIM)])
        return y + 22

    def _regiments(self, surface, title, regiments, x, y, width):
        units = self.game.data.units
        if title:
            theme.text(surface, title, (x, y), 18, theme.TEXT_DIM)
            y += 20
        for r in regiments:
            u = units[r.unit]
            icon = self.assets.get(f"unit_{u['icon']}", theme.faction_color(self.game, u["faction"]), 2)
            surface.blit(icon, icon.get_rect(center=(x + 8, y + 7)))
            name = theme.text(surface, u["name"], (x + 20, y), 18)
            if r.rank:
                theme.chevrons(surface, (name.right + 6, y + 13), r.rank)
            theme.tip((x, y, width, 18), tips.unit(self.game, r.unit, r))
            bar = pygame.Rect(x + width - 90, y + 5, 90, 7)
            share = max(0.0, min(1.0, r.hp / u["hp"]))
            theme.gauge(surface, bar, share,
                        theme.GOOD if share > 0.5 else theme.HIGHLIGHT if share > 0.25 else theme.DANGER)
            y += 19
        return y + 4

    def _chronicle(self, surface, x, y, width, bottom):
        theme.outlined(surface, "Chronicle", (x, y), 19, theme.GOLD, anchor="topleft", width=1)
        y += 26
        lines = []
        for entry in reversed(self.game.log):
            lines.extend((line, entry is self.game.log[-1]) for line in theme.wrap(entry, 17, width))
            if len(lines) * 18 > bottom - y:
                break
        for line, latest in lines:
            if y + 18 > bottom:
                break
            theme.text(surface, line, (x, y), 17, theme.TEXT if latest else theme.TEXT_DIM)
            y += 18
