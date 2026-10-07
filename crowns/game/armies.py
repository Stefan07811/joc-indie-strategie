"""Armies on the campaign map: where they stand, how far they may still march this month, and their
orders. They march Total War style, anywhere over the land, spending a monthly budget of movement."""

from dataclasses import dataclass, field
from typing import Optional

from .navigation import Route
from .rules import UNITS

FOOT_MARCH_KM = 220.0    # a month of marching for an army on foot, with its carts and baggage
HORSE_MARCH_KM = 330.0   # light horsemen living off the land: akinjis, Tatars, the Moldavian host


@dataclass
class Regiment:
    unit: str                # a key of rules.UNITS
    men: int
    experience: float = 0.0  # 0 .. 1

    @property
    def type(self):
        return UNITS[self.unit]

    @property
    def upkeep(self):
        return self.type.upkeep * self.men / self.type.men


@dataclass
class Army:
    id: str
    owner: str
    name: str
    x: float                 # map pixels
    y: float
    regiments: list = field(default_factory=list)
    march: Optional[float] = None      # km a month; by default the pace of its slowest troops
    moves: Optional[float] = None      # km of movement left this month
    route: Optional[Route] = None      # standing orders: the march still ahead
    commander: Optional[str] = None    # the person leading it

    def __post_init__(self):
        if self.march is None:
            self.march = min((r.type.march for r in self.regiments), default=FOOT_MARCH_KM)
        if self.moves is None:
            self.moves = self.march
        self.last_walk = []

    @property
    def march_km(self):
        return self.march

    @property
    def men(self):
        return sum(r.men for r in self.regiments)

    @property
    def upkeep(self):
        return sum(r.upkeep for r in self.regiments)

    @property
    def pos(self):
        return self.x, self.y

    def reach(self, nav):
        return nav.reach(self.x, self.y, self.moves)

    def order(self, nav, x, y, greed=1.0):
        """Order a march to map pixel (x, y); False if no road leads there."""
        route = nav.route(self.x, self.y, x, y, greed=greed)
        if route is None:
            return False
        self.route = route
        return True

    def halt(self):
        self.route = None

    def walk(self):
        """Walk the orders as far as this month's movement allows: the points walked (none if the army
        stays where it is)."""
        self.last_walk = []
        if self.route is None or self.moves <= 0:
            return []
        walked, self.route, spent = self.route.advance(self.moves)
        self.moves = max(0.0, self.moves - spent)
        self.x, self.y = walked[-1]
        self.last_walk = walked    # for the miniature to walk (not saved)
        return walked

    def new_month(self):
        self.moves = self.march
