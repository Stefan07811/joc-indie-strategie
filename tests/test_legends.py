"""Faction powers, unit abilities, public order and Outlaw uprisings."""

import random

import pytest

from legendele.game import Abduction, Battle, Captured, Game, MoveError, Rebellion, Regiment, economy, legends
from legendele.game.battle import Side, resolve


@pytest.fixture
def game(data):
    g = Game.new(data, "voievodat", seed=1)

    class Idle:
        def take_turn(self, game):
            pass
    for fid in g.ai:
        g.ai[fid] = Idle()
    return g


def army_at(game, fid, pid):
    return next(a for a in game.armies_of(fid) if a.province == pid)


def regs(data, *unit_ids):
    return [Regiment(u, data.units[u]["hp"]) for u in unit_ids]


# --- unit abilities ----------------------------------------------------------------------

def average_losses(data, attacker_units, defender_units, **defender_kwargs):
    total = 0
    for seed in range(30):
        a = Side("x", regs(data, *attacker_units), "A")
        d = Side("y", regs(data, *defender_units), **defender_kwargs)
        total += resolve(a, d, data.units, random.Random(seed)).defender.losses
    return total / 30


def test_flying_fire_ignores_walls(data):
    walls = dict(defense_mult=1.5, walls=True)
    open_field = dict(defense_mult=1.0)
    wyrms = ["balauri"] * 3
    whelps = ["pui_de_zmeu"] * 3
    target = ["oteni"] * 4
    wyrm_ratio = average_losses(data, wyrms, target, **walls) / average_losses(data, wyrms, target, **open_field)
    whelp_ratio = average_losses(data, whelps, target, **walls) / average_losses(data, whelps, target, **open_field)
    assert wyrm_ratio > whelp_ratio


def test_life_drain_heals_vampires(data):
    import copy
    no_drain = copy.deepcopy(data.units)
    no_drain["strigoi"]["ability"] = None

    def hp_left(units):
        total = 0
        for seed in range(30):
            vampires = Side("strigoi", regs(data, "strigoi", "strigoi"), "V")
            resolve(vampires, Side("y", regs(data, "oteni", "oteni")), units, random.Random(seed))
            total += sum(r.hp for r in vampires.regiments)
        return total
    assert hp_left(data.units) > hp_left(no_drain)


def test_forest_ambush_only_in_forests(data):
    def losses(ambush):
        total = 0
        for seed in range(30):
            a = Side("x", regs(data, "oteni", "oteni", "oteni"), "A")
            d = Side("iele", regs(data, "valve", "valve"), ambush_ground=ambush)
            total += resolve(a, d, data.units, random.Random(seed)).attacker.losses
        return total
    assert losses(True) > losses(False)


def test_dread_and_dance_weaken_the_enemy(data):
    plain = average_losses(data, ["oteni"] * 3, ["morti"] * 3)
    with_dread = average_losses(data, ["oteni"] * 3, ["morti", "morti", "moroi"])
    assert with_dread != plain  # the Wraith changes the fight
    dancers = Side("iele", regs(data, "iele_dansatoare", "iele_dansatoare"), "D")
    assert legends.traits  # module loaded
    counts = __import__("legendele.game.battle", fromlist=["x"])._abilities(dancers, data.units)
    assert counts == {"enchanting_dance": 2}


# --- faction powers ----------------------------------------------------------------------

def test_church_weakens_creatures(game):
    p = game.provinces["craiova"]
    before = legends.attack_modifier(game, "zmei", "craiova")
    p.buildings = ["church"]
    assert legends.attack_modifier(game, "zmei", "craiova") == pytest.approx(before * 0.8)
    assert legends.attack_modifier(game, "voievodat", "craiova") == 1.0  # men are not troubled by bells


def test_only_the_principality_builds_churches(data):
    g = Game.new(data, "zmei", seed=1)
    g.treasury["zmei"].gold = 1000
    assert economy.building_blocker(g, "zmei", "retezat", "church") == "Not one of yours"
    assert economy.building_blocker(g, "zmei", "retezat", "hoard") is None


def test_dragon_hoard_interest(data):
    g = Game.new(data, "zmei", seed=1)
    g.treasury["zmei"].gold = 1000
    assert legends.interest(g, "zmei") == 15  # 5% of 1000 is 50, capped at 15
    g.provinces["retezat"].buildings = ["hoard"]
    assert legends.interest(g, "zmei") == 30
    g.treasury["zmei"].gold = 100
    assert legends.interest(g, "zmei") == 5
    assert economy.balance(g, "zmei").interest == 5
    assert legends.interest(g, "iele") == 0


def test_abduction(data):
    g = Game.new(data, "zmei", seed=4)
    army = g.add_army("zmei", "arges", "Kidnapper", ["pui_de_zmeu"])  # next to Târgoviște
    g.treasury["voievodat"].gold = 300
    target, reason = legends.abduction_target(g, army)
    assert target == "targoviste" and reason is None
    events = g.abduct(army.id)
    abduction = next(e for e in events if isinstance(e, Abduction))
    if abduction.success:
        assert abduction.ransom == 150 and g.treasury["voievodat"].gold == 150
    else:
        assert army.id not in g.armies or army.regiments[0].hp < 100 + 20
    assert army.id not in g.armies or army.moves_left == 0
    army2 = g.add_army("zmei", "arges", "Second", ["pui_de_zmeu"])
    assert "next abduction" in legends.abduction_target(g, army2)[1]
    with pytest.raises(MoveError):
        g.abduct(army2.id)


