"""The 3D map: the land as a mesh lifted from the real relief, the sea over it, lit by GLSL shaders.

World units are map pixels (1.5 km): X runs east, Y north (Y = map height - map row), Z up. Heights are
exaggerated EXAGGERATION times, as on every strategy map, or the Carpathians would be a crease.
"""

from pathlib import Path

import numpy as np
from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat, NodePath, SamplerState,
                          Shader, Texture, TransparencyAttrib, Vec2, Vec3, Vec4)

from .. import geo
from ..mapdata import Ground

SHADERS = Path(__file__).resolve().parent / "shaders"
EXAGGERATION = 8.0
SEA_FLOOR = 0.04  # underwater depths are flattened: the water shader shows depth by colour
STEP = 2          # map pixels per mesh vertex
CHUNK = 64        # mesh cells per chunk side (each chunk is culled on its own)
HAZE = (0.66, 0.72, 0.78)
SUN = Vec3(-0.55, 0.35, 0.76).normalized()
# The map's looks: (land shader, sea shader, GLSL defines, name shown to the player)
STYLES = {
    "codex": ("terrain_codex.frag", "water_codex.frag", [], "Codex: an engraved portolan chart"),
    "real": ("terrain.frag", "water.frag", [], "Realistic relief (for checking the map)"),
}


def load_shader(vert, frag, defines=()):
    """A GLSL shader from shaders/, with #defines inserted after the #version line."""
    def source(name):
        text = (SHADERS / name).read_text(encoding="utf-8")
        head, _, rest = text.partition("\n")
        return head + "\n" + "".join(f"#define {d}\n" for d in defines) + rest
    return Shader.make(Shader.SL_GLSL, source(vert), source(frag))


def units(metres):
    """Height in world units."""
    return metres / 1000 / geo.KM_PER_PX * EXAGGERATION


