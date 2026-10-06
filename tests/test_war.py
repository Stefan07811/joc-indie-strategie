"""Conquest, sieges, retreats, elimination and victory on the campaign map."""

import pytest

from legendele.game import Battle, Captured, Eliminated, Game, MoveError, Regiment, SiegeStarted, Victory


@pytest.fixture
def game(data):
    return Game.new(data, "voievodat", seed=3)


def army_at(game, fid, pid):
    return next(a for a in game.armies_of(fid) if a.province == pid)


def no_ai(game):
    class Idle:
        def take_turn(self, game):
            pass
    for fid in game.ai:
        game.ai[fid] = Idle()


def test_walking_into_an_undefended_province_captures_it(game):
    radu = army_at(game, "voievodat", "craiova")
    game.provinces["iron_gates"].garrison = []  # its militia has been called away
    events = game.move_army(radu.id, "iron_gates")  # Dragonkin land, no army, no garrison
    assert game.provinces["iron_gates"].owner == "voievodat"
    assert any(isinstance(e, Captured) and e.previous == "zmei" for e in events)
    assert radu.moves_left == 0


def test_a_garrison_means_a_siege_that_starves_it_out(game):
    no_ai(game)
    vlad = army_at(game, "voievodat", "targoviste")
    events = game.move_army(vlad.id, "buzau")
    buzau = game.provinces["buzau"]
    assert any(isinstance(e, SiegeStarted) for e in events)
    assert buzau.owner is None and buzau.besieged_by == vlad.id
    start = sum(r.hp for r in buzau.garrison)
    game.end_turn()
    assert sum(r.hp for r in buzau.garrison) < start
    for _ in range(8):
        game.end_turn()
    assert buzau.owner == "voievodat"
    assert all(game.data.units[r.unit]["faction"] == "voievodat" for r in buzau.garrison)  # our own militia


def test_leaving_lifts_the_siege(game):
    no_ai(game)
    vlad = army_at(game, "voievodat", "targoviste")
    game.move_army(vlad.id, "buzau")
    game.end_turn()
    game.move_army(vlad.id, "targoviste")
    assert game.provinces["buzau"].besieged_by is None


def test_assault_takes_the_walls_or_throws_us_back(game):
    no_ai(game)
    vlad = army_at(game, "voievodat", "targoviste")
    game.move_army(vlad.id, "buzau")
    with pytest.raises(MoveError):
        game.assault(vlad.id)  # no moves left this turn
    game.end_turn()
    events = game.assault(vlad.id)
    result = next(e.result for e in events if isinstance(e, Battle))
    assert result.kind == "assault"
    if result.attacker_won:
        assert game.provinces["buzau"].owner == "voievodat"
    else:
        assert game.provinces["buzau"].besieged_by is None
        assert vlad.id not in game.armies or vlad.province != "buzau"


def test_a_lost_attack_falls_back_to_where_it_came_from(game):
    no_ai(game)
    radu = army_at(game, "voievodat", "craiova")
    radu.regiments = [Regiment("oteni", 30)]
    pajura = army_at(game, "zmei", "retezat")
    events = game.move_army(radu.id, "retezat")
    result = next(e.result for e in events if isinstance(e, Battle))
    assert not result.attacker_won
    assert radu.id not in game.armies or radu.province == "craiova"
    assert pajura.province == "retezat"


def test_beaten_defenders_retreat_or_die(game):
    no_ai(game)
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.regiments += [Regiment("calareti", 90) for _ in range(5)]
    victim = army_at(game, "zmei", "hunedoara")
    victim.regiments = [Regiment("morti", 20)]
    game.provinces["banat"].owner = "voievodat"
    game.provinces["banat"].garrison = []
    vlad.province = "banat"
    game.move_army(vlad.id, "hunedoara")
    assert victim.id not in game.armies or victim.province != "hunedoara"
    assert vlad.province == "hunedoara"


def test_losing_every_province_eliminates_a_faction(game):
    no_ai(game)
    for p in game.provinces_of("iele")[1:]:
        p.owner = "voievodat"
    last = game.provinces_of("iele")[0]
    last.garrison = []
    for a in game.armies_in(last.id):
        del game.armies[a.id]
    neighbour = next(n for n in last.neighbors if game.provinces[n].owner == "voievodat")
    army = game.add_army("voievodat", neighbour, "Test", ["calareti"])
    events = game.move_army(army.id, last.id)
    assert any(isinstance(e, Eliminated) and e.faction == "iele" for e in events)
    assert "iele" not in game.turn_order and not game.armies_of("iele")


def test_conquest_victory(game):
    no_ai(game)
    capitals = {game.capital_of(f) for f in game.turn_order}
    others = [p for p in game.provinces.values()
              if p.owner != "voievodat" and p.id not in capitals and not game.armies_in(p.id)]
    needed = game.victory_rules["conquest_provinces"]
    short = needed - 1 - len(game.provinces_of("voievodat"))
    for p in others[:short]:
        p.owner = "voievodat"
    last = next(p for p in others[short:] if any(game.provinces[n].owner == "voievodat" for n in p.neighbors))
    last.garrison = []
    assert len(game.provinces_of("voievodat")) == needed - 1
    army = game.add_army("voievodat", next(n for n in last.neighbors if game.provinces[n].owner == "voievodat"),
                         "Test", ["calareti"])
    game.move_army(army.id, last.id)
    assert game.winner == Victory("voievodat", "conquest") and game.over
    with pytest.raises(MoveError):
        game.move_army(army_at(game, "voievodat", "targoviste").id, "arges")


def test_legendary_victory_after_holding_the_heart(game):
    no_ai(game)
    game.provinces["heart"].owner = "voievodat"
    game.provinces["heart"].garrison = []
    for turn in range(1, 8):
        game.end_turn()
        assert game.heart_turns["voievodat"] == turn and not game.winner
    game.end_turn()
    assert game.winner == Victory("voievodat", "legend")


def test_losing_the_capital_resets_the_heart_count(game):
    no_ai(game)
    game.provinces["heart"].owner = "voievodat"
    game.end_turn()
    assert game.heart_turns["voievodat"] == 1
    game.provinces["targoviste"].owner = "strigoi"
    game.end_turn()
    assert game.heart_turns["voievodat"] == 0


def test_armies_heal_at_home(game):
    no_ai(game)
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.regiments[0].hp = 50
    game.end_turn()
    assert vlad.regiments[0].hp == 60


def test_player_eliminated_means_game_over(game):
    for p in game.provinces_of("voievodat"):
        p.owner = "strigoi"
    game.end_turn()
    assert game.over and "voievodat" in game.eliminated
