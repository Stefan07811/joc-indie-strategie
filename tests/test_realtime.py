"""Real-time battles: the simulation, its tie-in with the campaign, and the battle screen."""

import random

import pygame
import pytest

from legendele.game import Battle, Game, battle, diplomacy
from legendele.game.battle import Regiment, Side
from legendele.game.realtime import FIELD_H, TIME_LIMIT, WALL_X, Battlefield


def regs(data, *unit_ids):
    return [Regiment(u, data.units[u]["hp"]) for u in unit_ids]


def field(data, attackers, defenders, terrain="plains", kind="field", seed=1, walls=False, player_side=None):
    a = Side("voievodat", regs(data, *attackers), "Vlad")
    d = Side("zmei", regs(data, *defenders), "Pajura", defense_mult=1.5 if walls else 1.0, walls=walls,
             resolve_bonus=battle.WALLS_RESOLVE if walls else 0.0, creature=True)
    return Battlefield(a, d, data.units, terrain, kind, random.Random(seed), province="cluj", player_side=player_side)


@pytest.mark.parametrize("terrain", ["plains", "forest", "hills", "marsh", "mountains"])
def test_the_stronger_army_wins_on_any_ground(data, terrain):
    f = field(data, ["oteni"] * 5 + ["arcasi"] * 2 + ["calareti"], ["pui_de_zmeu"] * 2, terrain)
    result = f.finish()
    assert result.attacker_won and result.kind == "field" and f.time < TIME_LIMIT
    assert result.defender.end_hp < result.defender.start_hp


def test_losses_land_on_the_real_regiments(data):
    f = field(data, ["oteni"] * 4, ["pui_de_zmeu"] * 2)
    attackers = f.sides[0].regiments
    originals = list(attackers)
    result = f.finish()
    assert sum(r.hp for r in attackers) == pytest.approx(result.attacker.end_hp)
    assert all(r in originals for r in attackers)
    assert all(r.hp >= battle.MIN_HP for s in f.sides for r in s.regiments)


def test_same_seed_same_battle(data):
    a = field(data, ["oteni", "arcasi", "calareti"], ["pui_de_zmeu", "spiridusi"], seed=4).finish()
    b = field(data, ["oteni", "arcasi", "calareti"], ["pui_de_zmeu", "spiridusi"], seed=4).finish()
    assert (a.winner, a.rounds, a.attacker.end_hp, a.defender.end_hp) == \
        (b.winner, b.rounds, b.attacker.end_hp, b.defender.end_hp)


def test_agrees_with_the_auto_resolve_on_clear_fights(data):
    for attackers, defenders in ((["oteni"] * 6, ["oteni"] * 2), (["oteni"] * 2, ["pui_de_zmeu"] * 4)):
        rt = field(data, attackers, defenders).finish()
        auto = battle.resolve(Side("voievodat", regs(data, *attackers), "V"),
                              Side("zmei", regs(data, *defenders), "P", creature=True), data.units, random.Random(1))
        assert rt.winner == auto.winner


def test_assault_goes_through_the_gates(data):
    f = field(data, ["oteni"] * 6, ["oteni"] * 2, kind="assault", walls=True)
    assert any(b.kind == "wall" for b in f.blocks)
    result = f.finish()
    assert result.attacker_won and result.kind == "assault"
    survivors = [u for u in f.units if u.side == 0 and u.ready]
    assert any(u.x > WALL_X for u in survivors)  # someone got inside


def test_walls_protect_only_those_behind_them(data):
    f = field(data, ["oteni"], ["oteni"], kind="assault", walls=True)
    attacker, defender = f.units[0], f.units[1]
    attacker.fighting = defender.id
    defender.x, attacker.x = WALL_X + 40, WALL_X + 10
    inside = f._blow(attacker, defender, 1.0)
    defender.x, attacker.x = WALL_X - 60, WALL_X - 100
    outside = f._blow(attacker, defender, 1.0)
    assert outside > inside * 1.2


def test_a_blow_from_behind_hurts_more(data):
    f = field(data, ["oteni"], ["oteni"])
    attacker, defender = f.units[0], f.units[1]
    attacker.fighting = defender.id
    defender.facing = 3.1416  # facing left
    attacker.x, attacker.y, defender.x, defender.y = 400, 300, 440, 300  # attacker in front
    f.rng = random.Random(0)
    front = f._blow(attacker, defender, 1.0)
    attacker.x = 480  # now behind
    f.rng = random.Random(0)
    rear = f._blow(attacker, defender, 1.0)
    assert rear == pytest.approx(front * 1.6) and defender.shaken_until > f.time


def test_archers_shoot_from_afar(data):
    f = field(data, ["arcasi"], ["oteni"], player_side=0)
    archer, target = f.units[0], f.units[1]
    archer.x, archer.y, target.x, target.y = 400, 300, 600, 300
    f.step(0.1)
    assert archer.shooting == target.id and target.regiment.hp < 100


def test_orders_move_and_halt(data):
    f = field(data, ["oteni", "oteni"], ["oteni"], player_side=0)
    ids = [u.id for u in f.units if u.side == 0]
    f.order_move(ids, 300, 150)
    start = [(f.unit(i).x, f.unit(i).y) for i in ids]
    for _ in range(30):
        f.step(1 / 30)
    assert all(f.unit(i).y < y for i, (_, y) in zip(ids, start))
    f.order_halt(ids)
    assert all(f.unit(i).order is None for i in ids)


def test_withdrawing_loses_the_battle(data):
    f = field(data, ["oteni"] * 5, ["oteni"], player_side=0)
    f.withdraw(0)
    assert f.finish().winner == "defender"


