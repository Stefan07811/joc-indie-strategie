"""The realm as a state: traditions, trade, royal marriages and vassals."""

import pytest

from legendele.game import Game, diplomacy, economy, legends, techs
from legendele.game.save import from_dict, to_dict


@pytest.fixture
def quiet(real_data):
    game = Game.new(real_data, "voievodat", seed=2)
    for ai in game.ai.values():
        ai.take_turn = lambda game: None
    return game


def test_a_tradition_is_studied_and_pays_off(quiet):
    game = quiet
    game.treasury["voievodat"].gold = 1000
    before = economy.balance(game, "voievodat").tax
    assert techs.blocker(game, "voievodat", "royal_roads") == "Needs Market Rights, Chancery"
    assert techs.blocker(game, "voievodat", "hoard_vaults") == "Not one of your traditions"
    techs.start(game, "voievodat", "markets")
    assert techs.blocker(game, "voievodat", "chancery") == "Already studying"
    assert techs.blocker(game, "voievodat", "iron_mines") == "Needs Drill and Discipline"
    for _ in range(2):
        game.end_turn()
    assert "markets" in techs.known(game, "voievodat")
    assert economy.balance(game, "voievodat").tax > before


def test_traditions_reach_order_movement_and_battle(quiet):
    game = quiet
    game.techs["voievodat"] = ["chancery", "markets", "royal_roads", "drill", "iron_mines"]
    p = game.provinces["targoviste"]
    assert ("Traditions", 1) in legends.public_order(game, p)[1]
    vlad = next(a for a in game.armies_of("voievodat") if a.province == "targoviste")
    vlad.traits = []
    from legendele.game import generals
    assert generals.moves(game, vlad) == 5
    side = game._attackers([vlad], "arges")
    game.techs["voievodat"] = []
    assert side.attack_mult > game._attackers([vlad], "arges").attack_mult


def test_the_ai_studies_too(real_data):
    game = Game.new(real_data, "voievodat", seed=1)
    for _ in range(16):
        game.end_turn()
        while game.proposals:
            diplomacy.answer(game, game.proposals[0], accept=False)
        if game.over:
            break
    assert any(game.techs.get(f) or game.studying.get(f) for f in game.ai)


def test_trade_and_marriage(quiet):
    game = quiet
    gold = economy.balance(game, "voievodat").gold
    diplomacy.settle(game, diplomacy.Proposal("trade", "voievodat", "iele"), True)
    assert economy.balance(game, "voievodat").trade > 0 and economy.balance(game, "voievodat").gold > gold
    blocker = diplomacy.proposal_blocker(game, diplomacy.Proposal("marriage", "voievodat", "strigoi"))
    assert blocker == "The dead do not wed"
    diplomacy.settle(game, diplomacy.Proposal("marriage", "voievodat", "iele"), True)
    assert ("Royal marriage", 25) in diplomacy.attitude(game, "iele", "voievodat")[1]
    game.declare_war("voievodat", "iele")  # war on the in-laws is treachery, and ends the trade
    assert game.treachery.get("voievodat") and not diplomacy.trade_partners(game, "voievodat")


def test_a_beaten_legend_becomes_a_vassal(quiet):
    game = quiet
    game.declare_war("voievodat", "zmei")
    offer = diplomacy.Proposal("vassal", "voievodat", "zmei")
    assert diplomacy.proposal_blocker(game, offer) == "They are not beaten yet"
    for a in list(game.armies_of("zmei")):
        del game.armies[a.id]
    for p in game.provinces_of("zmei")[1:]:
        p.owner = "voievodat"
    assert diplomacy.proposal_blocker(game, offer) is None
    assert game.propose("vassal", "voievodat", "zmei") is True
    assert game.vassals["zmei"] == "voievodat" and diplomacy.relation(game, "voievodat", "zmei") == "alliance"
    assert game.realm_size("voievodat") == len(game.provinces_of("voievodat")) + 1
    assert economy.balance(game, "voievodat").vassals > 0 > economy.balance(game, "zmei").vassals
    game.break_alliance("zmei", "voievodat")
    assert "zmei" not in game.vassals


def test_the_state_is_saved(quiet):
    game = quiet
    game.techs["voievodat"] = ["markets"]
    game.studying["voievodat"] = {"tech": "chancery", "turns_left": 2}
    diplomacy.settle(game, diplomacy.Proposal("trade", "voievodat", "iele"), True)
    diplomacy.settle(game, diplomacy.Proposal("marriage", "voievodat", "zmei"), True)
    game.vassals["strigoi"] = "voievodat"
    loaded = from_dict(game.data, to_dict(game))
    assert loaded.techs == game.techs and loaded.studying == game.studying
    assert loaded.trade == game.trade and loaded.marriages == game.marriages and loaded.vassals == game.vassals
