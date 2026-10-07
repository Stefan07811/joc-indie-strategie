"""The map's overlays: realm colours, realm and province borders, the selected province; and the names
written across the land.
"""

from pathlib import Path

import numpy as np
from panda3d.core import NodePath, TextNode, TransparencyAttrib

from .. import geo
from .world import units


def _upscale(labels, k):
    return np.repeat(np.repeat(labels, k, axis=0), k, axis=1)


def _spread(labels, passes=6):
    """Provinces grown a few texels out to sea, so their colour reaches the true (smooth) shoreline."""
    labels = labels.copy()
    for _ in range(passes):
        grown = labels.copy()
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            moved = np.roll(labels, shift, axis=axis)
            grown = np.where(grown == 0, moved, grown)
        labels = grown
    return labels


def _border_distance(labels, reach=8):
    """Texels from every land texel to the nearest border between two provinces (not the coast),
    smoothed, so the shader can draw borders as clean curves at any zoom."""
    a = labels.astype(np.int32)
    edge = np.zeros(a.shape, bool)
    for axis in (0, 1):
        for shift in (1, -1):
            other = np.roll(a, shift, axis=axis)
            edge |= (other != a) & (other > 0) & (a > 0)
    dist = np.where(edge, 0.5, np.float32(reach)).astype(np.float32)
    for _ in range(reach):
        grown = dist
        for dr, dc, step in ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                             (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)):
            grown = np.minimum(grown, np.roll(np.roll(dist, dr, 0), dc, 1) + step)
        dist = grown
    from ..mapdata import blur
    return blur(dist, 1, passes=2)


def _rounded(labels, passes=3):
    """Labels with their stair-steps rounded off: every texel takes the most common label around it."""
    labels = labels.astype(np.int16)
    for _ in range(passes):
        padded = np.pad(labels, 1, mode="edge")
        h, w = labels.shape
        views = [padded[1 + dr:h + 1 + dr, 1 + dc:w + 1 + dc] for dr in (-1, 0, 1) for dc in (-1, 0, 1)]
        best, best_count = labels.copy(), np.zeros(labels.shape, np.int8)
        for v in views:
            count = sum((v == u) for u in views).astype(np.int8)
            better = count > best_count
            best = np.where(better, v, best)
            best_count = np.where(better, count, best_count)
        labels = np.where(labels > 0, np.where(best > 0, best, labels), 0)
    return labels


class Overlay:
    """The province map for the terrain shader: the province index of every texel (rounded borders),
    and the palettes that colour it (realm colours, religions, ...). Changing who holds what only
    rewrites the small palette, so conquests and selections show at once."""

    def __init__(self, provmap, scale=2):
        from .. import cache
        from ..provinces import DATA
        self.provmap = provmap
        self.scale = scale
        self.fine = cache.cached("province-index", [DATA / "provinces.png", Path(__file__)],
                                 lambda: _spread(_rounded(_upscale(provmap.labels, scale))).astype(np.uint16))
        self.size = max(provmap.by_index) + 1
        self.border_distance = cache.cached("province-border-distance", [DATA / "provinces.png", Path(__file__)],
                                            lambda: _border_distance(self.fine))

    def index_texture(self):
        from panda3d.core import SamplerState, Texture
        h, w = self.fine.shape
        tex = Texture("provinces")
        tex.setup2dTexture(w, h, Texture.T_unsigned_short, Texture.F_r16)
        tex.setRamImage(np.ascontiguousarray(np.flipud(self.fine)).tobytes())
        for setter in (tex.setMinfilter, tex.setMagfilter):
            setter(SamplerState.FT_nearest)
        tex.setWrapU(SamplerState.WM_clamp)
        tex.setWrapV(SamplerState.WM_clamp)
        return tex

    def distance_texture(self):
        from panda3d.core import SamplerState, Texture
        h, w = self.border_distance.shape
        tex = Texture("border-distance")
        tex.setup2dTexture(w, h, Texture.T_float, Texture.F_r32)
        tex.setRamImage(np.ascontiguousarray(np.flipud(self.border_distance)).astype(np.float32).tobytes())
        for setter in (tex.setMinfilter, tex.setMagfilter):
            setter(SamplerState.FT_linear)
        tex.setWrapU(SamplerState.WM_clamp)
        tex.setWrapV(SamplerState.WM_clamp)
        return tex

    def palette(self, color_of, alpha=1.0):
        """RGBA uint8 row (one texel per province index): the colour each province is painted."""
        pal = np.zeros((1, self.size, 4), np.uint8)
        for p in self.provmap.provinces.values():
            c = color_of(p)
            if c is not None:
                pal[0, p.index] = (*c[:3], round(255 * alpha))
        return pal


