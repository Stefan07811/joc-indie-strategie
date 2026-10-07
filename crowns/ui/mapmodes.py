"""The map's ways of looking at the world: who holds the land, the land itself, faiths, peoples, friends and
foes, and the trade roads. Each gives a colour (0-255 RGB) for a province, or None to leave it unpainted."""

import zlib

from ..game.trade import ROUTES

MODES = [("political", "Realms"), ("terrain", "Land"), ("religion", "Faiths"), ("culture", "Peoples"),
         ("diplomacy", "Friends and foes"), ("trade", "Trade roads")]
RELIGION = {"catholic": (214, 178, 84), "orthodox": (140, 86, 150), "sunni": (78, 140, 88),
            "armenian": (190, 110, 60), "shia": (60, 120, 130), "jewish": (90, 110, 170)}
ROUTE_COLORS = [(176, 120, 52), (54, 102, 160), (150, 60, 60), (60, 130, 120), (120, 90, 160), (170, 140, 40),
                (90, 140, 60)]
DIPLOMACY = {"own": (60, 100, 190), "vassal": (110, 160, 220), "lord": (220, 130, 50), "ally": (70, 160, 80),
             "war": (200, 50, 40), "truce": (220, 200, 90), "other": (205, 195, 170)}


def _culture_color(culture):
    h = zlib.crc32(culture.encode())
    return (80 + h % 150, 80 + (h >> 8) % 150, 80 + (h >> 16) % 150)


def relation(c, viewer, tag):
    if viewer is None:
        return "other"
    if tag == viewer:
        return "own"
    if c.at_war(viewer, tag):
        return "war"
    held = c.overlord.get(tag)
    if held and held[0] == viewer:
        return "vassal"
    lord = c.overlord.get(viewer)
    if lord and lord[0] == tag:
        return "lord"
    if sorted((viewer, tag)) in c.alliances:
        return "ally"
    if c.truce_with(viewer, tag):
        return "truce"
    return "other"


def painter(c, mode, colors):
    """fn(province) -> colour for the mode."""
    if mode == "religion":
        return lambda p: RELIGION.get(c.static(p.id).religion, (150, 150, 150))
    if mode == "culture":
        return lambda p: _culture_color(c.static(p.id).culture)
    if mode == "diplomacy":
        return lambda p: DIPLOMACY[relation(c, c.player, c.provinces[p.id].owner)]
    if mode == "trade":
        on = {}
        for k, (name, (_, towns)) in enumerate(ROUTES.items()):
            open_, _ = c.route_state(name)
            for town in towns:
                if town not in on:
                    on[town] = ROUTE_COLORS[k % len(ROUTE_COLORS)] if open_ >= 1.0 else (200, 60, 50)
        return lambda p: on.get(p.id, (215, 205, 180))
    return lambda p: colors.get(c.provinces[p.id].owner)


LEGEND = {
    "religion": "Gold: Catholic · purple: Orthodox · green: Muslim · orange: Armenian",
    "diplomacy": "Blue: yours · light blue: your vassals · orange: your overlord · green: allies · red: at war "
                 "· yellow: truce",
    "trade": "Each road in its colour; red: a road cut by war or siege",
    "culture": "Each people in its own colour",
}
