"""Saving and loading campaigns."""

import json

import pytest

from legendele.game import Game, diplomacy
from legendele.game.save import SaveError, from_dict, load_game, read_save, save_game, summary, to_dict


def play(game, turns):
    for _ in range(turns):
        game.end_turn()
        while game.proposals:
            diplomacy.answer(game, game.proposals[0], accept=False)
        if game.over:
            break


def test_round_trip_keeps_everything(real_data, tmp_path):
    game = Game.new(real_data, "zmei", seed=5)
    play(game, 12)
    path = tmp_path / "slot1.json"
    save_game(game, path)
    loaded = load_game(real_data, path)
    assert to_dict(loaded) == to_dict(game)


def test_a_loaded_war_goes_on_exactly_as_it_would_have(real_data, tmp_path):
    game = Game.new(real_data, "iele", seed=9)
    play(game, 8)
    save_game(game, tmp_path / "s.json")
    twin = load_game(real_data, tmp_path / "s.json")
    play(game, 10)
    play(twin, 10)
    assert to_dict(twin) == to_dict(game)


def test_save_is_plain_json_with_a_summary(real_data, tmp_path):
    game = Game.new(real_data, "voievodat", seed=1)
    save_game(game, tmp_path / "s.json", extra={"saved_at": "now"})
    d = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert d["saved_at"] == "now"
    assert summary(d) == {"player": "voievodat", "round": 0, "provinces": 3, "over": False, "era": 1400}
    assert not (tmp_path / "s.tmp").exists()


def test_bad_saves_are_refused(real_data, tmp_path):
    game = Game.new(real_data, "voievodat", seed=1)
    d = to_dict(game)
    with pytest.raises(SaveError, match="version"):
        from_dict(real_data, {**d, "version": 999})
    with pytest.raises(SaveError, match="map"):
        from_dict(real_data, {**d, "map": "Atlantis"})
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SaveError):
        read_save(tmp_path / "broken.json")


def test_pending_proposals_and_diplomacy_survive(real_data, tmp_path):
    game = Game.new(real_data, "voievodat", seed=2)
    game.declare_war("zmei", "voievodat")
    game.propose("peace", "zmei", "voievodat", gold=0)
    save_game(game, tmp_path / "s.json")
    loaded = load_game(real_data, tmp_path / "s.json")
    assert loaded.at_war("zmei", "voievodat")
    assert len(loaded.proposals) == 1 and loaded.proposals[0].faction == "zmei"
    assert diplomacy.answer(loaded, loaded.proposals[0], accept=True)