def texture(rgb, name, mipmap=True):
    """A texture from an RGB(A) uint8 array whose row 0 is the north."""
    h, w, c = rgb.shape
    tex = Texture(name)
    tex.setup2dTexture(w, h, Texture.T_unsigned_byte, Texture.F_rgba8 if c == 4 else Texture.F_rgb8)
    tex.setRamImageAs(np.ascontiguousarray(np.flipud(rgb)).tobytes(), "RGBA" if c == 4 else "RGB")
    tex.setWrapU(SamplerState.WM_clamp)
    tex.setWrapV(SamplerState.WM_clamp)
    if mipmap:
        tex.setMinfilter(SamplerState.FT_linear_mipmap_linear)
        tex.setAnisotropicDegree(8)
    else:
        tex.setMinfilter(SamplerState.FT_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    return tex


def float_texture(a, name):
    h, w = a.shape
    tex = Texture(name)
    tex.setup2dTexture(w, h, Texture.T_float, Texture.F_r32)
    tex.setRamImage(np.ascontiguousarray(np.flipud(a)).astype(np.float32).tobytes())
    tex.setWrapU(SamplerState.WM_clamp)
    tex.setWrapV(SamplerState.WM_clamp)
    tex.setMinfilter(SamplerState.FT_linear)
    tex.setMagfilter(SamplerState.FT_linear)
    return tex


def _mesh(name, xs, ys, zs, us, vs, cols, rows):
    """A grid mesh of rows x cols vertices (row-major arrays), as a GeomNode."""
    fmt = GeomVertexFormat.getV3t2()
    vdata = GeomVertexData(name, fmt, Geom.UH_static)
    vdata.uncleanSetNumRows(cols * rows)
    verts = np.stack([xs, ys, zs, us, vs], axis=-1).astype(np.float32)
    vdata.modifyArrayHandle(0).copyDataFrom(np.ascontiguousarray(verts).tobytes())
    i = np.arange(rows * cols, dtype=np.uint32).reshape(rows, cols)
    a, b, c, d = i[:-1, :-1], i[:-1, 1:], i[1:, :-1], i[1:, 1:]
    # rows run south in the arrays; wind the triangles counter-clockwise seen from above
    tris_idx = np.stack([a, c, b, b, c, d], axis=-1).reshape(-1).astype(np.uint32)
    tris = GeomTriangles(Geom.UH_static)
    tris.setIndexType(Geom.NT_uint32)
    handle = tris.modifyVertices()
    handle.uncleanSetNumRows(len(tris_idx))
    handle.modifyHandle().copyDataFrom(tris_idx.tobytes())
    geom = Geom(vdata)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    return node


class MapWorld:
    """The terrain and the sea, ready to attach to a scene graph."""

    def __init__(self, ground=None, style="codex"):
        self.ground = ground or Ground()
        self.style = style
        self.root = NodePath("map")
        self.size = Vec2(geo.WIDTH, geo.HEIGHT)
        self._build_textures()
        self._build_terrain()
        self._build_water()
        self.set_style(style)

    def _build_textures(self):
        from .. import cache, mapdata
        g = self.ground
        sources = [mapdata.DATA / "height.png", mapdata.DATA / "rivers.json", mapdata.DATA / "lakes.json",
                   Path(mapdata.__file__)]
        self.color_tex = texture(cache.cached("colors", sources, g.color_map), "colors")
        self.normal_tex = texture(cache.cached(f"normals-{EXAGGERATION}", sources,
                                               lambda: g.normal_map(EXAGGERATION)), "normals")
        self.height_tex = float_texture(g.height, "heights")
        self.coast_tex = float_texture(cache.cached("coast", sources, g.coast_distance), "coast")
        blank = np.zeros((1, 2, 4), np.uint8)
        self.palette_tex = self._palette_texture(blank)
        self.province_tex = texture(np.zeros((2, 2, 4), np.uint8), "provinces", mipmap=False)

    def height_at(self, x, y):
        """World Z of the ground at world (x, y), the sea counting as 0."""
        h = self.ground.height
        col = int(np.clip(x, 0, h.shape[1] - 1))
        row = int(np.clip(geo.HEIGHT - y, 0, h.shape[0] - 1))
        return max(0.0, units(float(h[row, col])))

    def set_style(self, style):
        """Change the map's look (one of STYLES) on the fly."""
        self.style = style
        land, sea, defines, _ = STYLES[style]
        self.terrain.setShader(load_shader("terrain.vert", land, defines))
        self.water.setShader(load_shader("water.vert", sea, defines))

    def _build_terrain(self):
        h = self.ground.height
        rows_all = np.arange(0, h.shape[0], STEP)
        cols_all = np.arange(0, h.shape[1], STEP)
        if rows_all[-1] != h.shape[0] - 1:
            rows_all = np.append(rows_all, h.shape[0] - 1)
        if cols_all[-1] != h.shape[1] - 1:
            cols_all = np.append(cols_all, h.shape[1] - 1)
        hs = h[np.ix_(rows_all, cols_all)]
        # continuous across the coast, so the water line follows the true shore, not the mesh's steps
        depth = np.clip(-hs / 40, 0, 1)
        z = np.where(hs > 0, units(hs), units(hs) * SEA_FLOOR - 1.2 * depth * depth * (3 - 2 * depth))
        self.terrain = self.root.attachNewNode("terrain")
        for r0 in range(0, len(rows_all) - 1, CHUNK):
            for c0 in range(0, len(cols_all) - 1, CHUNK):
                r = rows_all[r0:r0 + CHUNK + 1]
                c = cols_all[c0:c0 + CHUNK + 1]
                C, R = np.meshgrid(c, r)
                zz = z[r0:r0 + CHUNK + 1, c0:c0 + CHUNK + 1]
                xs, ys = C.astype(np.float32), (geo.HEIGHT - R).astype(np.float32)
                us, vs = (C + 0.5) / h.shape[1], 1 - (R + 0.5) / h.shape[0]
                node = _mesh(f"chunk{r0}_{c0}", xs.ravel(), ys.ravel(), zz.ravel(), us.ravel(), vs.ravel(),
                             len(c), len(r))
                self.terrain.attachNewNode(node)
        self.terrain.setShaderInputs(colormap=self.color_tex, normalmap=self.normal_tex, provinces=self.province_tex,
                                     palette=self.palette_tex, index_size=Vec2(2, 2), palette_size=2.0,
                                     coast=self.coast_tex, time=0.0, borderdist=self.coast_tex,
                                     selected=-1, hovered=-1, sun_dir=SUN, cam_pos=Vec3(0, 0, 1000),
                                     haze=Vec3(*HAZE), map_size=self.size, overlay_mix=0.0,
                                     reach=self.coast_tex, reach_rect=Vec4(0, 0, 1, 1), reach_on=0.0)

    def _build_water(self):
        w, h = geo.WIDTH, geo.HEIGHT
        xs = np.array([0, w, 0, w], np.float32)
        ys = np.array([h, h, 0, 0], np.float32)
        node = _mesh("water", xs, ys, np.zeros(4, np.float32), np.array([0, 1, 0, 1], np.float32),
                     np.array([1, 1, 0, 0], np.float32), 2, 2)
        self.water = self.root.attachNewNode(node)
        self.water.setShaderInputs(heightmap=self.height_tex, coast=self.coast_tex, sun_dir=SUN,
                                   cam_pos=Vec3(0, 0, 1000), haze=Vec3(*HAZE), map_size=self.size, time=0.0)
        self.water.setTransparency(TransparencyAttrib.M_alpha)
        self.water.setBin("transparent", 10)
        self.water.setDepthWrite(False)

    def update(self, cam_pos, time):
        self.terrain.setShaderInput("cam_pos", cam_pos)
        self.terrain.setShaderInput("time", time)
        self.water.setShaderInput("cam_pos", cam_pos)
        self.water.setShaderInput("time", time)

    @staticmethod
    def _palette_texture(rgba):
        tex = texture(rgba, "palette", mipmap=False)
        tex.setMinfilter(SamplerState.FT_nearest)
        tex.setMagfilter(SamplerState.FT_nearest)
        return tex

    def set_provinces(self, index_texture, distance_texture):
        """The province index of every texel, and every texel's distance to a province border."""
        self.province_tex = index_texture
        self.terrain.setShaderInputs(provinces=index_texture, borderdist=distance_texture,
                                     index_size=Vec2(index_texture.getXSize(), index_texture.getYSize()))

    def set_palette(self, rgba, mix):
        """The map mode: a colour per province index (1 x N RGBA), and how strongly it shows."""
        self.palette_tex = self._palette_texture(rgba)
        self.terrain.setShaderInputs(palette=self.palette_tex, palette_size=float(rgba.shape[1]), overlay_mix=mix)

    def set_reach(self, field=None, rect=None):
        """Show how far the chosen army can march this month: `field` is km / budget over the map
        pixels `rect` (left, top, width, height); None hides it."""
        if field is None:
            self.terrain.setShaderInput("reach_on", 0.0)
            return
        self.reach_tex = float_texture(field, "reach")
        self.terrain.setShaderInputs(reach=self.reach_tex, reach_rect=Vec4(*rect), reach_on=1.0)

    def set_highlight(self, selected=None, hovered=None):
        self.terrain.setShaderInputs(selected=-1 if selected is None else int(selected),
                                     hovered=-1 if hovered is None else int(hovered))
