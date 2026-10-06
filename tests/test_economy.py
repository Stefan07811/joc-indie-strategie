"""Gold, food, buildings, recruitment and the seasons."""

import pytest

from legendele.game import Game, MoveError, Regiment, economy


@pytest.fixture
def game(data):
    g = Game.new(data, "voievodat", seed=1)

    class Idle:
        def take_turn(self, game):
            pass
    for fid in g.ai:
        g.ai[fid] = Idle()
    return g


def army_at(game, fid, pid):
    return next(a for a in game.armies_of(fid) if a.province == pid)


def test_starting_treasury_and_balance(game):
    t = game.treasury["voievodat"]
    assert (t.gold, t.food) == (200, 40)
    bal = economy.balance(game, "voievodat")
    # Craiova (plains 18), Argeș (hills 15), Târgoviște (plains 18 + capital 25), Principality +35%
    assert bal.tax == round((18 + 15 + 18 + 25) * 1.35)
    assert bal.upkeep == sum(game.data.units[r.unit]["upkeep"] for a in game.armies_of("voievodat") for r in a.regiments)
    assert bal.food_made == 4 + 2 + 4
    assert bal.food_eaten == sum(economy.appetite(game, r.unit) for a in game.armies_of("voievodat")
                                 for r in a.regiments)


def test_end_of_turn_collects_taxes_and_food(game):
    expected = economy.balance(game, "voievodat", season="Summer")
    game.end_turn()
    t = game.treasury["voievodat"]
    assert t.gold == 200 + expected.gold
    assert t.food == 40 + expected.food


def test_summer_harvest_and_lean_winter(game):
    summer = economy.balance(game, "voievodat", season="Summer").food_made
    winter = economy.balance(game, "voievodat", season="Winter").food_made
    assert summer > economy.balance(game, "voievodat", season="Spring").food_made > winter


def test_dragons_eat_more_than_spearmen(game):
    assert economy.appetite(game, "zmei_buzdugan") > economy.appetite(game, "oteni") == 1


def test_build_pays_and_finishes_next_season(game):
    game.build("voievodat", "craiova", "market")
    assert game.treasury["voievodat"].gold == 50
    assert game.provinces["craiova"].construction == {"building": "market", "turns_left": 1}
    before = economy.province_yield(game, game.provinces["craiova"])[0]
    game.end_turn()
    assert game.provinces["craiova"].buildings == ["market"]
    assert economy.province_yield(game, game.provinces["craiova"])[0] == before + 12


def test_building_rules(game):
    g = game
    g.treasury["voievodat"].gold = 5000
    assert economy.building_blocker(g, "voievodat", "craiova", "mine") == "Not on plains"
    assert economy.building_blocker(g, "voievodat", "heart", "farm") == "Not your province"
    assert economy.building_blocker(g, "voievodat", "targoviste", "walls") == "Already walled"
    g.build("voievodat", "arges", "mine")
    assert economy.building_blocker(g, "voievodat", "arges", "farm") == "Already building"
    g.provinces["arges"].construction = None
    g.provinces["arges"].buildings = ["mine", "farm", "market"]
    assert economy.building_blocker(g, "voievodat", "arges", "barracks") == "No free slot"
    g.treasury["voievodat"].gold = 10
    with pytest.raises(MoveError, match="Not enough gold"):
        g.build("voievodat", "craiova", "farm")


def test_stone_walls_bring_a_garrison(game):
    game.treasury["voievodat"].gold = 1000
    game.build("voievodat", "arges", "walls")
    game.end_turn()
    assert not game.provinces["arges"].walls
    game.end_turn()
    p = game.provinces["arges"]
    assert p.walls and p.buildings == ["walls"]
    game.end_turn()
    assert len(p.garrison) == game.rules["garrison_size"]


def test_recruits_arrive_next_season_and_join_the_army(game):
    vlad = army_at(game, "voievodat", "targoviste")
    size = len(vlad.regiments)
    game.recruit("voievodat", "targoviste", "oteni")
    assert game.treasury["voievodat"].gold == 140 and len(vlad.regiments) == size
    game.end_turn()
    assert len(vlad.regiments) == size + 1


def test_recruits_with_no_army_to_join_raise_a_new_one(game):
    game.recruit("voievodat", "arges", "arcasi")
    game.end_turn()
    new = game.armies_in("arges")
    assert len(new) == 1 and new[0].general == game.data.factions["voievodat"]["general_names"][0]
    assert [r.unit for r in new[0].regiments] == ["arcasi"]


