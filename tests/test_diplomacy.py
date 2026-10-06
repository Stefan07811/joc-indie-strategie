"""War, peace, alliances, treachery and the AI's personalities (with the shipped, peaceful start)."""

import pytest

from legendele.game import DiplomacyChange, Game, MoveError, Proposal, diplomacy
from legendele.game.ai import SimpleAI


class Yes(SimpleAI):
    def consider(self, game, proposal):
        return True


class No(SimpleAI):
    def consider(self, game, proposal):
        return False


@pytest.fixture
def game(real_data):
    g = Game.new(real_data, "voievodat", seed=1)

    class Idle(SimpleAI):
        def take_turn(self, game):
            pass
    for fid in g.ai:
        g.ai[fid] = Idle(fid)
    return g


def army_at(game, fid, pid):
    return next(a for a in game.armies_of(fid) if a.province == pid)


def test_everyone_starts_at_peace(game):
    for a in game.turn_order:
        for b in game.turn_order:
            if a != b:
                assert diplomacy.relation(game, a, b) == "peace"
    assert game.at_war("voievodat", None) and game.at_war("voievodat", "haiduci")


def test_peace_closes_borders(game):
    vlad = army_at(game, "voievodat", "targoviste")
    reach = game.reachable(vlad)
    assert "retezat" not in reach  # Dragonkin land, a Dragonkin army, but we are at peace
    assert "buzau" in reach  # neutral land is always open
    game.declare_war("voievodat", "zmei")
    assert "retezat" in game.reachable(vlad)


def test_peace_protects_armies_on_neutral_land(game):
    vlad = army_at(game, "voievodat", "targoviste")
    game.add_army("strigoi", "buzau", "Visitor", ["morti"])
    assert "buzau" not in game.reachable(vlad)


def test_declaring_war_and_the_truce(game):
    events = game.declare_war("voievodat", "zmei")
    assert any(isinstance(e, DiplomacyChange) and e.kind == "war" and not e.treachery for e in events)
    game.ai["zmei"] = Yes("zmei")
    assert game.propose("peace", "voievodat", "zmei") is True
    assert diplomacy.relation(game, "voievodat", "zmei") == "peace"
    assert diplomacy.in_truce(game, "voievodat", "zmei")
    events = game.declare_war("voievodat", "zmei")  # breaking the truce
    assert events[0].treachery
    assert game.treachery["voievodat"] == 1 and ("zmei", "voievodat") in game.grudges
    mood = dict(diplomacy.attitude(game, "iele", "voievodat")[1])
    assert mood["Breaks treaties"] < 0


def test_peace_can_be_bought(game):
    game.declare_war("voievodat", "zmei")
    game.ai["zmei"] = Yes("zmei")
    game.propose("peace", "voievodat", "zmei", gold=100)
    assert game.treasury["voievodat"].gold == 100 and game.treasury["zmei"].gold == 300


def test_refused_offers_and_the_cooldown(game):
    game.declare_war("voievodat", "zmei")
    game.ai["zmei"] = No("zmei")
    assert game.propose("peace", "voievodat", "zmei") is False
    assert diplomacy.relation(game, "voievodat", "zmei") == "war"
    with pytest.raises(MoveError, match="too recently"):
        game.propose("peace", "voievodat", "zmei")


def test_alliance_rules(game):
    with pytest.raises(MoveError, match="never ally"):
        game.propose("alliance", "voievodat", "strigoi")
    game.declare_war("voievodat", "zmei")
    with pytest.raises(MoveError, match="at peace first"):
        game.propose("alliance", "voievodat", "zmei")
    game.ai["iele"] = Yes("iele")
    assert game.propose("alliance", "voievodat", "iele") is True
    assert diplomacy.relation(game, "voievodat", "iele") == "alliance"


def test_allies_share_the_road_and_the_war(game):
    game.ai["iele"] = Yes("iele")
    game.propose("alliance", "voievodat", "iele")
    radu = army_at(game, "voievodat", "craiova")
    radu.province = "cluj"
    game.provinces["cluj"].owner = "iele"
    assert game.passable("voievodat", "cluj")  # allied land: march on through
    assert "maramures" in game.reachable(radu) and not game.defended("voievodat", "maramures")
    game.declare_war("zmei", "iele")
    assert diplomacy.relation(game, "voievodat", "zmei") == "war"  # we stand by our ally