def test_time_runs_out_for_the_attacker(data, monkeypatch):
    from legendele.game import realtime
    monkeypatch.setattr(realtime, "DEFENDER_HOLD", 1e9)  # the defenders sit tight...
    f = field(data, ["oteni"], ["oteni"], player_side=0)  # ...and the player's attackers never move
    while not f.over:
        f.step(1.0)
    assert f.result.winner == "defender" and f.time >= TIME_LIMIT


# --- the campaign takes the battle from the hook -----------------------------------------

def test_fight_hook_takes_only_the_players_battles(data):
    game = Game.new(data, "voievodat", seed=3)
    calls = []

    def hook(g, attackers, defenders, pid, kind):
        calls.append((attackers.faction, defenders.faction, pid, kind))
        return Battlefield(attackers, defenders, g.data.units, g.provinces[pid].terrain, kind, g.rng,
                           province=pid).finish()
    game.fight_hook = hook
    vlad = next(a for a in game.armies_of("voievodat") if a.province == "targoviste")
    events = game.move_army(vlad.id, "retezat")
    assert calls == [("voievodat", "zmei", "retezat", "field")]
    assert any(isinstance(e, Battle) for e in events)
    for _ in range(4):
        game.end_turn()
    assert all("voievodat" in c[:2] for c in calls)


def test_hook_returning_none_keeps_the_auto_resolve(data):
    game = Game.new(data, "voievodat", seed=3)
    game.fight_hook = lambda *args: None
    vlad = next(a for a in game.armies_of("voievodat") if a.province == "targoviste")
    assert any(isinstance(e, Battle) for e in game.move_army(vlad.id, "retezat"))


# --- the battle screen -------------------------------------------------------------------

@pytest.fixture(scope="module")
def app(data):
    from legendele.ui.app import App
    return App(data)


def test_battle_screen_controls(app, data):
    from legendele.ui.battle_screen import BattleScreen
    game = Game.new(data, "voievodat", seed=1)
    f = field(data, ["oteni", "oteni", "arcasi"], ["pui_de_zmeu"], player_side=0)
    screen = BattleScreen(app, game, f)
    screen.draw(app.screen)
    assert screen.paused
    mine = [u for u in f.units if u.side == 0]
    # drag a box around our regiments, then order them to march
    xs, ys = [u.x for u in mine], [u.y for u in mine]
    screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(min(xs) - 30, min(ys) - 30), button=1))
    screen.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(max(xs) + 30, max(ys) + 30), button=1))
    assert screen.selected == {u.id for u in mine}
    screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(640, 300), button=3))
    assert all(u.order and u.order[0] == "move" for u in mine)
    enemy = next(u for u in f.units if u.side == 1)
    screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(enemy.x, enemy.y), button=3))
    assert all(u.order == ("attack", enemy.id) for u in mine)
    screen.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    screen.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_f))
    assert not screen.paused and screen.speed == 1
    for _ in range(60):
        screen.update(1 / 30)
    screen.draw(app.screen)
    assert f.time > 0
    screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=screen.buttons["auto"].center, button=1))
    assert f.over
    screen.draw(app.screen)
    screen.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert screen.result is f.result


def test_question_and_settings(app, data):
    from legendele.ui.battle_screen import BattleQuestion, fight
    game = Game.new(data, "voievodat", seed=1)
    a = Side("voievodat", regs(data, "oteni"), "V")
    d = Side("zmei", regs(data, "pui_de_zmeu"), "P", creature=True)
    question = BattleQuestion(app, game, a, d, "cluj", "field")
    question.draw(app.screen)
    question.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
    assert question.answer is False
    app.settings["battles"] = "auto"
    assert fight(app, game, a, d, "cluj", "field") is None  # auto: the campaign resolves it


def test_settings_cycle_the_battle_mode(app):
    from legendele.ui.menus import SettingsScreen
    from legendele import profile
    app.settings["battles"] = "ask"
    screen = SettingsScreen(app, back=app.scene)
    screen.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=screen.controls["battles"].center, button=1))
    assert app.settings["battles"] == "fight" and profile.load_settings()["battles"] == "fight"
    assert diplomacy  # imported for the campaign tests above
    assert FIELD_H == 600


def test_every_regiment_has_its_soldiers_drawn(app, data):
    from legendele.ui import battle_art
    for key, unit in data.units.items():
        for frame in range(5):
            image = battle_art.figure(unit["icon"], (200, 40, 40), frame, frame % 2 == 1)
            assert image.get_width() > 4 and image.get_height() > 4, key
        assert unit["icon"] in battle_art.FIGURES, key


def test_soldiers_fall_as_their_regiment_bleeds(app, data):
    from legendele.ui import battle_art
    f = field(data, ["oteni"], ["pui_de_zmeu"])
    troops = battle_art.Troops(f, data.units, [(200, 40, 40), (40, 40, 200)], battle_art.paint_field(f))
    effects = battle_art.Effects(f, data.units, troops)
    troops.update(0, effects)
    spearmen = f.units[0]
    full = sum(m.alive for m in troops.men[spearmen.id])
    spearmen.regiment.hp /= 2
    troops.update(0.1, effects)
    assert sum(m.alive for m in troops.men[spearmen.id]) == full // 2
    spearmen.state = "dead"
    troops.update(0.1, effects)
    assert not any(m.alive for m in troops.men[spearmen.id])
    assert len(troops.sprites(f.time)) == sum(m.alive for m in troops.men[f.units[1].id])