def test_recruitment_rules(game):
    g = game
    g.treasury["voievodat"].gold = 5000
    assert economy.unit_blocker(g, "voievodat", "targoviste", "calareti") == "Needs Barracks"
    assert economy.unit_blocker(g, "voievodat", "targoviste", "pui_de_zmeu") == "Not one of yours"
    g.provinces["arges"].buildings = ["barracks"]
    assert economy.unit_blocker(g, "voievodat", "arges", "calareti") is None
    assert economy.unit_blocker(g, "voievodat", "arges", "tunari") == "Capital only"
    g.provinces["targoviste"].buildings = ["barracks"]
    assert economy.unit_blocker(g, "voievodat", "targoviste", "tunari") is None
    g.recruit("voievodat", "arges", "oteni")
    g.recruit("voievodat", "arges", "oteni")
    assert economy.unit_blocker(g, "voievodat", "arges", "oteni") == "Training grounds full"


def test_one_hero_at_a_time(data):
    g = Game.new(data, "zmei", seed=1)
    g.treasury["zmei"].gold = 5000
    g.provinces["retezat"].buildings = ["barracks"]
    g.recruit("zmei", "retezat", "zmeul_mare")
    assert economy.unit_blocker(g, "zmei", "retezat", "zmeul_mare") == "Already serves you"


def test_cancel_recruit_refunds(game):
    game.recruit("voievodat", "craiova", "oteni")
    game.cancel_recruit("craiova", 0)
    assert game.treasury["voievodat"].gold == 200 and not game.provinces["craiova"].recruits


def test_capture_loses_work_in_progress_but_keeps_buildings(game):
    p = game.provinces["iron_gates"]
    p.buildings = ["mine"]
    p.construction = {"building": "farm", "turns_left": 1}
    p.recruits = ["spiridusi"]
    p.garrison = []
    radu = army_at(game, "voievodat", "craiova")
    game.move_army(radu.id, "iron_gates")
    assert p.owner == "voievodat" and p.buildings == ["mine"] and p.construction is None and not p.recruits


def test_empty_granary_starves_the_armies(game):
    game.treasury["voievodat"].food = -100
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.province = "heart"  # away from home, so no healing hides the loss
    full = sum(r.hp for r in vlad.regiments)
    game.end_turn()
    assert sum(r.hp for r in vlad.regiments) < full
    assert game.treasury["voievodat"].food == 0


def test_unpaid_regiments_desert(game):
    game.treasury["voievodat"].gold = -500
    before = sum(len(a.regiments) for a in game.armies_of("voievodat"))
    game.end_turn()
    assert sum(len(a.regiments) for a in game.armies_of("voievodat")) == before - 1
    assert any("desert" in line for line in game.log)


def test_winter_bites_armies_abroad_but_not_the_dead(game):
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.province = "heart"
    dead = army_at(game, "strigoi", "barlad")
    dead.province = "bacau"
    game.round = 2  # the next season is winter
    full_vlad = [r.hp for r in vlad.regiments]
    full_dead = [r.hp for r in dead.regiments]
    game.end_turn()
    assert game.season == "Winter"
    assert all(r.hp < f for r, f in zip(vlad.regiments, full_vlad))
    assert [r.hp for r in dead.regiments] == full_dead  # the Revenants do not feel the cold


def test_every_province_raises_a_militia(game):
    p = game.provinces["arges"]
    assert [r.unit for r in p.garrison] == ["oteni"]  # from the very start
    p.garrison = []
    game.end_turn()
    assert len(p.garrison) == 1


def test_merge_armies(game):
    vlad = army_at(game, "voievodat", "targoviste")
    radu = army_at(game, "voievodat", "craiova")
    radu.province = "targoviste"
    total = len(vlad.regiments) + len(radu.regiments)
    game.merge(vlad.id)
    assert len(vlad.regiments) == total and radu.id not in game.armies


def test_merge_respects_the_army_size_limit(game):
    vlad = army_at(game, "voievodat", "targoviste")
    vlad.regiments = [Regiment("oteni", 100) for _ in range(11)]
    other = game.add_army("voievodat", "targoviste", "Test", ["arcasi", "arcasi"])
    game.merge(vlad.id)
    assert len(vlad.regiments) == 12 and len(other.regiments) == 1


def test_ai_builds_and_recruits(data):
    g = Game.new(data, "voievodat", seed=2)
    for _ in range(6):
        g.end_turn()
        if g.over:
            break
    ai_land = [p for p in g.provinces.values() if p.owner in ("zmei", "iele", "strigoi")]
    assert any(p.buildings or p.construction for p in ai_land)
    assert g._generals_named or any(len(a.regiments) > 4 for a in g.armies.values())


def test_difficulty_sets_the_purses_and_the_rivals_taxes(data):
    from legendele.game import Game, economy
    easy = Game.new(data, "voievodat", seed=1, difficulty="easy")
    hard = Game.new(data, "voievodat", seed=1, difficulty="hard")
    assert easy.treasury["voievodat"].gold > hard.treasury["voievodat"].gold
    assert easy.treasury["zmei"].gold < hard.treasury["zmei"].gold
    assert economy.balance(easy, "zmei").tax < economy.balance(hard, "zmei").tax
    assert economy.balance(easy, "voievodat").tax == economy.balance(hard, "voievodat").tax
