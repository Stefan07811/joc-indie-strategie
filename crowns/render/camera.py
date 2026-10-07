"""The strategy camera: looks at a point on the map from a distance, tilting down as it rises.

Close to the ground it looks across the land (like a Total War campaign map); high up it looks almost
straight down (like a paper map). It can turn around the point it looks at.
"""

import math

from panda3d.core import Vec3

from .. import geo

MIN_DIST, MAX_DIST = 90.0, 1900.0
NEAR_PITCH, FAR_PITCH = 38.0, 72.0  # degrees below the horizon


class StrategyCamera:
    def __init__(self, camera, lens, height_at=None, limits=(MIN_DIST, MAX_DIST), bounds=None, near=8.0,
                 pitches=(NEAR_PITCH, FAR_PITCH)):
        self.camera = camera
        self.near_pitch, self.far_pitch = pitches
        self.lens = lens
        self.height_at = height_at or (lambda x, y: 0.0)
        self.min_dist, self.max_dist = limits
        self.bounds = bounds or (geo.WIDTH, geo.HEIGHT)
        self.target = [self.bounds[0] * 0.45, self.bounds[1] * 0.55]
        self.distance = min(900.0, self.max_dist)
        self.heading = 0.0  # degrees, 0 = north up
        self.near = near
        lens.setFov(40)
        lens.setNearFar(near, 8000.0)
        self.apply()

    def activate(self):
        """Make this the camera's controller again (after another one used the lens)."""
        self.lens.setNearFar(self.near, 8000.0)
        self.apply()

    @property
    def zoom(self):
        """0 close to the ground .. 1 as high as it goes."""
        return (math.log(self.distance) - math.log(self.min_dist)) / \
            (math.log(self.max_dist) - math.log(self.min_dist))

    @property
    def pitch(self):
        z = self.zoom
        return self.near_pitch + (self.far_pitch - self.near_pitch) * z * z

    def look_at(self, x, y, distance=None):
        self.target = [x, y]
        if distance:
            self.distance = distance
        self.apply()

    def pan(self, dx, dy):
        """Move by (dx, dy) screen-relative units, scaled with the distance."""
        a = math.radians(self.heading)
        k = self.distance / 600
        self.target[0] += (dx * math.cos(a) - dy * math.sin(a)) * k
        self.target[1] += (dx * math.sin(a) + dy * math.cos(a)) * k
        self.apply()

    def zoom_by(self, factor):
        self.distance = min(self.max_dist, max(self.min_dist, self.distance * factor))
        self.apply()

    def turn(self, degrees):
        self.heading = (self.heading + degrees) % 360
        self.apply()

    def apply(self):
        self.target[0] = min(self.bounds[0], max(0.0, self.target[0]))
        self.target[1] = min(self.bounds[1], max(0.0, self.target[1]))
        ground = self.height_at(*self.target)
        p, h = math.radians(self.pitch), math.radians(self.heading)
        back = self.distance * math.cos(p)
        pos = Vec3(self.target[0] + back * math.sin(h), self.target[1] - back * math.cos(h),
                   ground + self.distance * math.sin(p))
        self.camera.setPos(pos)
        self.camera.lookAt(Vec3(self.target[0], self.target[1], ground))

    @property
    def position(self):
        return self.camera.getPos()
