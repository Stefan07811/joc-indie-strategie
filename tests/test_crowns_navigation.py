"""Total War style movement over the real land: what costs how much, where armies can go in a month."""

import math

import numpy as np
import pytest

from crowns import geo
from crowns.game.navigation import CELL_KM, Navigation
from crowns.mapdata import Ground
from crowns.provinces import ProvinceMap


@pytest.fixture(scope="module")
def nav():
    return Navigation(Ground(), ProvinceMap())


def town(nav, pid):
    return nav.provmap.provinces[pid].town


def test_the_sea_cannot_be_marched_over(nav):
    assert not np.isfinite(nav.cost[nav.cell(*geo.to_map(34.0, 43.0))])   # the middle of the Black Sea
    assert np.isfinite(nav.cost[nav.cell(*town(nav, "targoviste"))])
    assert nav.route(*town(nav, "targoviste"), *geo.to_map(34.0, 43.0)) is None


def test_the_danube_is_crossed_at_its_fords(nav):
    # straight across the Danube between Vidin and Nikopol, far from any crossing ...
    north, south = geo.to_map(23.9, 44.1), geo.to_map(23.9, 43.5)
    straight = math.dist(north, south) * geo.KM_PER_PX
    route = nav.route(*north, *south)
    cost = route.cost
    # ... the army either pays for the boats or marches to a ford first
    assert cost > straight * 1.2
    lons = [geo.to_lonlat(*p)[0] for p in route.points]
    assert cost > straight + 40 or max(abs(lon - 23.9) for lon in lons) > 0.15


def test_a_diagonal_step_cannot_slip_across_a_river():
    # a river drawn diagonally between two cells of plain land
    nav = Navigation.__new__(Navigation)
    nav.__dict__["cost"] = np.array([[1, 25], [25, 1]], np.float32)
    down_right = nav.steps[7]
    assert down_right[1, 1] > 10 * math.sqrt(2) * CELL_KM
    assert nav.steps[1][1, 1] == pytest.approx(13 * CELL_KM)      # straight down, into the river


def test_a_month_of_marching_from_targoviste(nav):
    reach = nav.reach(*town(nav, "targoviste"), 220)
    assert reach.can_reach(*town(nav, "targoviste"))
    assert reach.can_reach(*town(nav, "giurgiu"))
    assert not reach.can_reach(*town(nav, "sofia"))
    assert not reach.can_reach(*town(nav, "constantinople"))
    assert reach.cost_to(*town(nav, "giurgiu")) <= 220
    # the reach agrees with the march along the cheapest path
    cost = nav.route(*town(nav, "targoviste"), *town(nav, "giurgiu")).cost
    assert cost == pytest.approx(reach.cost_to(*town(nav, "giurgiu")), rel=0.02, abs=CELL_KM)


def test_the_straits_are_ferried_over(nav):
    assert nav.route(*town(nav, "constantinople"), *town(nav, "bursa")).cost < 400
    assert 300 < nav.route(*town(nav, "targoviste"), *town(nav, "sofia")).cost < 600


def test_paths_are_simplified_into_strides(nav):
    path = nav.route(*town(nav, "buda"), *town(nav, "belgrade")).points
    assert path[0] == town(nav, "buda") and path[-1] == town(nav, "belgrade")
    assert 2 <= len(path) < 40
    for x, y in path:
        assert np.isfinite(nav.cost[nav.cell(x, y)])


def test_a_long_march_takes_months(nav):
    route = nav.route(*town(nav, "suceava"), *town(nav, "caffa"))
    assert route.costs == sorted(route.costs) and route.costs[0] == 0
    months, left = 0, route
    while left is not None:
        walked, left, spent = left.advance(200)
        months += 1
        assert spent <= 200 + 1e-6 and len(walked) >= 2
        if left is not None:
            assert walked[-1] == left.points[0]
            assert np.isfinite(nav.cost[nav.cell(*walked[-1])])
    assert months == math.ceil(route.cost / 200)
    near, far = route.split(200)
    assert near[0] == town(nav, "suceava") and far[-1] == town(nav, "caffa")


def test_islands_cannot_be_reached_on_foot(nav):
    import time
    from collections import Counter
    regions = nav.regions
    big = Counter(regions[regions > 0].ravel().tolist()).most_common(1)[0][0]
    assert regions[nav.cell(*town(nav, "targoviste"))] == big == regions[nav.cell(*town(nav, "konya"))]
    assert regions[nav.cell(*town(nav, "candia"))] not in (0, big)                   # Crete
    assert nav.connected(*town(nav, "constantinople"), *town(nav, "bursa"))           # the Bosporus ferry
    assert not nav.connected(*town(nav, "targoviste"), *town(nav, "rhodes"))
    t = time.time()
    assert nav.route(*town(nav, "targoviste"), *town(nav, "nicosia")) is None
    assert time.time() - t < 0.05
