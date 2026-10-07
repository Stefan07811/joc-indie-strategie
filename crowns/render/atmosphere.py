"""The air over the battlefield: the sky with its drifting clouds, the haze toward the horizon, and the sun
that throws the shadows of the regiments, the trees and the hills across the field."""

import math

import numpy as np
from panda3d.core import BitMask32, CompassEffect, DirectionalLight, Shader, Vec3

from .figures import SHADERS, geom_node

HAZE = (0.79, 0.82, 0.82)        # the colour of the air at the horizon: the sky's foot and the far land
ZENITH = (0.38, 0.56, 0.78)
FOG = 1.0 / 520.0                # how thick the haze is, per world unit
SUN = Vec3(-0.62, 0.40, 0.50).normalized()   # an afternoon sun, low enough for long shadows
SHADOW_CASTERS = BitMask32.bit(5)   # what the sun's camera sees


def _dome(rings=14, segments=36, radius=50.0):
    """Triangles of a sphere around the camera, from below the horizon up to the zenith."""
    verts = []
    lats = np.linspace(-0.35, math.pi / 2, rings + 1)
    lons = np.linspace(0, 2 * math.pi, segments + 1)

    def p(lat, lon):
        return (radius * math.cos(lat) * math.cos(lon), radius * math.cos(lat) * math.sin(lon), radius * math.sin(lat))
    for i in range(rings):
        for j in range(segments):
            a, b = p(lats[i], lons[j]), p(lats[i], lons[j + 1])
            c, d = p(lats[i + 1], lons[j + 1]), p(lats[i + 1], lons[j])
            verts += [(a, b, c), (a, c, d)]
    verts = np.array(verts, np.float64)
    return verts, np.ones((len(verts), 4))


class Sky:
    """A dome that goes wherever the camera goes, drawn behind everything else."""

    def __init__(self, camera, render, sun):
        self.root = camera.attachNewNode(geom_node("sky", *_dome()))
        self.root.setEffect(CompassEffect.make(render, CompassEffect.P_rot))
        self.root.setShader(Shader.load(Shader.SL_GLSL, str(SHADERS / "sky.vert"), str(SHADERS / "sky.frag")))
        self.root.setShaderInputs(sun_dir=sun, haze=Vec3(*HAZE), zenith=Vec3(*ZENITH), time=0.0)
        self.root.setBin("background", 0)
        self.root.setDepthWrite(False)
        self.root.setDepthTest(False)
        self.root.setTwoSided(True)
        self.root.setLightOff(1)
        self.root.hide(SHADOW_CASTERS)
        self.time = 0.0

    def update(self, dt):
        self.time += dt
        self.root.setShaderInput("time", self.time)

    def destroy(self):
        self.root.removeNode()


class Sun:
    """The sun as a light that casts shadows: its camera follows what the player looks at, covering more
    ground the further the camera stands back, and steps by whole texels so the shadows do not shimmer."""

    def __init__(self, render, sun_dir, size=4096, back=160.0):
        self.light = DirectionalLight("sun")
        self.light.setColor((1, 1, 1, 1))
        self.light.setShadowCaster(True, size, size)
        self.light.setCameraMask(SHADOW_CASTERS)
        self.lens = self.light.getLens()
        self.lens.setNearFar(10.0, back * 2.5)
        self.root = render.attachNewNode(self.light)
        self.dir = Vec3(sun_dir).normalized()
        self.size = size
        self.back = back
        self.root.setPos(self.dir * back)
        self.root.lookAt(0, 0, 0)

    def follow(self, x, y, z, span):
        """Cover a square of `span` world units around (x, y, z)."""
        self.lens.setFilmSize(span, span)
        texel = span / self.size
        q = self.root.getQuat()
        right, up, forward = q.getRight(), q.getUp(), q.getForward()
        t = Vec3(x, y, z)
        a = round(t.dot(right) / texel) * texel
        b = round(t.dot(up) / texel) * texel
        t = right * a + up * b + forward * t.dot(forward)
        self.root.setPos(t + self.dir * self.back)

    def destroy(self):
        self.light.setShadowCaster(False)
        self.root.removeNode()
