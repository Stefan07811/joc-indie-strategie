"""Each realm's own ambitions in 1402, drawn from what it historically wanted, and rewarded when achieved.

Realms with no missions of their own get a few that fit their place: freedom from an overlord, walls for
the capital, the richest land of a hated neighbour.
"""

from .calendar import Date
from .history import Mission, alive, both, calm, free, gold, level, manpower, owns, prestige, subject_of

OTTOMANS = ("ott_rum", "ott_isa", "ott_meh")


def _m(realm, key, title, text, done, reward, reward_text, after=()):
    return Mission(f"{realm}.{key}", realm, title, text, done, reward, reward_text,
                   tuple(f"{realm}.{a}" for a in after))


def _ottoman_tributary(c, tag):
    return any(subject_of(c, t, tag) for t in OTTOMANS if alive(c, t))


def _ottoman_land(c):
    return sum(len(c.provinces_of(t)) for t in OTTOMANS + ("ottomans",) if t in c.realms)


def _reunited(c, tag):
    return owns(c, tag, "edirne", "bursa") and all(not alive(c, t) or t == tag for t in OTTOMANS)


MISSIONS = [
    # --- Wallachia: Mircea's Danube ---------------------------------------------------------------
    _m("wallachia", "dobruja", "Take Back the Dobruja",
       "Mircea held the Dobruja and Silistra before Bayezid took them. The Turks are broken: take them back.",
       lambda c, t: owns(c, t, "dobruja", "silistra"), both(prestige(15), gold(3000)), "15 prestige, 3,000 ducats"),
    _m("wallachia", "fords", "Hold the Danube Fords",
       "Whoever holds the fords holds the river. Wall Giurgiu and hold Brăila.",
       lambda c, t: owns(c, t, "giurgiu", "braila") and level(c, "giurgiu", "walls") >= 1,
       prestige(10), "10 prestige"),
    _m("wallachia", "court", "The Princely Court at Târgoviște",
       "A castle and a monastery worthy of the Basarabs.",
       lambda c, t: level(c, "targoviste", "castle") >= 2 and level(c, "targoviste", "church") >= 2,
       both(prestige(10), calm(1.0)), "10 prestige, less unrest everywhere"),
    _m("wallachia", "sultans", "Make and Unmake Sultans",
       "Let a son of Bayezid owe his throne, or his tribute, to Wallachia.",
       _ottoman_tributary, both(prestige(25), gold(5000)), "25 prestige, 5,000 ducats", after=("dobruja",)),
    _m("wallachia", "friend", "A Friend, Not a Master",
       "Keep the King of Hungary a friend, and never his vassal.",
       lambda c, t: alive(c, "hungary") and c.opinion(t, "hungary") >= 50 and free(c, t),
       gold(2500), "2,500 ducats"),
    # --- Moldavia ---------------------------------------------------------------------------------
    _m("moldavia", "ports", "The Ports of the Black Sea",
       "Cetatea Albă is ours; Chilia, at the mouth of the Danube, is in Genoese hands. The trade road from "
       "Lwów to the sea must be ours from end to end.",
       lambda c, t: owns(c, t, "cetatea_alba", "chilia"), both(prestige(15), gold(3000)),
       "15 prestige, 3,000 ducats"),
    _m("moldavia", "free", "Free of Poland",
       "Homage to the King of Poland keeps us safe today. Tomorrow we shall need no master.",
       lambda c, t: free(c, t) and c.date.year >= 1405, prestige(20), "20 prestige"),
    _m("moldavia", "metropolis", "A Metropolis for Suceava",
       "The Patriarch has recognised our Church. Let Suceava have a cathedral to match.",
       lambda c, t: level(c, "suceava", "church") >= 3, both(prestige(15), calm(1.5)),
       "15 prestige, less unrest everywhere"),
    _m("moldavia", "walls", "The Fortresses of the Siret",
       "Wall Suceava and Roman, and the Tatars and the Hungarians will think twice.",
       lambda c, t: level(c, "suceava", "walls") >= 1 and level(c, "roman", "walls") >= 1,
       manpower(3000), "3,000 men"),
    # --- Hungary ----------------------------------------------------------------------------------
    _m("hungary", "barons", "Master in His Own House",
       "The barons who imprisoned the King must learn who rules. Keep the realm quiet and the treasury full.",
       lambda c, t: c.realms[t].treasury >= 30000 and all(p.unrest < 2 for p in c.provinces_of(t)),
       prestige(20), "20 prestige"),
    _m("hungary", "belgrade", "The Key of Belgrade",
       "Belgrade is the gate of Hungary. Make it the strongest fortress on the Danube.",
       lambda c, t: owns(c, t, "belgrade") and level(c, "belgrade", "walls") >= 2, prestige(15), "15 prestige"),
    _m("hungary", "wallachia", "The Voivode's Homage",
       "Wallachia should hold its land from the Holy Crown, as its voivodes once did.",
       lambda c, t: subject_of(c, "wallachia", t), both(prestige(15), gold(5000)), "15 prestige, 5,000 ducats"),
    _m("hungary", "bosnia", "Bosnia Under the Holy Crown",
       "Bring the Bosnian king and his magnates to heel.",
       lambda c, t: subject_of(c, "bosnia", t) or owns(c, t, "bobovac"), prestige(15), "15 prestige"),
    _m("hungary", "dalmatia", "Dalmatia, Not Venice's",
       "Keep Zara and Spalato from the Venetians.",
       lambda c, t: owns(c, t, "zara", "spalato") and c.date.year >= 1410, prestige(10), "10 prestige"),
    # --- Serbia -----------------------------------------------------------------------------------
    _m("serbia", "lands", "Master of the Serbian Lands",
       "The Brankovići hold Kosovo and Prizren against us. Make them our vassals, or take their land.",
       lambda c, t: subject_of(c, "brankovic", t) or owns(c, t, "kosovo", "prizren"),
       both(prestige(20), manpower(3000)), "20 prestige, 3,000 men"),
    _m("serbia", "belgrade", "Belgrade, the White City",
       "The King of Hungary may grant us Belgrade. Hold it, and make it our capital.",
       lambda c, t: owns(c, t, "belgrade"), prestige(20), "20 prestige"),
    _m("serbia", "silver", "The Silver of Novo Brdo",
       "Deep shafts at Novo Brdo would make the Despot the richest prince in the Balkans.",
       lambda c, t: level(c, "novo_brdo", "mine") >= 2, gold(4000), "4,000 ducats"),
    _m("serbia", "free", "Free of the Turk",
       "We fought for Bayezid at Ankara. We owe his sons nothing.",
       lambda c, t: free(c, t), prestige(15), "15 prestige"),
    # --- the Ottomans -----------------------------------------------------------------------------
    _m("ott_rum", "rumelia", "Hold Rumelia",
       "Keep the European lands of our father whole: Edirne, Sofia, Thessaloniki or not, and Gallipoli.",
       lambda c, t: owns(c, t, "edirne", "sofia", "gallipoli", "philippopolis") and c.date.year >= 1406,
       prestige(15), "15 prestige"),
    _m("ott_rum", "reunite", "Reunite the House of Osman",
       "There can be only one Sultan. Hold Edirne and Bursa, and let no brother rule.",
       _reunited, both(prestige(50), gold(10000)), "50 prestige, 10,000 ducats"),
    _m("ott_rum", "serbia", "The Despot's Tribute",
       "The Despot of Serbia owes us men and silver.",
       lambda c, t: subject_of(c, "serbia", t), gold(5000), "5,000 ducats"),
    _m("ott_meh", "bursa", "Take Bursa",
       "Bursa, the city of our fathers' tombs, must be ours.",
       lambda c, t: owns(c, t, "bursa"), both(prestige(20), manpower(4000)), "20 prestige, 4,000 men"),
    _m("ott_meh", "reunite", "Reunite the House of Osman",
       "There can be only one Sultan. Hold Edirne and Bursa, and let no brother rule.",
       _reunited, both(prestige(50), gold(10000)), "50 prestige, 10,000 ducats", after=("bursa",)),
    _m("ott_meh", "karaman", "Avenge Ankara on Karaman",
       "The Karamanids rode with Timur. Make them pay tribute, or take Konya.",
       lambda c, t: subject_of(c, "karaman", t) or owns(c, t, "konya"), prestige(20), "20 prestige"),
    _m("ott_isa", "bursa", "Hold Bursa Against My Brothers",
       "Keep Bursa until the summer of 1405, and the beys will know who is Sultan.",
       lambda c, t: owns(c, t, "bursa") and c.date >= Date(1405, 6), prestige(25), "25 prestige"),
    _m("ott_isa", "reunite", "Reunite the House of Osman",
       "There can be only one Sultan. Hold Edirne and Bursa, and let no brother rule.",
       _reunited, both(prestige(50), gold(10000)), "50 prestige, 10,000 ducats"),
    # --- the Greeks ---------------------------------------------------------------------------------
    _m("byzantium", "thessaloniki", "Thessaloniki Returned",
       "The second city of the Empire must come home.",
       lambda c, t: owns(c, t, "thessaloniki"), prestige(20), "20 prestige"),
    _m("byzantium", "walls", "The Walls of Theodosius",
       "Repair the Land Walls: the City has stood a thousand years behind them.",
       lambda c, t: level(c, "constantinople", "walls") >= 2, prestige(15), "15 prestige"),
    _m("byzantium", "survive", "The Empire Endures",
       "Let the Empire of the Romans see the year 1460.",
       lambda c, t: c.date.year >= 1460, prestige(100), "100 prestige"),
    _m("morea", "corinth", "Corinth Bought Back",
       "Theodore sold Corinth to the Knights in his fear of Bayezid. Buy it back, or take it.",
       lambda c, t: owns(c, t, "corinth"), prestige(15), "15 prestige"),
    _m("morea", "peloponnese", "All of the Peloponnese",
       "The last Franks of Achaea hold Patras, Glarentza and Kalamata. End their principality.",
       lambda c, t: owns(c, t, "patras", "glarentza", "kalamata"), both(prestige(25), gold(3000)),
       "25 prestige, 3,000 ducats", after=("corinth",)),
    _m("trebizond", "silk", "The Silk Road's End",
       "Markets and guilds at Trebizond, and the caravans from Tabriz will pay for our walls.",
       lambda c, t: level(c, "trebizond", "market") >= 2 and level(c, "trebizond", "workshop") >= 1,
       gold(3000), "3,000 ducats"),
    _m("trebizond", "free", "No Man's Vassal",
       "We bowed to Timur. We need bow to no one.",
       lambda c, t: free(c, t), prestige(15), "15 prestige"),
    _m("theodoro", "port", "A Port of Our Own",
       "The Genoese hold every harbour of the coast. Build our own.",
       lambda c, t: level(c, "gothia", "harbour") >= 1 or owns(c, t, "caffa"), prestige(15), "15 prestige"),
    # --- the Latins ---------------------------------------------------------------------------------
    _m("venice", "albania", "The Albanian Coast",
       "Scutari, Durazzo and the harbours of Albania keep the Turk away from the Adriatic.",
       lambda c, t: owns(c, t, "scutari", "durazzo") and (owns(c, t, "valona") or owns(c, t, "antivari")),
       prestige(15), "15 prestige"),
    _m("venice", "dalmatia", "Dalmatia Bought",
       "Zara and the Dalmatian towns can be had, for money or by the sword.",
       lambda c, t: owns(c, t, "zara"), both(prestige(20), gold(5000)), "20 prestige, 5,000 ducats"),
    _m("venice", "arsenal", "The Arsenal",
       "The greatest shipyard in the world.",
       lambda c, t: level(c, "venice", "harbour") >= 3, gold(8000), "8,000 ducats"),
    _m("venice", "negroponte", "The Eye of the Aegean",
       "Wall Negroponte and Modon, the stations of our galleys.",
       lambda c, t: level(c, "negroponte", "walls") >= 1 and level(c, "modon", "walls") >= 1,
       prestige(10), "10 prestige"),
    _m("genoa", "famagusta", "Famagusta Held",
       "The Lusignans want Famagusta back. Wall it and keep it.",
       lambda c, t: owns(c, t, "famagusta") and level(c, "famagusta", "walls") >= 1, gold(3000), "3,000 ducats"),
    _m("genoa", "caffa", "The Walls of Caffa",
       "Caffa is the gate of the steppe trade. Make its walls the strongest on the Black Sea.",
       lambda c, t: level(c, "caffa", "walls") >= 2, prestige(15), "15 prestige"),
    _m("knights", "rhodes", "The Bulwark of Rhodes",
       "Rhodes must be impregnable.",
       lambda c, t: level(c, "rhodes", "walls") >= 2, prestige(20), "20 prestige"),
    _m("knights", "bodrum", "A Castle on the Mainland",
       "Smyrna is lost: build a new castle across from Kos, at Bodrum, in the land of Menteşe.",
       lambda c, t: owns(c, t, "milas"), prestige(20), "20 prestige"),
    _m("cyprus", "famagusta", "Famagusta Restored",
       "The Genoese took Famagusta from our fathers. Take it back.",
       lambda c, t: owns(c, t, "famagusta"), both(prestige(25), gold(3000)), "25 prestige, 3,000 ducats"),
    _m("naples", "hungary", "The Crown of Saint Stephen",
       "Ladislaus was crowned at Zara. Let the crown sit on his head in Buda, or let Hungary pay him tribute.",
       lambda c, t: subject_of(c, "hungary", t) or c.ruler("hungary") is c.ruler(t), prestige(40), "40 prestige"),
    _m("naples", "rome", "Master of Rome",
       "Ladislaus will hold Rome itself.",
       lambda c, t: owns(c, t, "rome"), prestige(20), "20 prestige"),
    _m("papal", "crusade", "Christendom United",
       "Let no Catholic prince be at war with another.",
       lambda c, t: not any(c.info[w.leader]["religion"] == "catholic" and c.info[w.target]["religion"] == "catholic"
                            for w in c.wars) and c.date.year >= 1405, prestige(20), "20 prestige"),
    _m("poland", "sea", "The Road to the Black Sea",
       "Keep Moldavia's homage and its ports open to the merchants of Lwów.",
       lambda c, t: subject_of(c, "moldavia", t) and c.date.year >= 1410, gold(5000), "5,000 ducats"),
    _m("lithuania", "sea", "From Sea to Sea",
       "Vytautas's lands reach the Black Sea at Khadjibey. Push the Tatars from the Dnieper's mouth.",
       lambda c, t: owns(c, t, "khadjibey", "lower_dnieper"), prestige(25), "25 prestige"),
    _m("lithuania", "vorskla", "Revenge for the Vorskla",
       "Edigu's Tatars crushed us on the Vorskla. Make the Horde pay tribute, or take its lands.",
       lambda c, t: subject_of(c, "horde", t) or owns(c, t, "zaporozhia", "poltava"), prestige(30), "30 prestige"),
    _m("bohemia", "peace", "Peace in Prague",
       "Let the kingdom be quiet: no province restless, the treasury full.",
       lambda c, t: c.date.year >= 1405 and all(p.unrest < 2 for p in c.provinces_of(t)) and
       c.realms[t].treasury >= 15000, prestige(15), "15 prestige"),
    _m("austria", "inherit", "The Habsburg Inheritance",
       "Albert has been named heir to Hungary. Let a Habsburg wear the crown of Saint Stephen.",
       lambda c, t: c.ruler("hungary") is c.ruler(t) or subject_of(c, "hungary", t), prestige(50), "50 prestige"),
    # --- the Bosnians and the Albanians -------------------------------------------------------------
    _m("bosnia", "magnates", "A King, Not a Puppet",
       "Hrvoje, Sandalj and Pavle rule their lands like kings. Bring all three to obey, or take their land.",
       lambda c, t: all(subject_of(c, m, t) or not alive(c, m) for m in ("hrvoje", "kosaca", "pavlovic")) and
       c.realms[t].prestige >= 20, prestige(25), "25 prestige"),
    _m("hrvoje", "split", "Duke of Split",
       "Ladislaus will make Hrvoje Duke of Split. Let him hold the Dalmatian coast.",
       lambda c, t: owns(c, t, "spalato"), prestige(25), "25 prestige"),
    _m("kosaca", "ragusa", "Lord of the Coast",
       "Ragusa's merchants pass through Sandalj's land. Let them pay him tribute.",
       lambda c, t: subject_of(c, "ragusa", t), gold(4000), "4,000 ducats"),
    _m("ragusa", "land", "Land for the Republic",
       "The Republic buys land from its neighbours when it can. Hold one province more.",
       lambda c, t: len(c.provinces_of(t)) >= 2, gold(4000), "4,000 ducats"),
    _m("zeta", "scutari", "Scutari Back",
       "Our father sold Scutari to Venice. It was a mistake.",
       lambda c, t: owns(c, t, "scutari"), both(prestige(20), manpower(1500)), "20 prestige, 1,500 men"),
    _m("kastrioti", "kruja", "Kruja",
       "The fortress of Kruja, on its rock, would be the heart of a free Albania.",
       lambda c, t: owns(c, t, "kruja"), prestige(25), "25 prestige"),
    _m("thopia", "hold", "Hold Kruja",
       "Our half-brother Niketa wants Kruja; the Turks want it more. Wall it.",
       lambda c, t: level(c, "kruja", "walls") >= 1, prestige(10), "10 prestige"),
    # --- Anatolia, the steppe, the Levant -------------------------------------------------------
    _m("karaman", "seljuk", "Heirs of the Seljuks",
       "Konya was the Seljuk Sultans' capital. Their land, to Ankara and Kütahya, is ours by right.",
       lambda c, t: owns(c, t, "ankara") or owns(c, t, "kutahya"), prestige(25), "25 prestige"),
    _m("karaman", "bursa", "Burn Bursa",
       "Take the Ottomans' old capital, even for a season.",
       lambda c, t: c.provinces["bursa"].controller == t, prestige(20), "20 prestige"),
    _m("candar", "sinop", "The Copper of Sinop",
       "A deep mine and a busy harbour at Sinop.",
       lambda c, t: level(c, "sinop", "harbour") >= 1 and level(c, "kastamonu", "market") >= 1, gold(2500),
       "2,500 ducats"),
    _m("horde", "tribute", "The Tribute of the Steppe",
       "The Crimean Goths and the Circassians paid tribute to the Horde. Let them pay again.",
       lambda c, t: subject_of(c, "theodoro", t) and subject_of(c, "circassia", t), gold(5000), "5,000 ducats"),
    _m("horde", "crimea", "All of the Crimea",
       "Take Caffa from the Genoese.",
       lambda c, t: owns(c, t, "caffa"), prestige(25), "25 prestige"),
    _m("mamluks", "aleppo", "Aleppo Rebuilt",
       "Timur burned Aleppo. Rebuild its markets and its walls.",
       lambda c, t: level(c, "aleppo", "market") >= 2 and level(c, "aleppo", "walls") >= 1, prestige(20),
       "20 prestige"),
    _m("mamluks", "cyprus", "The Lusignans Humbled",
       "The Cypriots raid our coasts. Make their king pay tribute.",
       lambda c, t: subject_of(c, "cyprus", t), gold(8000), "8,000 ducats"),
    _m("georgia", "rebuild", "Rise From the Ashes",
       "Timur came eight times. Rebuild the churches and the towns.",
       lambda c, t: level(c, "kutaisi", "church") >= 2 and all(p.prosperity >= 0.95 for p in c.provinces_of(t)),
       prestige(20), "20 prestige"),
]