def test_peace_sends_armies_home(game):
    game.declare_war("voievodat", "strigoi")
    radu = army_at(game, "voievodat", "craiova")
    radu.province = "barlad"  # deep in Revenant land
    game.ai["strigoi"] = Yes("strigoi")
    game.propose("peace", "voievodat", "strigoi")
    assert radu.id not in game.armies or game.provinces[radu.province].owner != "strigoi"


def test_a_human_answers_ai_proposals_later(game):
    game.declare_war("zmei", "voievodat")
    result = game.propose("peace", "zmei", "voievodat")
    assert result is None and len(game.proposals) == 1
    offer = game.proposals[0]
    assert isinstance(offer, Proposal) and offer in game.events
    assert diplomacy.answer(game, offer, accept=True)
    assert diplomacy.relation(game, "voievodat", "zmei") == "peace" and not game.proposals


def test_hora_and_abduction_only_against_enemies(game):
    vlad = army_at(game, "voievodat", "targoviste")
    army = game.add_army("zmei", "arges", "Kidnapper", ["pui_de_zmeu"])
    assert game.capital_of("voievodat") in game.provinces["arges"].neighbors
    from legendele.game import legends
    assert legends.abduction_target(game, army)[0] is None  # at peace: no abductions
    game.declare_war("zmei", "voievodat")
    assert legends.abduction_target(game, army)[0] == "targoviste"
    assert vlad  # quiet linter


# --- personalities -------------------------------------------------------------------------

def test_personalities_come_from_the_data(game):
    assert SimpleAI("zmei").personality(game)["personality"] == "Greedy"
    assert SimpleAI("iele").personality(game)["personality"] == "Guarded"


def test_greedy_dragonkin_take_gold_for_peace(game):
    game.declare_war("voievodat", "zmei")
    ai = SimpleAI("zmei")
    cheap = Proposal("peace", "voievodat", "zmei", gold=0)
    rich = Proposal("peace", "voievodat", "zmei", gold=500)
    assert not ai.consider(game, cheap) and ai.consider(game, rich)


def test_ancient_enemies_never_ally(game):
    game.relations[diplomacy.key("voievodat", "strigoi")] = "peace"
    assert not SimpleAI("strigoi").consider(game, Proposal("alliance", "voievodat", "strigoi"))


def test_everyone_turns_on_a_runaway_leader(game):
    for pid in ("buzau", "bacau", "brasov", "sibiu", "cluj", "mures"):
        game.provinces[pid].owner = "zmei"
    ai = SimpleAI("iele")
    assert "zmei" in ai._alarming(game)
    game.declare_war("iele", "zmei")
    assert not ai._wants_peace(game, "zmei")
    assert not ai.consider(game, Proposal("peace", "zmei", "iele", gold=1000))


def test_ai_turns_are_diplomatic(real_data):
    kinds = set()
    from legendele.game.ai import SimpleAI
    for seed in range(8):
        g = Game.new(real_data, "voievodat", seed=seed)
        g.ai["voievodat"] = SimpleAI("voievodat")  # every legend is the computer's: a long war
        g.spectate = True
        for _ in range(30):
            g.ai_turn("voievodat")
            g.end_turn()
            if g.over:
                break
        kinds |= {e.kind for e in g.events if isinstance(e, DiplomacyChange)}
    assert "war" in kinds and "peace" in kinds


def test_no_two_warring_factions_share_a_province(real_data):
    g = Game.new(real_data, "iele", seed=3)
    for _ in range(30):
        g.end_turn()
        while g.proposals:
            diplomacy.answer(g, g.proposals[0], accept=True)
        for pid in g.provinces:
            factions = {a.faction for a in g.armies_in(pid)}
            for a in factions:
                for b in factions - {a}:
                    assert not g.at_war(a, b), (pid, a, b)
        if g.over:
            break
