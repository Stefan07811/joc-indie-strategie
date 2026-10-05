import pytest

from legendele.mapshape import adjacency, build_grid, components


@pytest.fixture(scope="module")
def grid(data):
    return build_grid(data.provinces, data.map["width"], data.map["height"])


def test_twenty_provinces(data):
    assert len(data.provinces) == 20


def test_each_faction_capital_is_owned_by_it(data):
    by_id = {p["id"]: p for p in data.provinces}
    for fid, f in data.factions.items():
        if f["capital"]:
            assert by_id[f["capital"]]["owner"] == fid


def test_exactly_one_heart_of_the_mountains(data):
    assert [p["id"] for p in data.provinces if p.get("special") == "heart"] == ["heart"]


def test_neighbours_are_symmetric(data):
    by_id = {p["id"]: p for p in data.provinces}
    for p in data.provinces:
        for n in p["neighbors"]:
            assert p["id"] in by_id[n]["neighbors"], f"{p['id']} -> {n} is one-way"


def test_map_is_connected(data):
    by_id = {p["id"]: p for p in data.provinces}
    seen, stack = {"heart"}, ["heart"]
    while stack:
        for n in by_id[stack.pop()]["neighbors"]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    assert seen == set(by_id)


def test_neighbours_match_the_drawn_map(data, grid):
    """map.json must agree with what the player sees; rerun tools/build_adjacency.py if not."""
    drawn = adjacency(grid)
    for p in data.provinces:
        assert set(p["neighbors"]) == drawn[p["id"]], p["id"]


def test_every_province_is_one_piece_and_contains_its_centre(data, grid):
    for p in data.provinces:
        assert components(grid, p["id"]) == 1, p["id"]
        assert grid[p["y"] // 4][p["x"] // 4] == p["id"]
