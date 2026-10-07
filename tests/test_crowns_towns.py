"""The towns' miniatures: bigger towns have more, walls follow the fortifications, faith shapes the
church."""

from crowns.render.towns import town_model


def tris(city, fort, religion="orthodox", culture="romanian"):
    verts, colors = town_model(city, fort, religion, culture, 1)
    assert verts.shape[1:] == (3, 3) and len(colors) == len(verts)
    return len(verts)


def test_towns_grow_with_their_people_and_walls():
    assert tris(0, 0) < tris(6, 0) < tris(25, 0)
    assert tris(6, 0) < tris(6, 1) < tris(6, 3)


def test_the_faith_shows_in_the_skyline():
    mosque = town_model(10, 0, "sunni", "turkish", 1)[0]
    church = town_model(10, 0, "catholic", "hungarian", 1)[0]
    assert mosque[..., 2].max() > church[..., 2].max() * 0.9      # the minaret stands tall
    camp = town_model(6, 0, "sunni", "tatar", 1)[0]               # felt tents, no minaret
    town = town_model(6, 0, "sunni", "turkish", 1)[0]
    assert camp[..., 2].max() < town[..., 2].max() / 2
