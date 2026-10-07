"""The campaign's rules as data: what goods are worth, what can be built, what troops can be raised.

Money is counted in ducats (the Venetian gold coin everyone in the region reckoned in), population in
thousands of people, time in months.
"""

from dataclasses import dataclass, field

# --- trade goods: ducats a month for a province of 10,000 people working it ----------------------------

GOOD_PRICE = {
    "grain": 15, "livestock": 17, "fish": 16, "timber": 15, "wine": 22, "olive_oil": 24, "wax": 26,
    "horses": 24, "furs": 30, "salt": 40, "iron": 34, "copper": 40, "cloth": 38, "cotton": 26, "silk": 50,
    "glass": 45, "sugar": 42, "alum": 55, "mastic": 60, "spices": 70, "silver": 140, "gold": 170,
}
MINED = {"silver", "gold", "iron", "copper", "salt", "alum"}
GOOD_NAMES = {"olive_oil": "Olive oil"}

# --- money ------------------------------------------------------------------------------------------

TAX_PER_THOUSAND = 4.5       # ducats a month from every thousand people, at full prosperity
COMMERCE_PER_THOUSAND = 25   # ducats a month from every thousand townsfolk
COASTAL_COMMERCE = 1.3       # sea trade
COURT_UPKEEP = {"empire": 500, "kingdom": 250, "duchy": 100, "county": 25}
COURT_SHARE = 0.10           # of the income: officials, the court, the church's due
FORT_UPKEEP = 30             # a month for each level of walls a realm has built
OCCUPIED_INCOME = 0.4        # what an occupier squeezes out of a province it holds in war
GROWTH_PER_YEAR = 0.004      # the population's natural growth at full prosperity
PROSPERITY_RECOVERY = 0.01   # a month, back towards 1 after a war has passed
LEVY_SHARE = 0.03            # the share of the people who can be called to arms
MANPOWER_RECOVERY = 1 / 60   # of the levy pool, a month (five years to recover from a disaster)


# --- buildings ----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class BuildingType:
    id: str
    names: tuple                 # the name of every level
    costs: tuple                 # ducats for every level
    months: tuple                # months to build every level
    effects: dict                # effect name -> amount per level
    needs: str = ""              # "coastal", "mine", "town", "horses" or "" (anywhere)
    about: str = ""

    @property
    def levels(self):
        return len(self.names)


BUILDINGS = {b.id: b for b in (
    BuildingType("fields", ("Ploughlands", "Watermills", "Rich Estates"), (300, 700, 1500), (6, 9, 12),
                 {"tax": 0.10, "growth": 0.002}, about="More land under the plough: taxes and growth."),
    BuildingType("market", ("Market", "Fair", "Staple Town"), (400, 1000, 2500), (6, 10, 15),
                 {"commerce": 0.35, "tax": 0.03}, needs="town", about="Merchants and their tolls."),
    BuildingType("workshop", ("Workshops", "Guild Hall", "Great Guilds"), (500, 1200, 2800), (8, 12, 16),
                 {"production": 0.25}, needs="town", about="Craftsmen working the province's goods."),
    BuildingType("mine", ("Mine", "Deep Shafts", "Mining Town"), (700, 1600, 3500), (8, 12, 18),
                 {"production": 0.40}, needs="mine", about="Saxon miners dig deeper for metal and salt."),
    BuildingType("harbour", ("Harbour", "Port", "Arsenal"), (500, 1300, 3000), (8, 12, 18),
                 {"commerce": 0.25, "production": 0.10}, needs="coastal", about="Ships, sea trade and fishing."),
    BuildingType("walls", ("Palisade", "Stone Walls", "Towers"), (600, 1500, 3500), (8, 14, 20),
                 {"fort": 1}, about="One more level of fortification against sieges."),
    BuildingType("castle", ("Keep", "Castle", "Citadel"), (500, 1300, 3000), (8, 12, 18),
                 {"recruit": 1, "levy": 0.15, "garrison": 200}, about="Raises better troops and a garrison."),
    BuildingType("stables", ("Stables", "Stud Farm", "Royal Stud"), (400, 1000, 2400), (6, 10, 14),
                 {"cavalry": 1}, needs="horses", about="Horses for the realm's horsemen."),
    BuildingType("church", ("Church", "Monastery", "Cathedral"), (300, 900, 2500), (6, 12, 24),
                 {"order": 1, "prestige": 0.05}, about="Faith and learning: order, and prestige for the realm."),
)}
MOSQUE_NAMES = ("Mosque", "Medrese", "Külliye")


def slots(city):
    """How many buildings a province can hold (towns hold more)."""
    return 3 + (city >= 5) + (city >= 15) + (city >= 40)


# --- troops -------------------------------------------------------------------------------------------

# The military tradition of each culture: which troops its lords raise.
TRADITION = {
    "hungarian": "latin", "croatian": "latin", "german": "latin", "czech": "latin", "slovak": "latin",
    "slovene": "latin", "polish": "latin", "italian": "latin",
    "romanian": "vlach", "ruthenian": "vlach",
    "serbian": "balkan", "bulgarian": "balkan", "bosnian": "balkan", "albanian": "balkan",
    "greek": "greek", "georgian": "greek", "armenian": "greek",
    "turkish": "ottoman",
    "tatar": "steppe", "circassian": "steppe",
    "arab": "levant", "kurdish": "levant",
}


