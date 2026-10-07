"""Generals who learn from the war, and veteran regiments."""

from legendele.game import Game, GeneralFell, Regiment, economy, generals
from legendele.game.battle import Side, predict
from legendele.game.save import from_dict, to_dict


def army_at(game, fid, pid):
    return next(a for a in game.armies_of(fid) if a.province == pid)


def test_ranks_follow_experience(game, monkeypatch):
    monkeypatch.setitem(generals.FALL_CHANCE, "won", 0.0)        # he must live to learn
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.traits, vlad.xp, vlad.rank = [], 0, 0
    assert generals.rank_for(0) == 0 and generals.rank_for(3) == 1 and generals.rank_for(1000) == 8
    for _ in range(3):
        generals.after_battle(game, vlad, won=True)
    assert vlad.xp == 9 and vlad.rank == 2
    assert generals.attack_mult(game, vlad) > 1.0 and generals.resolve_bonus(game, vlad) > 0


def test_traits_change_how_an_army_marches_fights_and_costs(game):
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.traits = []
    plain = economy.balance(game, "voievodat").upkeep
    assert generals.moves(game, vlad) == 4
    generals.give_trait(game, vlad, "swift")
    assert generals.moves(game, vlad) == 5
    assert not generals.give_trait(game, vlad, "drunkard")  # a Swift general is no Drunkard
    generals.give_trait(game, vlad, "greedy")
    assert economy.balance(game, "voievodat").upkeep > plain
    generals.give_trait(game, vlad, "siege_master")
    assert generals.attack_mult(game, vlad, assault=True) > generals.attack_mult(game, vlad)
    assert not generals.give_trait(game, vlad, "tactician")  # three traits at most


def test_a_winter_warrior_does_not_freeze(game):
    for ai in game.ai.values():
        ai.take_turn = lambda game: None
    vlad = army_at(game, "voievodat", "targoviste")
    radu = army_at(game, "voievodat", "craiova")
    vlad.traits, radu.traits = ["winter_warrior"], []
    game.provinces["vlasia"].owner = "zmei"  # enemy ground: no rest, no healing
    game.provinces["vlasia"].garrison = []
    vlad.province = radu.province = "vlasia"
    while game.season != "Autumn":
        game.end_turn()
    before = [sum(r.hp for r in a.regiments) for a in (vlad, radu)]
    game.end_turn()  # winter comes
    after = [sum(r.hp for r in a.regiments) for a in (vlad, radu)]
    assert after[0] == before[0] and after[1] < before[1]


def test_a_general_can_fall_and_a_lieutenant_takes_over(game):
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.xp, vlad.rank = 20, 4
    generals.fall(game, vlad)
    assert vlad.general != "Vlad the Young" and vlad.rank == 0 and vlad.xp == 0
    assert any(isinstance(e, GeneralFell) and e.general == "Vlad the Young" for e in game.events)


def test_veterans_fight_better_and_are_made_in_battle(data):
    units = data.units
    green = Side("voievodat", [Regiment("oteni", 100) for _ in range(3)], "A")
    old = Side("zmei", [Regiment("oteni", 100, xp=12, rank=3) for _ in range(3)], "B")
    assert not predict(green, old, units)[0]  # the same men, but the veterans win
    regiments = [Regiment("oteni", 100)]
    for _ in range(2):
        generals.season_of_battle(regiments, won=True)
    assert regiments[0].rank == 1
    generals.season_of_battle(regiments, won=True)
    generals.season_of_battle(regiments, won=False)
    assert regiments[0].rank == 2


def test_battles_teach_the_survivors(data):
    game = Game.new(data, "voievodat", seed=2)
    for ai in game.ai.values():
        ai.take_turn = lambda game: None
    radu = army_at(game, "voievodat", "craiova")
    radu.regiments += [Regiment("calareti", 90) for _ in range(6)]
    xp = radu.xp
    game.move_army(radu.id, "iron_gates")  # a Dragonkin province: a garrison to fight, or a siege
    if game.provinces["iron_gates"].besieged_by == radu.id:
        game.end_turn()
        game.assault(radu.id)
    assert radu.xp > xp
    assert all(r.xp > 0 for r in radu.regiments)


def test_generals_and_veterans_are_saved(game):
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.xp, vlad.rank, vlad.traits = 9, 2, ["brave"]
    vlad.regiments[0].xp, vlad.regiments[0].rank = 7, 2
    loaded = from_dict(game.data, to_dict(game))
    again = army_at(loaded, "voievodat", "targoviste")
    assert (again.xp, again.rank, again.traits) == (9, 2, ["brave"])
    assert (again.regiments[0].xp, again.regiments[0].rank) == (7, 2)
