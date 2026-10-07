"""Armies on the campaign map: where they stand, how far they may still march this month, and their
orders. They march Total War style, anywhere over the land, spending a monthly budget of movement."""

from dataclasses import dataclass
from typing import Optional

from .navigation import Route

FOOT_MARCH_KM = 220.0    # a month of marching for an army on foot, with its carts and baggage
HORSE_MARCH_KM = 330.0   # light horsemen living off the land: akinjis, Tatars, the Moldavian host


@dataclass
class Army:
    id: str
    owner: str
    name: str
    x: float                 # map pixels
    y: float
    men: int
    march_km: float = FOOT_MARCH_KM
    moves: Optional[float] = None      # km of movement left this month
    route: Optional[Route] = None      # standing orders: the march still ahead

    def __post_init__(self):
        if self.moves is None:
            self.moves = self.march_km

    @property
    def pos(self):
        return self.x, self.y

    def reach(self, nav):
        return nav.reach(self.x, self.y, self.moves)

    def order(self, nav, x, y):
        """Order a march to map pixel (x, y); False if no road leads there."""
        route = nav.route(self.x, self.y, x, y)
        if route is None:
            return False
        self.route = route
        return True

    def halt(self):
        self.route = None

    def march(self):
        """Walk the orders as far as this month's movement allows: the points walked (none if the army
        stays where it is)."""
        if self.route is None or self.moves <= 0:
            return []
        walked, self.route, spent = self.route.advance(self.moves)
        self.moves = max(0.0, self.moves - spent)
        self.x, self.y = walked[-1]
        return walked

    def new_month(self):
        self.moves = self.march_km
