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


def test_foreign_armies_block_movement(game):
    vlad = army_at(game, "voievodat", "targoviste")
    assert "black_marsh" not in game.reachable(vlad)  # the Strigoi army stands there
    game.armies_in("black_marsh")[0].province = "barlad"
    assert "black_marsh" in game.reachable(vlad)


def test_move_spends_points_and_can_continue(game):
    vlad = army_at(game, "voievodat", "targoviste")
    game.move_army(vlad.id, "arges")
    assert (vlad.province, vlad.moves_left) == ("arges", 2)
    game.move_army(vlad.id, "brasov")
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


def test_ai_armies_march_and_never_share_a_province_with_enemies(game):
    start = {a.id: a.province for a in game.armies.values() if a.faction != "voievodat"}
    for _ in range(12):
        game.end_turn()
        for p in game.provinces:
            assert len({a.faction for a in game.armies_in(p)}) <= 1, p
    moved = [aid for aid, pid in start.items() if game.armies[aid].province != pid]
    assert moved, "AI armies should leave their starting provinces"
    assert any("marches to" in line for line in game.log)


def test_ai_turns_are_deterministic(data):
    a, b = Game.new(data, "zmei"), Game.new(data, "zmei")
    for _ in range(8):
        a.end_turn()
        b.end_turn()
    assert [(x.id, x.province) for x in a.armies.values()] == [(x.id, x.province) for x in b.armies.values()]