class Labels:
    """Province names lying on the land, shown when the camera is close."""

    def __init__(self, provmap, height_at, font, parent):
        self.root = parent.attachNewNode("labels")
        self.root.setTransparency(TransparencyAttrib.M_alpha)
        self.root.setDepthWrite(False)
        self.root.setBin("fixed", 20)
        self.nodes = []
        for p in provmap.provinces.values():
            x, y = p.label
            wx, wy = x, geo.HEIGHT - y
            text = TextNode(f"label-{p.id}")
            text.setText(p.name)
            text.setFont(font)
            text.setAlign(TextNode.ACenter)
            text.setTextColor(0.12, 0.09, 0.06, 0.9)
            text.setShadow(0.04, 0.04)
            text.setShadowColor(0.95, 0.9, 0.8, 0.35)
            node = self.root.attachNewNode(text)
            size = min(14.0, max(5.0, (p.area ** 0.5) / 18))
            node.setScale(size)
            node.setPos(wx, wy, height_at(wx, wy) + 2.5)
            node.setP(-90)
            self.nodes.append((node, size))

    def update(self, camera_distance, heading):
        show = camera_distance < 650
        self.root.show() if show else self.root.hide()
        if show:
            for node, size in self.nodes:
                node.setH(heading)


def realm_blocks(provmap, owner_of, capitals=None):
    """{realm: (centre x, y, length, angle in degrees, area)} for the piece of each realm that holds its
    capital (or its biggest connected piece, if the capital is lost or unknown)."""
    import math
    out = {}
    by_realm = {}
    for p in provmap.provinces.values():
        if owner_of.get(p.id):
            by_realm.setdefault(owner_of[p.id], []).append(p)
    for realm, provs in by_realm.items():
        ids = {p.id for p in provs}
        seen, best = set(), []
        for p in provs:
            if p.id in seen:
                continue
            group, stack = [], [p.id]
            seen.add(p.id)
            while stack:
                q = provmap.provinces[stack.pop()]
                group.append(q)
                for n in q.neighbors:
                    if n in ids and n not in seen:
                        seen.add(n)
                        stack.append(n)
            if (capitals or {}).get(realm) in {q.id for q in group}:
                best = group
                break
            if sum(q.area for q in group) > sum(q.area for q in best):
                best = group
        weights = np.array([q.area for q in best], np.float64)
        pts = np.array([q.label for q in best], np.float64)
        centre = (pts * weights[:, None]).sum(0) / weights.sum()
        # stand on land: the province label nearest the centre of mass
        centre = pts[np.argmin(((pts - centre) ** 2).sum(1))] * 0.4 + centre * 0.6
        if len(best) > 1:
            cov = np.cov((pts - centre).T, aweights=weights)
            vals, vecs = np.linalg.eigh(cov)
            major = vecs[:, np.argmax(vals)]
            angle = math.degrees(math.atan2(-major[1], major[0]))
            angle = (angle + 90) % 180 - 90
            angle = max(-40.0, min(40.0, angle))
            length = 2.6 * math.sqrt(max(vals))
        else:
            angle, length = 0.0, math.sqrt(best[0].area) / 1.5
        out[realm] = (float(centre[0]), float(centre[1]), float(length), angle, float(weights.sum()))
    return out


class RealmLabels:
    """Realm names written large across their lands, shown from high up (like a paper map)."""

    def __init__(self, provmap, owner_of, names, height_at, font, parent, capitals=None):
        self.root = parent.attachNewNode("realm-labels")
        self.root.setTransparency(TransparencyAttrib.M_alpha)
        self.root.setDepthTest(False)
        self.root.setDepthWrite(False)
        self.root.setBin("fixed", 30)
        self.font = font
        self.height_at = height_at
        self.provmap = provmap
        self.names = names
        self.capitals = capitals or {}
        self.rebuild(owner_of)

    def rebuild(self, owner_of):
        self.root.getChildren().detach()
        for realm, (x, y, length, angle, area) in realm_blocks(self.provmap, owner_of, self.capitals).items():
            if area < 3000:
                continue  # too small to write across; the province names will do
            name = self.names.get(realm, realm).upper()
            text = TextNode(f"realm-{realm}")
            text.setText(name)
            text.setFont(self.font)
            text.setAlign(TextNode.ACenter)
            text.setTextColor(0.10, 0.07, 0.05, 0.78)
            node = self.root.attachNewNode(text)
            width = max(1.0, text.getWidth())
            size = max(9.0, min(70.0, min(length / width, (area ** 0.5) / 4.5)))
            wx, wy = x, geo.HEIGHT - y
            node.setScale(size)
            node.setPos(wx, wy - size * 0.3, self.height_at(wx, wy) + 6)
            node.setHpr(angle, -90, 0)

    def update(self, camera_distance):
        show = camera_distance >= 650
        self.root.show() if show else self.root.hide()
        self.root.setAlphaScale(min(1.0, (camera_distance - 650) / 250) if show else 0)
