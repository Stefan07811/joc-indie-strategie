"""Tales from folklore: events with a choice."""

import pytest

from legendele.game import Game, MoveError, Tale, events, legends
from legendele.game.save import from_dict, to_dict


def test_every_event_can_be_chosen_every_way(data):
    for eid, e in data.events.items():
        for i in range(len(e["choices"])):
            game = Game.new(data, "voievodat", seed=i)
            fid = (e.get("factions") or [f for f in game.turn_order if f not in e.get("not_factions", ())])[0]
            pid = game.provinces_of(fid)[0].id if e.get("target") == "province" else None
            tale = Tale(eid, fid, pid)
            assert events.choose(game, tale, i)
            assert events.summary(game, e["choices"][i].get("effects", {}))


def test_the_player_decides_and_the_choice_takes_effect(data, monkeypatch):
    game = Game.new(data, "voievodat", seed=1)
    monkeypatch.setattr(events, "EVENT_CHANCE", 1.0)
    for ai in game.ai.values():
        ai.take_turn = lambda game: None
    game.end_turn()
    assert game.pending_events and all(t.faction == "voievodat" for t in game.pending_events)
    tale = game.pending_events[0]
    gold = game.treasury["voievodat"].gold
    game.choose_event(tale, 0)
    assert tale not in game.pending_events
    with pytest.raises(MoveError):
        game.choose_event(tale, 0)  # decided once
    assert game.data.events[tale.event]["title"] in game.log[-1] or game.treasury["voievodat"].gold != gold


def test_events_weigh_on_public_order_for_a_while(data):
    game = Game.new(data, "voievodat", seed=1)
    p = game.provinces["arges"]
    before, _ = legends.public_order(game, p)
    events.choose(game, Tale("strigoi_village", "voievodat", "arges"), 2)  # "only peasant talk": -2 order
    after, parts = legends.public_order(game, p)
    assert after == before - 2 and ("A Strigoi in the Village", -2) in parts
    for ai in game.ai.values():
        ai.take_turn = lambda game: None
    for _ in range(5):
        game.end_turn()
    assert ("A Strigoi in the Village", -2) not in legends.public_order(game, p)[1]


def test_a_free_regiment_arrives_and_pending_tales_are_saved(data):
    game = Game.new(data, "iele", seed=1)
    tale = Tale("fae_midsummer", "iele", "suceava")
    game.pending_events.append(tale)
    loaded = from_dict(game.data, to_dict(game))
    assert loaded.pending_events == [tale]
    loaded.choose_event(loaded.pending_events[0], 0)
    assert "sanziene" in loaded.provinces["suceava"].recruits
