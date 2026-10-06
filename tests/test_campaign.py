import pytest

from legendele.game import Game, MoveError


def army_at(game, fid, pid):
    return next(a for a in game.armies_of(fid) if a.province == pid)


def test_new_game_setup(game):
    assert game.date == "Spring 1400"
    assert game.turn_order[0] == "voievodat"
    assert set(game.turn_order) == {"voievodat", "zmei", "iele", "strigoi"}
    assert len(game.armies) == 8
    assert set(game.ai) == {"zmei", "iele", "strigoi"}


def test_cannot_play_rebels(data):
    with pytest.raises(ValueError):
        Game.new(data, "haiduci")


def test_terrain_costs_and_mastery(game):
    assert game.enter_cost("voievodat", "craiova") == 1      # plains
    assert game.enter_cost("voievodat", "arges") == 2        # hills
    assert game.enter_cost("voievodat", "heart") == 3        # mountains
    assert game.enter_cost("zmei", "heart") == 1             # Zmei master the mountains
    assert game.enter_cost("iele", "suceava") == 1           # Iele master the forest
    assert game.enter_cost("strigoi", "siret") == 1          # Strigoi master the marsh


def test_reachable_respects_move_points(game):
    vlad = army_at(game, "voievodat", "targoviste")
    reach = game.reachable(vlad)
    assert reach["arges"].cost == 2
    assert reach["brasov"].cost == 4 and reach["brasov"].path == ["arges", "brasov"]
    assert "heart" not in reach  # 2 (Argeș) + 3 (mountains) > 4
    assert "targoviste" not in reach


def test_marching_stops_at_the_first_province_we_do_not_own(game):
    vlad = army_at(game, "voievodat", "targoviste")
    reach = game.reachable(vlad)
    assert "black_marsh" in reach      # an enemy army: we may attack it...
    assert "barlad" not in reach       # ...but not march past it
    assert "buzau" in reach and "bacau" not in reach  # neutral Buzău ends the march too


def test_move_spends_points_and_can_continue(game):
    vlad = army_at(game, "voievodat", "targoviste")
    game.move_army(vlad.id, "arges")
    assert (vlad.province, vlad.moves_left) == ("arges", 2)
    game.move_army(vlad.id, "brasov")  # neutral, with a garrison: the march ends in a siege
    assert (vlad.province, vlad.moves_left) == ("brasov", 0)
    with pytest.raises(MoveError):
        game.move_army(vlad.id, "bacau")


def test_illegal_move_changes_nothing(game):
    vlad = army_at(game, "voievodat", "targoviste")
    with pytest.raises(MoveError):
        game.move_army(vlad.id, "maramures")
    assert (vlad.province, vlad.moves_left) == ("targoviste", 4)


def test_end_turn_advances_season_and_restores_moves(game):
    vlad = army_at(game, "voievodat", "targoviste")
    game.move_army(vlad.id, "arges")
    game.end_turn()
    assert game.date == "Summer 1400"
    assert all(a.moves_left == 4 for a in game.armies.values())
    for _ in range(3):
        game.end_turn()
    assert game.date == "Spring 1401"


def test_ai_wages_war_and_never_shares_a_province_with_enemies(data):
    game = Game.new(data, "voievodat", seed=1)
    for _ in range(12):
        game.end_turn()
        for p in game.provinces:
            assert len({a.faction for a in game.armies_in(p)}) <= 1, p
        if game.over:
            break
    assert any(p.owner != data_owner for p, data_owner in
               zip(game.provinces.values(), (d["owner"] for d in data.provinces))), "AI should take land"


def test_same_seed_same_war(data):
    a, b = Game.new(data, "zmei", seed=7), Game.new(data, "zmei", seed=7)
    for _ in range(10):
        a.end_turn()
        b.end_turn()
    assert [(x.id, x.province, [r.hp for r in x.regiments]) for x in a.armies.values()] == \
        [(x.id, x.province, [r.hp for r in x.regiments]) for x in b.armies.values()]
    assert a.log == b.log
