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
    path, cost = nav.path(*town(nav, "targoviste"), *geo.to_map(34.0, 43.0))
    assert path is None and cost == math.inf


def test_the_danube_is_crossed_at_its_fords(nav):
    # straight across the Danube between Vidin and Nikopol, far from any crossing ...
    north, south = geo.to_map(23.9, 44.1), geo.to_map(23.9, 43.5)
    straight = math.dist(north, south) * geo.KM_PER_PX
    path, cost = nav.path(*north, *south)
    # ... the army either pays for the boats or marches to a ford first
    assert cost > straight * 1.2
    lons = [geo.to_lonlat(*p)[0] for p in path]
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
    path, cost = nav.path(*town(nav, "targoviste"), *town(nav, "giurgiu"))
    assert cost == pytest.approx(reach.cost_to(*town(nav, "giurgiu")), rel=0.02, abs=CELL_KM)


def test_the_straits_are_ferried_over(nav):
    path, cost = nav.path(*town(nav, "constantinople"), *town(nav, "bursa"))
    assert path is not None and cost < 400
    path, cost = nav.path(*town(nav, "targoviste"), *town(nav, "sofia"))
    assert path is not None and 300 < cost < 600


def test_paths_are_simplified_into_strides(nav):
    path, _ = nav.path(*town(nav, "buda"), *town(nav, "belgrade"))
    assert path[0] == town(nav, "buda") and path[-1] == town(nav, "belgrade")
    assert 2 <= len(path) < 40
    for x, y in path:
        assert np.isfinite(nav.cost[nav.cell(x, y)])
