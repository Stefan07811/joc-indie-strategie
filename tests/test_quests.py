"""Quests of legend and their heroes."""

from legendele.game import Game, QuestDone, quests
from legendele.game.save import from_dict, to_dict


def quiet(data, fid):
    game = Game.new(data, fid, seed=1)
    for ai in game.ai.values():
        ai.take_turn = lambda game: None
    return game


def test_a_hoard_brings_the_griffin_hag(real_data):
    game = quiet(real_data, "zmei")
    assert quests.progress(game, "zmei", "hoard_of_hoards")[1] == 900
    game.treasury["zmei"].gold = 2000
    game.end_turn()
    assert quests.done(game, "zmei", "hoard_of_hoards")
    assert any(isinstance(e, QuestDone) and e.hero == "zgripturoaica" for e in game.events)
    game.end_turn()
    assert any(r.unit == "zgripturoaica" for a in game.armies_of("zmei") for r in a.regiments)
    game.end_turn()
    assert sum(isinstance(e, QuestDone) and e.quest == "hoard_of_hoards" for e in game.events) == 1  # once only


def test_progress_counts_deeds(real_data):
    game = quiet(real_data, "voievodat")
    game.stats["voievodat"] = {"won": 3, "from_zmei": 1}
    assert quests.progress(game, "voievodat", "golden_apples") == (3, 5)
    assert quests.progress(game, "voievodat", "stolen_lights") == (1, 2)
    iele = quiet(real_data, "iele")
    assert quests.progress(iele, "iele", "sacred_woods") == (3, 4)  # Maramureș, Suceava, Bistrița


def test_captures_are_counted_by_victim(real_data):
    game = quiet(real_data, "voievodat")
    p = game.provinces["iron_gates"]
    p.garrison = []
    game._capture(p, "voievodat")
    assert game.stats["voievodat"]["from_zmei"] == 1


def test_quests_are_saved(real_data):
    game = quiet(real_data, "iele")
    game.quests_done["iele"] = ["the_fairest"]
    assert from_dict(game.data, to_dict(game)).quests_done == {"iele": ["the_fairest"]}