@dataclass(frozen=True)
class UnitType:
    id: str
    name: str
    tradition: str
    kind: str                    # "horse", "foot" or "missile"
    men: int
    cost: int                    # ducats to raise
    upkeep: int                  # ducats a month
    melee: int
    missile: int
    defence: int
    morale: int
    march: int                   # km a month
    tier: int = 0                # castle level needed
    about: str = ""
    tags: tuple = field(default=())


def _u(*args, **kw):
    return UnitType(*args, **kw)


UNITS = {u.id: u for u in (
    # the Latin kingdoms: knights, men-at-arms, crossbows
    _u("knights", "Knights", "latin", "horse", 300, 1800, 600, 14, 0, 12, 12, 220, tier=1,
       about="Armoured lances: the best charge in Christendom.", tags=("shock",)),
    _u("light_horse", "Light Horse", "latin", "horse", 400, 700, 280, 7, 3, 5, 8, 300, about="Scouts and raiders."),
    _u("men_at_arms", "Men-at-Arms", "latin", "foot", 500, 1600, 600, 10, 0, 11, 11, 200, tier=1),
    _u("crossbowmen", "Crossbowmen", "latin", "missile", 500, 1100, 400, 4, 10, 6, 8, 200),
    _u("militia", "Town Militia", "latin", "foot", 600, 250, 90, 5, 0, 7, 6, 200, about="Burghers with pikes."),
    # Wallachia and Moldavia: boyars, light horse and the great host of the peasants
    _u("boyars", "Boyar Horse", "vlach", "horse", 300, 900, 270, 11, 2, 9, 11, 260, tier=1,
       about="The country's nobles and their retinues."),
    _u("calarasi", "Călărași", "vlach", "horse", 400, 450, 160, 7, 5, 5, 8, 330,
       about="Free horsemen: quick to strike, quick to vanish into the woods."),
    _u("vlach_archers", "Archers", "vlach", "missile", 500, 400, 150, 4, 8, 5, 7, 220),
    _u("great_host", "The Great Host", "vlach", "foot", 1000, 200, 100, 5, 1, 5, 6, 200,
       about="Every free man called to arms in the hour of need."),
    # the Serbian, Bulgarian, Bosnian and Albanian lords
    _u("vlastela", "Vlastela Horse", "balkan", "horse", 300, 1000, 300, 12, 0, 11, 11, 230, tier=1,
       about="Armoured noble horsemen in the western manner."),
    _u("stradioti", "Stradioti", "balkan", "horse", 400, 700, 240, 8, 3, 5, 9, 320,
       about="Albanian light horse with lance and sword."),
    _u("bowmen", "Bowmen", "balkan", "missile", 500, 450, 150, 4, 8, 5, 7, 210),
    _u("spearmen", "Spearmen", "balkan", "foot", 600, 300, 100, 6, 0, 8, 7, 210),
    # the Greek world
    _u("archontes", "Archontes", "greek", "horse", 300, 1100, 350, 12, 2, 11, 10, 230, tier=1),
    _u("stratiotai", "Stratiotai", "greek", "horse", 400, 700, 240, 7, 4, 5, 8, 300),
    _u("greek_archers", "Archers", "greek", "missile", 500, 500, 170, 4, 8, 5, 7, 200),
    _u("militia_greek", "Militia", "greek", "foot", 600, 250, 90, 5, 1, 7, 6, 200),
    # the Ottomans
    _u("sipahis", "Sipahis", "ottoman", "horse", 400, 800, 200, 10, 5, 8, 10, 280,
       about="Timar-holding horsemen, bow and lance."),
    _u("akinjis", "Akıncıs", "ottoman", "horse", 500, 250, 60, 7, 5, 4, 8, 380,
       about="Raiders who ride ahead of the army and live off plunder."),
    _u("azaps", "Azaps", "ottoman", "missile", 600, 500, 180, 5, 7, 5, 7, 220),
    _u("janissaries", "Janissaries", "ottoman", "foot", 300, 2400, 700, 12, 8, 11, 14, 220, tier=2,
       about="The sultan's slave infantry: few, and the best foot of the age.", tags=("elite",)),
    # the steppe
    _u("horse_archers", "Horse Archers", "steppe", "horse", 500, 400, 120, 6, 9, 4, 8, 400,
       about="The Horde's riders: arrows from the saddle, never caught."),
    _u("mirza_horse", "Mirza's Guard", "steppe", "horse", 300, 1000, 300, 11, 6, 9, 11, 330, tier=1),
    # Syria and the Kurdish mountains
    _u("mamluks", "Mamluks", "levant", "horse", 300, 2800, 800, 14, 9, 12, 13, 260, tier=2,
       about="Slave-soldiers trained from boyhood: the finest horse archers of Islam.", tags=("elite",)),
    _u("kurdish_horse", "Kurdish Horse", "levant", "horse", 400, 650, 200, 8, 4, 6, 9, 300),
    _u("levant_foot", "Foot Archers", "levant", "missile", 500, 500, 170, 4, 8, 5, 7, 210),
)}


def units_for(culture):
    """The troops a lord of this culture can raise."""
    tradition = TRADITION.get(culture, "latin")
    return [u for u in UNITS.values() if u.tradition == tradition]
