"""Armies marching over the campaign map, month by month."""

import numpy as np
import pytest

from crowns.game.armies import Army, Regiment
from crowns.game.calendar import START, Date
from crowns.game.navigation import Navigation
from crowns.mapdata import Ground
from crowns.provinces import ProvinceMap
from crowns.render.orders import months_of, reach_field


@pytest.fixture(scope="module")
def nav():
    return Navigation(Ground(), ProvinceMap())


def town(nav, pid):
    return nav.provmap.provinces[pid].town


def test_the_calendar_turns_by_months():
    assert START == Date(1402, 9) and str(START) == "September 1402"
    assert Date(1402, 12).next() == Date(1403, 1)
    assert Date(1403, 1).season == "winter" and Date(1403, 7).season == "summer"
    assert Date(1404, 2).months_since(START) == 17
    assert Date(1402, 10) > START


def test_an_army_marches_as_far_as_its_month_allows(nav):
    army = Army("w1", "wallachia", "Army of Wallachia", *town(nav, "targoviste"), [Regiment("great_host", 9000)])
    assert army.moves == army.march == 200          # the pace of the peasant host
    assert army.order(nav, *town(nav, "sofia"))
    total = army.route.cost
    walked = army.walk()
    assert walked[0] == town(nav, "targoviste") and army.pos == walked[-1]
    assert army.moves == pytest.approx(0) and army.route is not None
    assert army.walk() == []                     # nothing left this month
    army.new_month()
    walked = army.walk()
    assert army.route is None and army.pos == town(nav, "sofia")
    assert army.moves == pytest.approx(2 * army.march - total, abs=1e-3)


def test_no_march_over_the_sea(nav):
    army = Army("w1", "wallachia", "Army of Wallachia", *town(nav, "targoviste"), [Regiment("great_host", 9000)])
    assert not army.order(nav, 1300, 700)         # the middle of the Black Sea
    assert army.route is None and army.walk() == []


def test_the_route_is_drawn_month_by_month(nav):
    route = nav.route(*town(nav, "suceava"), *town(nav, "caffa"))
    months = months_of(route, 100, 220)
    assert len(months) == 1 + int(np.ceil((route.cost - 100) / 220))
    assert months[0][0] == town(nav, "suceava") and months[-1][-1] == town(nav, "caffa")
    assert months_of(route, 0, 220)[0] == []


def test_the_reach_field_for_the_shader(nav):
    reach = nav.reach(*town(nav, "targoviste"), 220)
    field, rect = reach_field(reach)
    assert field.dtype == np.float32 and np.isfinite(field).all()
    assert field.min() == 0 and field.max() == pytest.approx(1.5)
    assert rect[2] == field.shape[1] * 2 and rect[3] == field.shape[0] * 2
