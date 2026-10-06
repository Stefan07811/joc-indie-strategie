import random

from legendele.game.battle import Regiment, Side, break_point, predict, resolve


def regs(*unit_ids, hp=None):
    from legendele.game import GameData
    units = GameData.load().units
    return [Regiment(u, hp if hp is not None else units[u]["hp"]) for u in unit_ids]


def test_the_stronger_side_wins(data):
    big = Side("zmei", regs("zmei_buzdugan", "zmei_buzdugan", "pui_de_zmeu"), "Pajura")
    small = Side("haiduci", regs("haiduc_brigands"))
    result = resolve(big, small, data.units, random.Random(1), province="cluj")
    assert result.attacker_won
    assert result.defender.end_regiments == 0 or result.defender.losses > result.attacker.losses
    assert result.winning_faction == "zmei" and result.losing_faction == "haiduci"


def test_damage_is_applied_and_the_dead_are_removed(data):
    a = Side("voievodat", regs("oteni", "oteni", "calareti"), "Vlad")
    d = Side("haiduci", regs("haiduc_brigands", "haiduc_brigands"))
    before = sum(r.hp for r in a.regiments)
    result = resolve(a, d, data.units, random.Random(3))
    assert sum(r.hp for r in a.regiments) == result.attacker.end_hp < before
    assert all(r.hp >= 8 for r in a.regiments + d.regiments)
    assert result.attacker.end_regiments == len(a.regiments)


def test_walls_turn_the_tide(data):
    def fight(defense_mult, resolve_bonus):
        wins = 0
        for seed in range(40):
            a = Side("voievodat", regs("oteni", "oteni", "arcasi"), "Vlad")
            d = Side("zmei", regs("pui_de_zmeu", "pui_de_zmeu"), defense_mult=defense_mult, resolve_bonus=resolve_bonus)
            wins += resolve(a, d, data.units, random.Random(seed)).attacker_won
        return wins
    assert fight(1.5, 0.2) < fight(1.0, 0.0)


def test_fearless_dead_hold_longer_than_living_men(data):
    assert break_point(regs("morti", "morti"), data.units) > break_point(regs("oteni", "oteni"), data.units)


def test_hunters_strike_creatures_harder(data):
    def damage_dealt(creature):
        hunters = Side("voievodat", regs("vanatori", "vanatori"), "Vlad")
        prey = Side("strigoi", regs("strigoi", "strigoi", "strigoi"), creature=creature)
        return resolve(hunters, prey, data.units, random.Random(5)).defender.losses
    assert damage_dealt(True) > damage_dealt(False)


def test_predict_does_not_touch_the_real_armies(data):
    a = Side("iele", regs("rusalii", "valve"), "Sânziana")
    d = Side("haiduci", regs("haiduc_brigands"))
    wins, share = predict(a, d, data.units)
    assert wins and 0 < share <= 1
    assert [r.hp for r in a.regiments] == [80, 100] and len(d.regiments) == 1


def test_same_seed_same_battle(data):
    def run():
        a = Side("strigoi", regs("morti", "morti", "varcolaci"), "Gravedigger")
        d = Side("voievodat", regs("oteni", "arcasi"))
        r = resolve(a, d, data.units, random.Random(11))
        return r.winner, r.rounds, [x.hp for x in a.regiments], [x.hp for x in d.regiments]
    assert run() == run()