def test_only_the_dragonkin_abduct(game):
    vlad = army_at(game, "voievodat", "targoviste")
    assert legends.abduction_target(game, vlad) == (None, "Only the Dragonkin abduct heirs")


def test_hora_wears_down_invaders(game):
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.province = "suceava"  # Fae land
    full = sum(r.hp for r in vlad.regiments)
    game.end_turn()
    assert sum(r.hp for r in vlad.regiments) < full
    assert any("Hora" in line for line in game.log)


def test_fae_hide_in_the_forest(game):
    fae = army_at(game, "iele", "maramures")
    assert not legends.visible_to(game, "voievodat", fae)
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.province = "cluj"  # next door
    assert legends.visible_to(game, "voievodat", fae)
    fae.province = "mures"  # plains: no cover
    vlad.province = "targoviste"
    assert legends.visible_to(game, "voievodat", fae)


def test_the_dead_rise_after_a_revenant_victory(data):
    g = Game.new(data, "strigoi", seed=2)
    dead = g.add_army("strigoi", "barlad", "Necromancer", ["varcolaci"] * 6)
    victims = g.add_army("voievodat", "bacau", "Victims", ["oteni"] * 3)
    g.provinces["bacau"].garrison = []
    size = len(dead.regiments)
    events = g.move_army(dead.id, "bacau")
    result = next(e.result for e in events if isinstance(e, Battle))
    assert result.attacker_won
    risen = len(dead.regiments) - size + result.attacker.start_regiments - result.attacker.end_regiments
    assert risen >= 1 and any("rise again" in n for n in result.notes)
    assert victims.id not in g.armies or victims.province != "bacau"


def test_revenants_fight_harder_in_winter(data):
    g = Game.new(data, "strigoi", seed=2)
    summer = legends.attack_modifier(g, "strigoi", "barlad")
    g.round = 3
    assert legends.attack_modifier(g, "strigoi", "barlad") == pytest.approx(summer * 1.15)


# --- public order and rebellions ---------------------------------------------------------

def test_order_of_a_quiet_province(game):
    order, parts = legends.public_order(game, game.provinces["craiova"])
    assert order == 2 + 3  # base, plus Radu's army and the militia (capped at 3)
    assert dict(parts)["Base"] == 2


def test_fresh_conquests_are_restless(game):
    p = game.provinces["arges"]
    p.captured_round = game.round
    p.garrison = []
    order, parts = legends.public_order(game, p)
    assert order == 2 - 6 and ("Recently conquered", -6) in parts


def test_hunger_debt_and_churches_change_order(game):
    p = game.provinces["arges"]
    base, _ = legends.public_order(game, p)
    p.buildings = ["church"]
    game.treasury["voievodat"].food = 0
    game.treasury["voievodat"].gold = -1
    order, _ = legends.public_order(game, p)
    assert order == base + 2 - 3 - 2


def test_a_restless_province_rises_up(game):
    for ai in game.ai.values():
        ai.take_turn = lambda game: None  # nobody marches in to calm (or stir) things
    p = game.provinces["arges"]
    p.garrison = []
    for _ in range(12):
        p.captured_round = game.round  # freshly conquered and hungry, season after season
        game.treasury["voievodat"].food = -50
        game.end_turn()
        if any(isinstance(e, Rebellion) for e in game.events):
            break
    rebellion = next(e for e in game.events if isinstance(e, Rebellion))
    assert rebellion.province == "arges" and rebellion.faction == "voievodat"


def test_rebels_take_an_undefended_province_as_free_land(game):
    p = game.provinces["arges"]
    p.garrison = []
    rebels = game.add_army(legends.REBELS, "arges", "Iancu", ["haiduc_brigands", "haiduc_marksmen"])
    game._arrive(rebels, None)
    assert p.owner is None and len(p.garrison) == 2 and rebels.id not in game.armies
    assert any(isinstance(e, Captured) and e.faction == legends.REBELS for e in game.events)


def test_rebels_besiege_a_garrison_and_can_be_crushed(game):
    p = game.provinces["arges"]
    rebels = game.add_army(legends.REBELS, "arges", "Iancu", ["haiduc_brigands"])
    game._arrive(rebels, None)
    assert p.besieged_by == rebels.id
    vlad = army_at(game, "voievodat", "targoviste")
    game.move_army(vlad.id, "arges")  # relief force
    assert rebels.id not in game.armies
    assert p.besieged_by is None and p.owner == "voievodat"


def test_ai_uses_its_legends(data):
    seen = set()
    for seed in range(6):
        g = Game.new(data, "voievodat", seed=seed)
        for _ in range(20):
            g.end_turn()
            if g.over:
                break
        for p in g.provinces.values():
            seen.update(b for b in p.buildings if data.buildings[b].get("faction"))
        seen.update("abduction" for e in g.events if isinstance(e, Abduction))
    assert {"hoard", "ring", "crypt"} & seen and "abduction" in seen
