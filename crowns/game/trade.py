"""The great trade roads of the Balkans and the seas about them, as the merchants of 1402 knew them. Every
leg of a road between two towns is open while their holders are not at war with each other and neither
town is besieged; the silver that moves along a road is shared among the towns on it, and the merchant
republics take a larger share in their own ports. A war across a road starves everyone on it."""

# name -> (ducats a month moving along the whole road when every leg is open, the towns in order)
ROUTES = {
    "the Danube": (650, ["vienna", "pozsony", "esztergom", "buda", "kalocsa", "bacs", "szerem", "belgrade",
                         "smederevo", "branicevo", "vidin", "nikopol", "ruse", "silistra", "braila", "chilia"]),
    "the Black Sea": (750, ["tana", "caffa", "cetatea_alba", "chilia", "varna", "anchialos", "constantinople"]),
    "the Anatolian shore": (450, ["constantinople", "izmit", "amasra", "sinop", "samsun", "kerasous",
                                  "trebizond"]),
    "the Adriatic": (900, ["venice", "istria", "zara", "spalato", "ragusa", "kotor", "durazzo", "valona",
                           "corfu"]),
    "the Aegean": (700, ["constantinople", "gallipoli", "lemnos", "lesbos", "chios", "smyrna", "naxos", "candia"]),
    "the Via Militaris": (400, ["belgrade", "nis", "sofia", "philippopolis", "edirne", "constantinople"]),
    "the Via Egnatia": (350, ["durazzo", "ohrid", "monastir", "thessaloniki", "christoupolis", "komotini",
                              "constantinople"]),
}
MERCHANTS = {"venice": 1.6, "genoa": 1.6, "ragusa": 1.5}


class Trade:
    """Mixed into Campaign."""

    def _trade_key(self):
        return (self.date.year, self.date.month, len(self.wars),
                tuple(sorted(pid for pid, p in self.provinces.items() if p.siege)))

    def leg_open(self, a, b):
        pa, pb = self.provinces.get(a), self.provinces.get(b)
        if pa is None or pb is None or pa.siege or pb.siege:
            return False
        return not self.at_war(pa.controller, pb.controller)

    def route_state(self, name):
        """(share of the road open 0-1, ducats a month moving along it now)."""
        value, towns = ROUTES[name]
        legs = list(zip(towns, towns[1:]))
        open_ = sum(1 for a, b in legs if self.leg_open(a, b)) / len(legs)
        return open_, value * open_ * open_       # a road cut in two carries far less than half

    def trade_income(self, pid):
        """What a town earns from the roads through it this month."""
        cache = getattr(self, "_trade_cache", None)
        key = self._trade_key()
        if cache is None or cache[0] != key:
            cache = (key, {})
            for name, (value, towns) in ROUTES.items():
                _, flow = self.route_state(name)
                for town in towns:
                    if town in self.provinces:
                        cache[1][town] = cache[1].get(town, 0.0) + flow / len(towns)
            self._trade_cache = cache
        earned = cache[1].get(pid, 0.0)
        if earned:
            earned *= MERCHANTS.get(self.provinces[pid].controller, 1.0) * self.provinces[pid].prosperity
        return earned

    def routes_through(self, pid):
        return [name for name, (_, towns) in ROUTES.items() if pid in towns]