def generic_missions(c, tag):
    """A few ambitions for any realm without missions of its own."""
    out = []
    cap = c.info[tag]["capital"]
    out.append(_m(tag, "walls", "Walls for the Capital", "A realm whose capital can be taken in a month is no "
                  "realm at all.", lambda c, t, cap=cap: level(c, cap, "walls") >= 1, prestige(10), "10 prestige"))
    out.append(_m(tag, "church", "A House of God", "Raise a great church in the capital.",
                  lambda c, t, cap=cap: level(c, cap, "church") >= 2, prestige(10), "10 prestige"))
    if c.overlord.get(tag):
        lord = c.overlord[tag][0]
        out.append(_m(tag, "free", "Free at Last", f"We answer to {c.name(lord)}. One day we shall not.",
                      lambda c, t: free(c, t), prestige(20), "20 prestige"))
    out.append(_m(tag, "grow", "A Greater Realm", "Hold two more provinces than in 1402.",
                  lambda c, t: len(c.provinces_of(t)) >= c.start_size.get(t, 1) + 2,
                  both(prestige(15), gold(2000)), "15 prestige, 2,000 ducats"))
    return out


def missions_of(c, tag):
    own = [m for m in MISSIONS if m.realm == tag]
    return own if own else generic_missions(c, tag)
