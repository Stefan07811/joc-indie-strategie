"""Start options and the two newest legends (the Outlaws and the Solomonari)."""

import pytest

from legendele.game import Battle, Captured, Game, Regiment, legends
from legendele.game.battle import Side, resolve
from legendele.game.save import from_dict, to_dict


def test_default_start_has_every_legend_in_its_own_homeland(data):
    game = Game.new(data, "outlaws", seed=3)
    assert game.capital_of("outlaws") == "vlasia" and game.provinces["vlasia"].owner == "outlaws"
    assert game.capital_of("solomonari") == "apuseni" and game.provinces["apuseni"].owner == "solomonari"
    assert len(game.factions) == 6 and game.year == 1400
    assert game.victory_rules["conquest_provinces"] == 21


def test_fewer_rivals_leave_their_lands_to_the_rebels(data):
    game = Game.new(data, "zmei", seed=5, options={"rivals": 2})
    assert len(game.factions) == 3 and "zmei" in game.factions
    out = [f for f in ("voievodat", "iele", "strigoi", "outlaws", "solomonari") if f not in game.factions]
    capital = data.factions[out[0]]["capital"]
    assert game.provinces[capital].owner is None and game.provinces[capital].garrison
    assert not [a for a in game.armies.values() if a.faction in out]
    assert set(game.turn_order) == set(game.factions)


def test_shuffled_homelands(data):
    for seed in range(20):
        game = Game.new(data, "voievodat", seed=seed, options={"shuffle": True})
        if game.capital_of("voievodat") != "targoviste":
            break
    capital = game.capital_of("voievodat")
    p = game.provinces[capital]
    assert p.owner == "voievodat"
    assert all(data.units[r.unit]["faction"] == "voievodat" for r in p.garrison)
    assert any(a.faction == "voievodat" and a.province == capital for a in game.armies.values())
    for fid in game.factions:  # every legend rules its new capital
        assert game.provinces[game.capital_of(fid)].owner == fid


def test_age_of_kings_and_a_short_war(data):
    plain = Game.new(data, "iele", seed=1)
    kings = Game.new(data, "iele", seed=1, options={"era": 1450, "victory": "short"})
    assert kings.year == 1450 and kings.date == "Spring 1450"
    assert kings.treasury["iele"].gold == plain.treasury["iele"].gold + 200
    assert "drill" in kings.techs["iele"] and "barracks" in kings.provinces["maramures"].buildings
    assert sum(len(a.regiments) for a in kings.armies_of("iele")) > sum(len(a.regiments) for a in plain.armies_of("iele"))
    assert kings.victory_rules["conquest_provinces"] == 15


def test_options_survive_a_save(data):
    game = Game.new(data, "solomonari", seed=2, options={"rivals": 3, "shuffle": True, "era": 1450})
    loaded = from_dict(data, to_dict(game))
    assert loaded.factions == game.factions and loaded.capitals == game.capitals
    assert loaded.year == 1450 and set(loaded.turn_order) == set(game.turn_order)


def test_old_saves_keep_their_four_legends(data):
    game = Game.new(data, "voievodat", seed=2)
    d = to_dict(game)
    del d["options"]
    for fid in ("outlaws", "solomonari"):
        del d["treasury"][fid]
    loaded = from_dict(data, d)
    assert set(loaded.turn_order) == {"voievodat", "zmei", "iele", "strigoi"}


def test_bad_options(data):
    with pytest.raises(ValueError):
        Game.new(data, "voievodat", options={"era": 1066})


def test_outlaws_rob_the_rich(data):
    game = Game.new(data, "outlaws", seed=1)
    gold = game.treasury["outlaws"].gold
    game._capture(game.provinces["buzau"], "outlaws")
    assert game.treasury["outlaws"].gold == gold + 60
    order = dict(legends.public_order(game, game.provinces["vlasia"])[1])
    assert order["Loved by the poor"] == 1


def test_solomonari_weather_blunts_arrows(data):
    units = data.units

    def volley(storm):
        archers = Side("voievodat", [Regiment("arcasi", 80) for _ in range(4)])
        target = Side("solomonari", [Regiment("paznici", 100) for _ in range(4)], storm=storm)
        resolve(archers, target, units, rng=_Fixed(), kind="field")
        return sum(r.hp for r in target.regiments)

    assert volley(0.8) > volley(1.0)


class _Fixed:
    def random(self):
        return 0.5

    def choice(self, seq):
        return seq[0]


def test_new_legends_fight_in_the_campaign(data):
    game = Game.new(data, "voievodat", seed=4)
    for _ in range(16):
        game.end_turn()
        if game.over:
            break
    fought = {e.result.winning_faction for e in game.events if isinstance(e, Battle)} | \
        {e.faction for e in game.events if isinstance(e, Captured)}
    assert fought & {"outlaws", "solomonari"}
