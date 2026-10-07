"""The realms of the map as they stood in September 1402, two months after Ankara.

Run it to write crowns/data/realms.json (the colours and short names come from history_1402.py):

    python tools/realms_1402.py

Every realm: its full name, government, the ruler's title, its weight (empire, kingdom, duchy, county),
its capital, the ruler, heir and spouse, its overlord, where it stood and what it wanted, and what
history had in store for it. Where the sources disagree or are thin, the entry says so in `uncertain`.

Sources, besides the general histories (Fine, The Late Medieval Balkans; Imber, The Ottoman Empire
1300-1481; Nicol, The Last Centuries of Byzantium): the Wikipedia articles on the realms and rulers
named below, among them
https://en.wikipedia.org/wiki/Ottoman_Interregnum, https://en.wikipedia.org/wiki/Battle_of_Ankara,
https://en.wikipedia.org/wiki/Principality_of_Theodoro, https://en.wikipedia.org/wiki/Pedro_de_San_Superano,
https://en.wikipedia.org/wiki/Niketa_Thopia, https://en.wikipedia.org/wiki/Dukagjini_family,
https://en.wikipedia.org/wiki/Theodor_Corona_Musachi, https://en.wikipedia.org/wiki/Maurice_Spata,
https://en.wikipedia.org/wiki/Nikola_IV_Frankopan, https://en.wikipedia.org/wiki/Mehmed_II_of_Karaman,
https://en.wikipedia.org/wiki/Beylik_of_Teke, https://en.wikipedia.org/wiki/Junayd_of_Aydın,
https://en.wikipedia.org/wiki/Ahmed_of_Ramadan, https://en.wikipedia.org/wiki/Mehmed_of_Dulkadir,
https://en.wikipedia.org/wiki/Hamidids (Hamid's land was shared between the Ottomans and Karaman
after Ankara, so Isparta starts Karamanid).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from history_1402 import PROVINCES, REALM_COLORS, REALM_NAMES  # noqa: E402


def person(name, born, dynasty=None, approximate=False, reign=None, relation=None):
    p = {"name": name, "born": born}
    if dynasty:
        p["dynasty"] = dynasty
    if approximate:
        p["approximate"] = True
    if reign is not None:
        p["reign_start"] = reign
    if relation:
        p["relation"] = relation
    return p


def R(tag, name, adjective, government, title, rank, capital, religion, culture, ruler, heir=None, spouse=None,
      overlord=None, situation="", notable=(), uncertain=""):
    out = {"tag": tag, "name": name, "adjective": adjective, "government": government, "title": title,
           "rank": rank, "capital": capital, "religion": religion, "culture": culture, "ruler": ruler,
           "heir": heir, "spouse": spouse,
           "overlord": {"tag": overlord[0], "kind": overlord[1]} if overlord else None,
           "situation": situation, "notable": [{"year": y, "event": e} for y, e in notable]}
    if uncertain:
        out["uncertain"] = uncertain
    return out


REALMS = [
    # --- the Danube and the Carpathians ---------------------------------------------------------------
    R("wallachia", "Principality of Wallachia", "Wallachian", "monarchy", "Voivode", "duchy", "targoviste",
      "orthodox", "romanian",
      person("Mircea the Elder", 1355, "Basarab", approximate=True, reign=1386),
      heir=person("Mihail", 1385, approximate=True, relation="son"),
      situation="Mircea held the Danube against Bayezid at Rovine and survived him. With the Ottomans broken "
                "at Ankara he means to take back the Dobruja and the Danube fords, and to make and unmake "
                "sultans in the coming civil war, while keeping Hungary a friend and not a master.",
      notable=[(1404, "Mircea retakes the Dobruja and Silistra"),
               (1409, "Mircea backs Musa Çelebi for the Ottoman throne"),
               (1418, "Mircea dies; the long feud of the Dănești and the Drăculești begins"),
               (1456, "Vlad III, the Impaler, takes the throne")],
      uncertain="Wallachia's standing with the Ottomans in 1402 is debated: Mircea had paid tribute after "
                "1395 but stopped after Ankara. He also held Făgăraș and Amlaș as Hungarian fiefs."),
    R("moldavia", "Principality of Moldavia", "Moldavian", "monarchy", "Voivode", "duchy", "suceava", "orthodox",
      "romanian",
      person("Alexander the Good", 1375, "Mușat", approximate=True, reign=1400),
      spouse="Margareta Losonczy", overlord=("poland", "vassal"),
      situation="Alexander swore homage to Władysław Jagiełło at Suceava in March 1402. Moldavia's wealth is "
                "the trade road from Lwów to Cetatea Albă and Chilia; its church was just recognised by "
                "Constantinople. Hungary and Poland both want it as their march against the steppe.",
      notable=[(1402, "Homage to the King of Poland at Suceava"),
               (1410, "Moldavian troops fight for Poland at Grunwald"),
               (1432, "Alexander dies; years of war between his sons follow"),
               (1457, "Stephen the Great takes the throne")],
      uncertain="Alexander's year of birth is not known."),
    R("hungary", "Kingdom of Hungary", "Hungarian", "monarchy", "King", "kingdom", "buda", "catholic", "hungarian",
      person("Sigismund of Luxembourg", 1368, "Luxembourg", reign=1387),
      heir=person("Albert of Austria", 1377, "Habsburg", relation="designated heir (1402)"),
      situation="Sigismund was held prisoner by his own barons in 1401 and many of them now call Ladislaus of "
                "Naples to the throne. He must win back his kingdom, then turn to the Ottoman danger he "
                "failed to stop at Nicopolis, and to Dalmatia, which Venice covets.",
      notable=[(1403, "Ladislaus of Naples is crowned at Zara; the rebel barons are crushed"),
               (1408, "Sigismund founds the Order of the Dragon"),
               (1410, "Sigismund is elected King of the Romans"),
               (1456, "John Hunyadi breaks the Ottoman siege of Belgrade")],
      uncertain="In 1402 Sigismund named Albert IV of Austria his heir; Albert died in 1404 and the pact lapsed."),
    R("frankopan", "County of Krk, Senj and Modruš", "Frankopan", "monarchy", "Count", "county", "modrus",
      "catholic", "croatian",
      person("Nikola IV Frankopan", 1360, "Frankopan", approximate=True, reign=1393),
      heir=person("Ivan VI Frankopan", 1395, approximate=True, relation="son"), overlord=("hungary", "vassal"),
      situation="The Frankopans are the greatest lords of the Croatian coast, from Krk to Modruš. Nikola "
                "weighs Sigismund against Ladislaus of Naples and means to come out of the civil war richer.",
      notable=[(1426, "Nikola becomes Ban of Croatia and Dalmatia"),
               (1430, "Nikola marries his daughter to the Despot of Serbia's heir"),
               (1449, "The Frankopan lands are divided among Nikola's sons")]),
    R("ragusa", "Republic of Ragusa", "Ragusan", "republic", "Rector", "county", "ragusa", "catholic", "croatian",
      person("The Rector and Great Council", None, reign=1358),
      overlord=("hungary", "tributary"),
      situation="Ragusa lives by the caravans to the Serbian and Bosnian silver mines and by the sea. It pays "
                "its tribute to the King of Hungary, buys land from its neighbours when it can, and stays at "
                "peace with everyone.",
      notable=[(1419, "Ragusa buys Konavle from Sandalj Hranić"),
               (1458, "Ragusa begins to pay tribute to the Ottoman sultan")],
      uncertain="The Rector served for one month at a time: the 'ruler' is the republic itself."),
    # --- Central Europe -------------------------------------------------------------------------------
    R("austria", "Duchy of Austria", "Austrian", "monarchy", "Duke", "duchy", "vienna", "catholic", "german",
      person("Albert IV", 1377, "Habsburg", reign=1395),
      heir=person("Albert V", 1397, "Habsburg", relation="son"), spouse="Joanna Sophia of Bavaria",
      situation="The Habsburg lands are split between the Albertine line at Vienna and the Leopoldine dukes in "
                "Styria, Carinthia and Carniola. Albert IV has just been named heir to Hungary by Sigismund.",
      notable=[(1404, "Albert IV dies; his son Albert V succeeds as a child"),
               (1438, "Albert V is crowned King of Hungary and Bohemia"),
               (1453, "Austria becomes an archduchy")],
      uncertain="Duke William of the Leopoldine line ruled Inner Austria (Graz, Carinthia, Carniola, Trieste) in "
                "his own right; the game folds his lands into one realm."),
    R("celje", "County of Celje", "Celjan", "monarchy", "Count", "county", "celje", "catholic", "slovene",
      person("Hermann II of Celje", 1365, "Celje", approximate=True, reign=1385),
      heir=person("Frederick II of Celje", 1379, approximate=True, relation="son"), spouse="Anna of Schaunberg",
      overlord=("austria", "vassal"),
      situation="Hermann saved Sigismund's life at Nicopolis and is his closest friend. The Counts of Celje "
                "rise through marriages: Hermann's cousin Anna has just wed the King of Poland, his daughter "
                "Barbara will marry Sigismund.",
      notable=[(1405, "Barbara of Celje marries Sigismund"), (1436, "The counts are made princes of the Empire"),
               (1456, "Ulrich II of Celje is murdered at Belgrade and the house dies out")],
      uncertain="Celje's lands lay in Styria under the Habsburgs, but its counts acted as Sigismund's men."),
    R("aquileia", "Patriarchate of Aquileia", "Friulian", "theocracy", "Patriarch", "county", "friuli",
      "catholic", "italian",
      person("Antonio Panciera", 1350, approximate=True, reign=1402),
      situation="The patriarchs rule Friuli as princes of the Empire, squeezed between Venice and the Counts "
                "of Gorizia. Antonio Panciera has just been named patriarch.",
      notable=[(1411, "Panciera is deposed; Friuli is fought over by Sigismund and Venice"),
               (1420, "Venice conquers Friuli and ends the patriarchs' rule")]),
    R("salzburg", "Prince-Archbishopric of Salzburg", "Salzburger", "theocracy", "Archbishop", "county",
      "salzburg", "catholic", "german",
      person("Gregor Schenk von Osterwitz", 1350, approximate=True, reign=1396),
      situation="The archbishops grow rich on the salt of Hallein and keep their see free of the Bavarian "
                "and Austrian dukes.",
      notable=[(1403, "Eberhard III von Neuhaus becomes archbishop")]),
    R("bavaria", "Duchy of Bavaria-Landshut", "Bavarian", "monarchy", "Duke", "duchy", "landshut", "catholic",
      "german", person("Henry XVI the Rich", 1386, "Wittelsbach", reign=1393),
      situation="Young Henry is the richest of the Wittelsbach dukes and quarrels with his cousins of Ingolstadt.",
      notable=[(1422, "Henry defeats Ingolstadt at Alling"), (1450, "Henry dies; Louis IX the Rich succeeds")]),
    R("bohemia", "Kingdom of Bohemia", "Bohemian", "monarchy", "King", "kingdom", "prague", "catholic", "czech",
      person("Wenceslaus IV", 1361, "Luxembourg", reign=1378),
      heir=person("Sigismund of Luxembourg", 1368, relation="brother"), spouse="Sophia of Bavaria",
      situation="Deposed as King of the Romans in 1400, Wenceslaus was seized in March 1402 by his brother "
                "Sigismund and is held prisoner in Vienna. Prague is restless, and Jan Hus is preaching.",
      notable=[(1403, "Wenceslaus escapes captivity and returns to Prague"), (1415, "Jan Hus is burned at Constance"),
               (1419, "The defenestration of Prague: the Hussite wars begin"),
               (1458, "George of Poděbrady is elected king")]),
    R("moravia", "Margraviate of Moravia", "Moravian", "monarchy", "Margrave", "duchy", "brno", "catholic", "czech",
      person("Jobst of Moravia", 1351, "Luxembourg", reign=1375),
      heir=person("Prokop of Moravia", 1355, approximate=True, relation="brother"), overlord=("bohemia", "vassal"),
      situation="Jobst is the shrewdest of the Luxembourgs and a creditor of half Europe; his brother and "
                "co-margrave Prokop is Sigismund's prisoner.",
      notable=[(1405, "Prokop dies in Sigismund's prison"), (1410, "Jobst is elected King of the Romans"),
               (1411, "Jobst dies; Moravia passes to Wenceslaus")]),
    R("poland", "Kingdom of Poland", "Polish", "monarchy", "King", "kingdom", "krakow", "catholic", "polish",
      person("Władysław II Jagiełło", 1362, "Jagiellon", approximate=True, reign=1386), spouse="Anna of Celje",
      situation="Widowed of Queen Jadwiga, Jagiełło married Anna of Celje in January 1402 to keep his crown. "
                "His great enemy is the Teutonic Order; to the south he collects the homage of Moldavia.",
      notable=[(1410, "Poland and Lithuania crush the Teutonic Order at Grunwald"),
               (1413, "The Union of Horodło"), (1444, "Władysław III falls at Varna"),
               (1454, "The Thirteen Years' War against the Order begins")]),
    R("lithuania", "Grand Duchy of Lithuania", "Lithuanian", "monarchy", "Grand Duke", "kingdom", "lutsk",
      "catholic", "lithuanian",
      person("Vytautas the Great", 1350, "Gediminid", approximate=True, reign=1392), spouse="Anna",
      overlord=("poland", "union"),
      situation="Vytautas rules the steppe frontier to the Black Sea, but his crusade against the Tatars ended "
                "in disaster at the Vorskla in 1399. He bargains with Poland for his crown and with the "
                "Horde's khans for the steppe.",
      notable=[(1410, "Vytautas leads the Lithuanians at Grunwald"), (1429, "The Congress of Lutsk"),
               (1430, "Vytautas dies before he can be crowned king")],
      uncertain="Vilnius lies off the map; Lutsk, one of his residences, stands in as the capital."),
    # --- the steppe and the Black Sea ---------------------------------------------------------------
    R("horde", "Golden Horde", "Tatar", "tribal", "Khan", "empire", "solkhat", "sunni", "tatar",
      person("Shadi Beg", 1380, "Jochid", approximate=True, reign=1399),
      situation="The khans are puppets of the beklerbek Edigu, who crushed Vytautas at the Vorskla. The Horde "
                "still claims tribute from Moscow and the Lithuanian lands, but Timur's wars have broken its "
                "cities and its trade.",
      notable=[(1407, "Shadi Beg is overthrown"), (1408, "Edigu besieges Moscow"),
               (1441, "Hacı Giray founds the Khanate of Crimea")],
      uncertain="Edigu, not the khan, held power; he is the Horde's real master in 1402."),
    R("theodoro", "Principality of Theodoro", "Gothic", "monarchy", "Prince", "county", "gothia", "orthodox",
      "greek",
      person("Alexios I of Theodoro", 1375, "Gabras", approximate=True, reign=1402),
      situation="A small Orthodox principality in the Crimean mountains, heir of the Byzantine Gothia. Its "
                "princes compete with the Genoese of Caffa for the southern coast and want a port of their own.",
      notable=[(1427, "Alexios builds the harbour fortress of Kalamita"),
               (1433, "War with Genoa over Cembalo"),
               (1475, "The Ottomans take Mangup and end the principality")],
      uncertain="Alexios's predecessor Stephen left for Moscow either in 1391 or in 1402."),
    R("genoa", "Genoese Gazaria and the Levant", "Genoese", "republic", "Governor", "duchy", "caffa", "catholic",
      "italian",
      person("Jean Le Maingre, Boucicaut", 1366, reign=1401),
      situation="Genoa is under the lordship of the King of France, governed by Marshal Boucicaut. Its colonies "
                "- Caffa, Chios, Famagusta, Chilia, Amasra - live from the Black Sea grain and slave trade and "
                "are Venice's bitter rivals.",
      notable=[(1403, "Boucicaut raids the Levant and is beaten by Venice at Modon"),
               (1409, "Genoa throws off French rule"), (1475, "The Ottomans take Caffa")],
      uncertain="The city of Genoa lies off the map: the realm is its eastern colonies, seated at Caffa."),
    R("circassia", "Circassia", "Circassian", "tribal", "Prince", "duchy", "kabarda", "orthodox", "circassian",
      person("Inal", 1380, approximate=True, reign=1400),
      situation="The Circassian princes rule the Kuban and the Kabarda valleys, raid the steppe and sell "
                "slaves and horses through the Genoese ports.",
      notable=[(1427, "Inal unites much of Circassia, by tradition")],
      uncertain="Inal is known mostly from tradition and his dates are disputed; the Circassians' faith "
                "mixed old Christianity and their own gods."),
    # --- Italy ----------------------------------------------------------------------------------------
    R("venice", "Republic of Venice", "Venetian", "republic", "Doge", "kingdom", "venice", "catholic", "italian",
      person("Michele Steno", 1331, reign=1400),
      situation="Venice holds the sea road to the Levant: Crete, Negroponte, Modon and Coron, Corfu, Durazzo "
                "and Scutari. With the Ottomans broken it wants Dalmatia back from Hungary, the Terraferma "
                "from the Carrara of Padua, and safe trade with whoever wins in Edirne.",
      notable=[(1405, "Venice takes Padua, Vicenza and Verona"),
               (1409, "Venice buys Zara and Dalmatia from Ladislaus of Naples"),
               (1423, "Venice takes Thessaloniki from the Byzantines"), (1454, "The Peace of Lodi")]),
    R("papal", "Papal States", "Papal", "theocracy", "Pope", "kingdom", "rome", "catholic", "italian",
      person("Boniface IX", 1350, "Tomacelli", approximate=True, reign=1389),
      situation="The Church is split between popes in Rome and Avignon. Boniface rebuilds his authority in "
                "Rome and the Papal States with the help of Ladislaus of Naples.",
      notable=[(1404, "Boniface IX dies"), (1417, "The Council of Constance ends the Schism"),
               (1459, "Pius II calls a crusade at Mantua")]),
    R("naples", "Kingdom of Naples", "Neapolitan", "monarchy", "King", "kingdom", "naples", "catholic", "italian",
      person("Ladislaus", 1377, "Anjou-Durazzo", reign=1386),
      heir=person("Joanna", 1373, relation="sister"),
      situation="Ladislaus has won back his kingdom from the Angevins of Provence and now claims Hungary, "
                "where Sigismund's barons call him in. He dreams of ruling all of Italy.",
      notable=[(1403, "Ladislaus is crowned King of Hungary at Zara"), (1408, "Ladislaus occupies Rome"),
               (1414, "Ladislaus dies; Joanna II succeeds"), (1442, "Alfonso of Aragon conquers Naples")]),
    R("sicily", "Kingdom of Sicily", "Sicilian", "monarchy", "King", "kingdom", "palermo", "catholic", "italian",
      person("Martin I", 1376, "Barcelona", reign=1392),
      heir=person("Martin of Aragon", 1356, relation="father"), spouse="Blanche of Navarre",
      overlord=None,
      situation="Martin the Younger has subdued the Sicilian barons with Aragonese help and just married "
                "Blanche of Navarre. Sicily is bound ever closer to the crown of Aragon.",
      notable=[(1409, "Martin I wins at Sanluri in Sardinia and dies of fever"),
               (1412, "Sicily passes to the Trastámara kings of Aragon")]),
    # --- the Ottomans and the Greeks ------------------------------------------------------------------
    R("ott_rum", "Ottoman Rumelia", "Ottoman", "monarchy", "Emir", "kingdom", "edirne", "sunni", "turkish",
      person("Süleyman Çelebi", 1377, "Osman", approximate=True, reign=1402),
      heir=person("Orhan", 1395, approximate=True, relation="son"),
      situation="Bayezid's eldest son escaped from Ankara and holds the European half of the empire from "
                "Edirne. He buys peace from the Christians to fight his brothers in Anatolia.",
      notable=[(1403, "The Treaty of Gallipoli: Thessaloniki and the coast are given back to Byzantium"),
               (1411, "Süleyman is overthrown and killed by his brother Musa"),
               (1413, "Mehmed defeats Musa at Çamurlu and reunites the empire"),
               (1453, "Mehmed II takes Constantinople")]),
    R("byzantium", "Byzantine Empire", "Byzantine", "monarchy", "Emperor", "empire", "constantinople",
      "orthodox", "greek",
      person("Manuel II Palaiologos", 1350, "Palaiologos", reign=1391),
      heir=person("John VIII Palaiologos", 1392, relation="son"), spouse="Helena Dragaš",
      situation="Ankara saved the City from Bayezid's siege. Manuel is still in the West begging for help; his "
                "nephew John VII rules Constantinople and will win back Thessaloniki and the Black Sea coast "
                "from Süleyman.",
      notable=[(1403, "Manuel returns; the Treaty of Gallipoli restores Thessaloniki"),
               (1422, "Murad II besieges Constantinople"), (1439, "The Union of the Churches at Florence"),
               (1453, "Constantinople falls to Mehmed II")],
      uncertain="Manuel II was in the West until 1403; John VII governed the City in his absence."),
    R("morea", "Despotate of the Morea", "Moreot", "monarchy", "Despot", "duchy", "mystras", "orthodox", "greek",
      person("Theodore I Palaiologos", 1355, "Palaiologos", approximate=True, reign=1383),
      heir=person("Theodore II Palaiologos", 1396, relation="nephew"), spouse="Bartolomea Acciaioli",
      overlord=("byzantium", "vassal"),
      situation="Theodore sold Corinth to the Knights of Rhodes in his fear of Bayezid and now wants it back. "
                "The Latin principality of Achaea and the Navarrese are his rivals for the peninsula.",
      notable=[(1404, "Corinth is bought back from the Knights"), (1407, "Theodore I dies"),
               (1415, "The Hexamilion wall is built across the Isthmus"),
               (1460, "Mehmed II conquers the Morea")]),
    R("achaea", "Principality of Achaea", "Achaean", "monarchy", "Prince", "duchy", "glarentza", "catholic",
      "italian",
      person("Pedro de San Superano", 1340, "San Superano", approximate=True, reign=1396),
      spouse="Maria II Zaccaria",
      situation="The last Frankish principality of the Morea is held by the captains of the Navarrese Company. "
                "It is squeezed between the Despot of Mystras and Venice's ports.",
      notable=[(1402, "Pedro dies in November; his widow Maria Zaccaria rules as regent"),
               (1404, "Centurione II Zaccaria becomes prince"),
               (1430, "The Palaiologoi conquer the last of Achaea")]),
    R("athens", "Duchy of Athens", "Athenian", "monarchy", "Lord", "county", "thebes", "catholic", "italian",
      person("Antonio I Acciaioli", 1370, "Acciaioli", approximate=True, reign=1394),
      overlord=("ott_rum", "tributary"),
      situation="The Florentine bastard son of Nerio Acciaioli holds Thebes and is besieging the Venetians "
                "on the Acropolis of Athens, which his father had left to the Republic.",
      notable=[(1403, "Antonio takes the Acropolis and Athens from Venice"),
               (1435, "Antonio dies"), (1456, "The Ottomans take Athens")]),
    R("ioannina", "Despotate of Epirus", "Epirote", "monarchy", "Despot", "county", "ioannina", "orthodox",
      "italian",
      person("Esau de' Buondelmonti", 1350, "Buondelmonti", approximate=True, reign=1385),
      heir=person("Giorgio de' Buondelmonti", 1400, approximate=True, relation="son"),
      spouse="Jevdokija Balšić", overlord=("ott_rum", "tributary"),
      situation="A Florentine despot of Ioannina among Albanian clans. Esau holds on with Ottoman help "
                "against the Spata of Arta and the Zenebishi.",
      notable=[(1411, "Esau dies; Carlo Tocco takes Ioannina"), (1430, "Ioannina submits to the Ottomans")]),
    R("spata", "Despotate of Arta", "Artan", "monarchy", "Despot", "county", "arta", "orthodox", "albanian",
      person("Muriq Shpata", 1360, "Shpata", approximate=True, reign=1400),
      heir=person("Yaqub Shpata", 1365, approximate=True, relation="brother"),
      situation="The Albanian lords of Arta live by war with Ioannina and Carlo Tocco.",
      notable=[(1411, "Muriq and Zenebishi invade Epirus"), (1416, "Carlo Tocco takes Arta")],
      uncertain="Some sources date Muriq's rule from 1403."),
    R("tocco", "County Palatine of Cephalonia and Zakynthos", "Tocco", "monarchy", "Count", "county",
      "cephalonia", "catholic", "italian",
      person("Carlo I Tocco", 1372, "Tocco", approximate=True, reign=1376),
      heir=person("Leonardo II Tocco", 1376, approximate=True, relation="brother"),
      spouse="Francesca Acciaioli", overlord=("naples", "vassal"),
      situation="The Neapolitan lords of the Ionian islands look across the strait to Epirus, its Albanian "
                "despots and its towns.",
      notable=[(1411, "Carlo takes Ioannina"), (1416, "Carlo takes Arta"),
               (1430, "Ioannina falls to the Ottomans")]),
    R("knights", "Knights Hospitaller", "Hospitaller", "order", "Grand Master", "duchy", "rhodes", "catholic",
      "french",
      person("Philibert de Naillac", 1350, approximate=True, reign=1396),
      situation="The Knights of Rhodes hold the castle of Smyrna and, since 1400, Corinth. Timur's armies are "
                "near Smyrna; Corinth must be returned to the Despot.",
      notable=[(1402, "Timur takes Smyrna from the Knights in December"),
               (1404, "The Knights begin the castle of Bodrum"), (1444, "The Mamluks besiege Rhodes")]),
    R("lesbos", "Lordship of Lesbos", "Gattilusi", "monarchy", "Lord", "county", "lesbos", "catholic", "italian",
      person("Francesco II Gattilusio", 1365, "Gattilusi", approximate=True, reign=1384),
      heir=person("Jacopo Gattilusio", 1390, approximate=True, relation="son"), spouse="Valentina Doria",
      overlord=("byzantium", "vassal"),
      situation="Genoese lords married into the imperial house, holding Lesbos and Ainos as vassals of the "
                "emperor and living from the alum and grain trade.",
      notable=[(1404, "Francesco II dies"), (1462, "Mehmed II takes Mytilene")]),
    R("naxos", "Duchy of the Archipelago", "Naxiot", "monarchy", "Duke", "county", "naxos", "catholic", "italian",
      person("Giacomo I Crispo", 1360, "Crispo", approximate=True, reign=1397),
      overlord=("venice", "vassal"),
      situation="A Latin duchy of the Cyclades under Venice's protection, plagued by Turkish corsairs.",
      notable=[(1418, "Giacomo I dies"), (1537, "The duchy becomes an Ottoman tributary")]),
    R("cyprus", "Kingdom of Cyprus", "Cypriot", "monarchy", "King", "kingdom", "nicosia", "catholic", "french",
      person("Janus", 1375, "Lusignan", reign=1398), spouse="Anglesia Visconti",
      situation="The Lusignan kings want Famagusta back from the Genoese and fear the Mamluks, whose coasts "
                "their ships raid.",
      notable=[(1426, "The Mamluks invade; Janus is captured at Khirokitia"),
               (1427, "Cyprus becomes a Mamluk tributary"), (1489, "Venice takes Cyprus")]),
    # --- Serbia and Bosnia --------------------------------------------------------------------------
    R("serbia", "Despotate of Serbia", "Serbian", "monarchy", "Despot", "duchy", "krusevac", "orthodox", "serbian",
      person("Stefan Lazarević", 1377, "Lazarević", reign=1389),
      heir=person("Vuk Lazarević", 1380, approximate=True, relation="brother"),
      overlord=("ott_rum", "tributary"),
      situation="Stefan fought for Bayezid at Ankara and came home through Constantinople with the title of "
                "Despot. He wants to be free of the Ottomans and master of the Serbian lands, and the "
                "Brankovićs stand in his way.",
      notable=[(1402, "Stefan defeats the Brankovićs and the Ottomans at Tripolje (November)"),
               (1403, "Stefan becomes Sigismund's vassal and receives Belgrade"),
               (1427, "Stefan dies; Đurađ Branković succeeds"), (1459, "The Ottomans take Smederevo")]),
    R("brankovic", "Lands of the Brankovići", "Branković", "monarchy", "Lord", "county", "kosovo", "orthodox",
      "serbian",
      person("Đurađ Branković", 1377, "Branković", approximate=True, reign=1396),
      heir=person("Grgur Branković", 1375, approximate=True, relation="brother"),
      overlord=("ott_rum", "vassal"),
      situation="The sons of Vuk Branković hold Kosovo, Peć and Prizren as Ottoman vassals and refuse the "
                "Despot's rule; Đurađ was briefly Stefan's prisoner after Ankara.",
      notable=[(1402, "The Brankovićs lose to Stefan at Tripolje"),
               (1412, "Đurađ reconciles with Stefan, his uncle"), (1427, "Đurađ becomes Despot of Serbia")]),
    R("bosnia", "Kingdom of Bosnia", "Bosnian", "monarchy", "King", "kingdom", "bobovac", "bosnian_church",
      "bosnian",
      person("Stephen Ostoja", 1360, "Kotromanić", approximate=True, reign=1398),
      situation="Ostoja reigns at the pleasure of the great magnates, Hrvoje above all. He wavers between "
                "Sigismund and Ladislaus of Naples.",
      notable=[(1404, "The magnates depose Ostoja for Tvrtko II"), (1409, "Ostoja returns to the throne"),
               (1463, "The Ottomans conquer Bosnia")]),
    R("hrvoje", "Lands of Hrvoje Vukčić", "Hrvatinić", "monarchy", "Grand Duke", "duchy", "jajce",
      "bosnian_church", "bosnian",
      person("Hrvoje Vukčić Hrvatinić", 1350, "Hrvatinić", approximate=True, reign=1380),
      spouse="Jelena Nelipčić", overlord=("bosnia", "vassal"),
      situation="The mightiest man in Bosnia makes and unmakes kings. He backs Ladislaus of Naples, who will "
                "make him Duke of Split.",
      notable=[(1403, "Ladislaus makes Hrvoje Duke of Split"), (1409, "Hrvoje goes over to Sigismund"),
               (1415, "Hrvoje calls in the Ottomans against Hungary"), (1416, "Hrvoje dies")],
      uncertain="Hrvoje's faith is debated: he patronised both the Bosnian Church and Catholics."),
    R("kosaca", "Lands of Sandalj Hranić", "Kosača", "monarchy", "Grand Duke", "county", "hum", "bosnian_church",
      "bosnian",
      person("Sandalj Hranić Kosača", 1370, "Kosača", approximate=True, reign=1392),
      heir=person("Vukac Hranić", 1372, approximate=True, relation="brother"), overlord=("bosnia", "vassal"),
      situation="Sandalj rules Hum and the hills behind Ragusa, and plays the Bosnian king, Hrvoje, Ragusa "
                "and the Ottomans against each other.",
      notable=[(1411, "Sandalj marries Jelena, the Despot's sister"),
               (1419, "Sandalj sells Konavle to Ragusa"),
               (1448, "His nephew Stjepan takes the title Herceg: Herzegovina")]),
    R("pavlovic", "Lands of Pavle Radinović", "Pavlović", "monarchy", "Lord", "county", "borac",
      "bosnian_church", "bosnian",
      person("Pavle Radinović", 1360, "Pavlović", approximate=True, reign=1391),
      overlord=("bosnia", "vassal"),
      situation="The lord of Borač and its silver mines, at Sandalj's elbow and in his way.",
      notable=[(1415, "Pavle is murdered at Sandalj's instigation"), (1463, "The Ottomans take the Pavlović lands")]),
    R("zeta", "Lordship of Zeta", "Zetan", "monarchy", "Lord", "county", "zeta", "orthodox", "serbian",
      person("Đurađ II Balšić", 1365, "Balšić", approximate=True, reign=1385),
      heir=person("Balša III", 1387, relation="son"), spouse="Jelena Lazarević",
      overlord=("ott_rum", "tributary"),
      situation="The Balšići have lost Scutari to Venice and want it back. Đurađ is ailing; his son Balša will "
                "fight Venice for the coast.",
      notable=[(1403, "Đurađ II dies; Balša III succeeds"), (1405, "The first Scutari war against Venice"),
               (1421, "Balša III dies and leaves Zeta to the Despot of Serbia")]),
    # --- the Albanian lords -------------------------------------------------------------------------
    R("thopia", "Lordship of Kruja", "Thopia", "monarchy", "Lady", "county", "kruja", "catholic", "albanian",
      person("Helena Thopia", 1365, "Thopia", approximate=True, reign=1394),
      overlord=("venice", "protectorate"),
      situation="Karl Thopia's daughter holds Kruja with Venetian backing; her half-brother Niketa wants it.",
      notable=[(1403, "Niketa Thopia takes Kruja from Helena"), (1415, "Kruja falls to the Ottomans")],
      uncertain="Helena's first husband, the Venetian Marco Barbarigo, ruled in her name; Venice's protection "
                "is the game's reading of that."),
    R("kastrioti", "Lordship of Kastrioti", "Kastrioti", "monarchy", "Lord", "county", "dibra", "orthodox",
      "albanian",
      person("Gjon Kastrioti", 1375, "Kastrioti", approximate=True, reign=1389),
      heir=person("Stanisha Kastrioti", 1395, approximate=True, relation="son"), spouse="Voisava",
      overlord=("ott_rum", "vassal"),
      situation="Gjon holds Mat and Dibra between the Ottomans and Venice, switching faith and allegiance as "
                "he must. His youngest son, George, will be born in 1405.",
      notable=[(1405, "George Kastrioti, Skanderbeg, is born"), (1443, "Skanderbeg rises against the Ottomans"),
               (1444, "The League of Lezhë")],
      uncertain="When Gjon began to rule is not known exactly."),
    R("dukagjini", "Lordship of Dukagjini", "Dukagjini", "monarchy", "Lord", "county", "dukagjin", "catholic",
      "albanian",
      person("Tanush the Great", 1360, "Dukagjini", approximate=True, reign=1393),
      heir=person("Pal Dukagjini", 1390, approximate=True, relation="son"), overlord=("venice", "protectorate"),
      situation="The Dukagjini hold the mountains behind Lezhë and treat with Venice over the town.",
      notable=[(1444, "The Dukagjini join the League of Lezhë")],
      uncertain="Lekë Dukagjini's sons Progon and Tanush shared the lordship; dates are approximate."),
    R("arianiti", "Lordship of Arianiti", "Arianiti", "monarchy", "Lord", "county", "shpat", "orthodox",
      "albanian",
      person("Komnen Arianiti", 1360, "Arianiti", approximate=True, reign=1390),
      heir=person("Gjergj Arianiti", 1383, relation="son"), overlord=("ott_rum", "vassal"),
      situation="The Arianiti hold the mountains of Shpat between the Shkumbin and Ohrid.",
      notable=[(1432, "Gjergj Arianiti rises against the Ottomans"),
               (1451, "His daughter Donika marries Skanderbeg")],
      uncertain="Komnen Arianiti's dates are approximate."),
    R("muzaka", "Lordship of Berat", "Muzaka", "monarchy", "Lord", "county", "berat", "orthodox", "albanian",
      person("Teodor III Muzaka", 1370, "Muzaka", approximate=True, reign=1396),
      overlord=("ott_rum", "tributary"),
      situation="The Muzaka hold Berat and the plain of Myzeqe, the richest corner of Albania.",
      notable=[(1417, "The Ottomans take Berat"), (1437, "Teodor rises against the Ottomans")]),
    R("valona", "Principality of Valona", "Valonan", "monarchy", "Lady", "county", "valona", "orthodox",
      "albanian",
      person("Regina Balšić", 1365, "Balšić", approximate=True, reign=1396),
      overlord=("ott_rum", "tributary"),
      situation="The widow of Mrkša Žarković holds Valona and Kanina, and offers them to Venice in turn.",
      notable=[(1414, "Regina dies"), (1417, "The Ottomans take Valona")]),
    R("zenebishi", "Lordship of Gjirokastër", "Zenebishi", "monarchy", "Lord", "county", "gjirokaster",
      "orthodox", "albanian",
      person("Gjin Zenebishi", 1350, "Zenebishi", approximate=True, reign=1386),
      heir=person("Simon Zenebishi", 1380, approximate=True, relation="son"), overlord=("ott_rum", "tributary"),
      situation="The lord of Gjirokastër raids Epirus and once held Esau of Ioannina for ransom.",
      notable=[(1411, "Zenebishi and the Spata invade Epirus"), (1418, "Gjin Zenebishi dies"),
               (1419, "The Ottomans take Gjirokastër")]),
    # --- Anatolia -------------------------------------------------------------------------------------
    R("ott_isa", "Ottomans of Bursa", "Ottoman", "monarchy", "Çelebi", "duchy", "bursa", "sunni", "turkish",
      person("İsa Çelebi", 1380, "Osman", approximate=True, reign=1402), overlord=("timurids", "vassal"),
      situation="After Timur's men sacked Bursa, Bayezid's son İsa took the old capital and calls himself "
                "sultan. His brothers Mehmed and Süleyman both want it.",
      notable=[(1403, "Mehmed defeats İsa at Ulubad"), (1403, "İsa is killed")]),
    R("ott_meh", "Ottomans of Amasya", "Ottoman", "monarchy", "Çelebi", "duchy", "amasya", "sunni", "turkish",
      person("Mehmed Çelebi", 1386, "Osman", approximate=True, reign=1402), overlord=("timurids", "vassal"),
      situation="The youngest of Bayezid's free sons holds Amasya and Tokat, far from Timur's reach. He is "
                "patient, and he means to have the whole empire.",
      notable=[(1403, "Mehmed takes Bursa from İsa"), (1413, "Mehmed reunites the empire as Mehmed I"),
               (1421, "Mehmed I dies; Murad II succeeds")]),
    R("candar", "Beylik of Candar", "Candarid", "monarchy", "Bey", "duchy", "kastamonu", "sunni", "turkish",
      person("İsfendiyar Bey", 1350, "Candar", approximate=True, reign=1385), overlord=("timurids", "vassal"),
      situation="Timur gave İsfendiyar back Kastamonu. He holds Sinop's harbour and copper mines and wants "
                "to keep the Ottomans divided.",
      notable=[(1417, "Mehmed I takes Çankırı from İsfendiyar"), (1461, "The Ottomans annex the beylik")]),
    R("germiyan", "Beylik of Germiyan", "Germiyanid", "monarchy", "Bey", "duchy", "kutahya", "sunni", "turkish",
      person("Yakub II", 1367, "Germiyan", approximate=True, reign=1387), overlord=("timurids", "vassal"),
      situation="Restored by Timur to his old lands around Kütahya, Yakub is a poet and a schemer who fears "
                "both the Ottomans and Karaman.",
      notable=[(1411, "Yakub is imprisoned by Karaman"), (1429, "Yakub leaves Germiyan to the Ottomans")]),
    R("saruhan", "Beylik of Saruhan", "Saruhanid", "monarchy", "Bey", "county", "manisa", "sunni", "turkish",
      person("Hızır Şah", 1365, "Saruhan", approximate=True, reign=1402), overlord=("timurids", "vassal"),
      situation="Restored by Timur, the last Saruhanid holds Manisa and the alum of the Hermus valley.",
      notable=[(1410, "Mehmed Çelebi kills Hızır Şah and takes Saruhan")]),
    R("aydin", "Beylik of Aydın", "Aydınid", "monarchy", "Bey", "county", "ayasoluk", "sunni", "turkish",
      person("İsa Bey", 1370, "Aydın", approximate=True, reign=1402),
      heir=person("Umur II", 1372, approximate=True, relation="brother"), overlord=("timurids", "vassal"),
      situation="Timur gave the brothers İsa and Umur back the coast of Ephesus and Smyrna; the adventurer "
                "Cüneyd waits for his chance.",
      notable=[(1405, "Cüneyd seizes the beylik"), (1425, "The Ottomans annex Aydın")]),
    R("mentese", "Beylik of Menteşe", "Menteşid", "monarchy", "Bey", "county", "milas", "sunni", "turkish",
      person("İlyas Bey", 1370, "Menteşe", approximate=True, reign=1402), overlord=("timurids", "vassal"),
      situation="Restored by Timur, İlyas holds Milas and the coast facing Rhodes, and trades with Venice.",
      notable=[(1421, "İlyas dies"), (1425, "The Ottomans annex Menteşe")]),
    R("teke", "Beylik of Teke", "Tekeid", "monarchy", "Bey", "county", "elmali", "sunni", "turkish",
      person("Osman Çelebi", 1370, "Teke", approximate=True, reign=1402), overlord=("timurids", "vassal"),
      situation="Osman is back in the hills of Elmalı and wants Antalya, the great port his family lost to "
                "Bayezid.",
      notable=[(1423, "Osman is killed besieging Antalya")],
      uncertain="Whether Antalya itself was in Teke's or Ottoman hands in 1402 is unclear."),
    R("karaman", "Beylik of Karaman", "Karamanid", "monarchy", "Bey", "kingdom", "konya", "sunni", "turkish",
      person("Mehmed II of Karaman", 1370, "Karaman", approximate=True, reign=1402),
      heir=person("Bengi Ali", 1372, approximate=True, relation="brother"), overlord=("timurids", "vassal"),
      situation="Freed by Timur, the sons of Alaeddin Ali are back in Konya with a few more fortresses. "
                "Karaman claims the heritage of the Seljuks and is the Ottomans' oldest enemy.",
      notable=[(1414, "Mehmed of Karaman takes and burns Bursa"), (1423, "Mehmed dies besieging Antalya"),
               (1468, "The Ottomans annex Karaman")]),
    R("ramazan", "Beylik of Ramazan", "Ramazanid", "monarchy", "Bey", "county", "adana", "sunni", "turkish",
      person("Ahmed Bey", 1350, "Ramazan", approximate=True, reign=1383), overlord=("mamluks", "vassal"),
      situation="The Turkmen lords of Adana guard the Mamluks' northern march in Cilicia.",
      notable=[(1415, "Ahmed takes Tarsus from Karaman"), (1416, "Ahmed dies")]),
    R("dulkadir", "Beylik of Dulkadir", "Dulkadirid", "monarchy", "Bey", "county", "elbistan", "sunni", "turkish",
      person("Nasireddin Mehmed Bey", 1365, "Dulkadir", approximate=True, reign=1399),
      overlord=("mamluks", "vassal"),
      situation="The Turkmen of Elbistan and Maraş balance between the Mamluks and the Ottomans and marry "
                "their daughters to both.",
      notable=[(1403, "Mehmed marries a daughter to Mehmed Çelebi"), (1442, "Nasireddin Mehmed dies")]),
    R("trebizond", "Empire of Trebizond", "Trapezuntine", "monarchy", "Emperor", "kingdom", "trebizond",
      "orthodox", "greek",
      person("Manuel III Megas Komnenos", 1364, "Komnenos", reign=1390),
      heir=person("Alexios IV Megas Komnenos", 1382, relation="son"), spouse="Anna Philanthropene",
      overlord=("timurids", "vassal"),
      situation="Manuel bowed to Timur and sent him ships. Trebizond lives from the silk road's end and its "
                "Genoese and Venetian merchants.",
      notable=[(1417, "Manuel III dies"), (1461, "Mehmed II takes Trebizond")]),
    R("timurids", "Timurid Empire", "Timurid", "monarchy", "Emir", "empire", "erzincan", "sunni", "turkish",
      person("Timur", 1336, "Timurid", reign=1370),
      heir=person("Muhammad Sultan", 1375, relation="grandson"),
      situation="The conqueror has broken the Ottomans and his armies winter in western Anatolia. He has "
                "restored the beyliks as his vassals; in the east he holds Erzincan, Erzurum and Mardin "
                "through his vassals. He will soon turn back towards China.",
      notable=[(1402, "Timur takes Smyrna from the Knights in December"),
               (1403, "Timur leaves Anatolia; Bayezid dies a prisoner"),
               (1405, "Timur dies on his way to China")],
      uncertain="Timur's capital, Samarkand, is far off the map; Erzincan stands in for his eastern vassals."),
    R("akkoyunlu", "Aq Qoyunlu", "Aq Qoyunlu", "tribal", "Bey", "duchy", "diyarbakir", "sunni", "turkish",
      person("Qara Osman", 1356, "Aq Qoyunlu", approximate=True, reign=1402), overlord=("timurids", "vassal"),
      situation="The White Sheep Turkmen fought for Timur at Ankara and were given Diyarbakır. Their enemies "
                "are the Black Sheep of Qara Yusuf.",
      notable=[(1435, "Qara Osman falls in battle against the Qara Qoyunlu"),
               (1467, "Uzun Hasan destroys the Qara Qoyunlu")],
      uncertain="Qara Osman led the confederation in fact before he was its formal head."),
    R("georgia", "Kingdom of Georgia", "Georgian", "monarchy", "King", "kingdom", "kutaisi", "orthodox",
      "georgian",
      person("George VII", 1370, "Bagrationi", approximate=True, reign=1393),
      heir=person("Constantine", 1369, approximate=True, relation="brother"),
      situation="Georgia has been ravaged by Timur's eight invasions and still resists. The king wants his "
                "land rebuilt and his vassals in the west kept loyal.",
      notable=[(1407, "George VII falls fighting the Qara Qoyunlu"), (1412, "Alexander I begins to rebuild"),
               (1466, "The kingdom splits into Kartli, Kakheti and Imereti")],
      uncertain="Tbilisi lies just off the map; Kutaisi stands in as the capital."),
    R("mamluks", "Mamluk Sultanate", "Mamluk", "monarchy", "Sultan", "empire", "aleppo", "sunni", "arab",
      person("an-Nasir Faraj", 1386, "Burji", reign=1399),
      situation="The boy sultan's Syria was sacked by Timur in 1400-1401: Aleppo and Damascus burned. The "
                "emirs fight over the regency while the Turkmen of the north drift away.",
      notable=[(1405, "Faraj is briefly deposed"), (1412, "Faraj is killed in Damascus"),
               (1426, "The Mamluks defeat and capture King Janus of Cyprus at Khirokitia")],
      uncertain="Cairo lies far off the map; Aleppo stands in as the capital. The Mamluk elite were "
                "Circassians and Turks ruling an Arab country."),
]


def build():
    owners = {}
    for pid, _name, _lon, _lat, owner, _culture, _religion in PROVINCES:
        owners.setdefault(owner, []).append(pid)
    out = []
    for r in REALMS:
        tag = r["tag"]
        assert tag in REALM_COLORS, tag
        assert r["capital"] in owners[tag], (tag, r["capital"])
        if r["overlord"]:
            assert r["overlord"]["tag"] in REALM_COLORS, (tag, r["overlord"])
        out.append({**r, "short": REALM_NAMES[tag], "color": list(REALM_COLORS[tag])})
    missing = set(REALM_COLORS) - {r["tag"] for r in REALMS}
    assert not missing, missing
    return out


RELATIONS = [
    (["hungary", "naples"], "rivalry", "Ladislaus of Naples claims the Hungarian crown against Sigismund."),
    (["hungary", "bohemia"], "rivalry", "Sigismund holds his brother King Wenceslaus prisoner."),
    (["hungary", "moravia"], "rivalry", "Sigismund holds his cousin Prokop prisoner; Jobst wants him back."),
    (["hungary", "austria"], "alliance", "Sigismund has named Albert IV of Austria his heir."),
    (["hungary", "celje"], "alliance", "Hermann of Celje is Sigismund's closest friend."),
    (["poland", "lithuania"], "union", "The Polish-Lithuanian union, renewed at Vilnius and Radom in 1401."),
    (["poland", "celje"], "marriage", "Władysław Jagiełło married Anna of Celje in January 1402."),
    (["poland", "moldavia"], "alliance", "Alexander of Moldavia swore homage to Poland in March 1402."),
    (["lithuania", "horde"], "rivalry", "Edigu crushed Vytautas at the Vorskla in 1399."),
    (["venice", "genoa"], "rivalry", "The old enemies of the Levant trade; war will flare at Modon in 1403."),
    (["venice", "hungary"], "rivalry", "Venice wants Dalmatia back from the crown of Hungary."),
    (["venice", "zeta"], "rivalry", "The Balšići want back Scutari, which they sold to Venice in 1396."),
    (["hrvoje", "naples"], "alliance", "Hrvoje backs Ladislaus of Naples for the crown of Hungary."),
    (["serbia", "brankovic"], "war", "Stefan Lazarević and the Brankovićs fight for Serbia; Tripolje is near."),
    (["serbia", "zeta"], "marriage", "Đurađ Balšić is married to Stefan Lazarević's sister Jelena."),
    (["ott_rum", "ott_isa"], "rivalry", "The sons of Bayezid fight for his throne."),
    (["ott_isa", "ott_meh"], "war", "İsa and Mehmed will fight for Bursa within the year."),
    (["ott_rum", "byzantium"], "rivalry", "Süleyman must buy peace from the Christians he can no longer "
                                          "frighten; the Treaty of Gallipoli is coming."),
    (["byzantium", "morea"], "alliance", "The Despot of the Morea is the emperor's brother."),
    (["morea", "knights"], "rivalry", "The Despot wants Corinth back from the Knights."),
    (["karaman", "ott_meh"], "rivalry", "Karaman is the Ottomans' oldest enemy in Anatolia."),
    (["timurids", "mamluks"], "rivalry", "Timur sacked Aleppo and Damascus in 1400-1401."),
    (["timurids", "georgia"], "war", "Timur's armies have invaded Georgia again and again."),
    (["timurids", "knights"], "war", "Timur's armies march on the Knights' castle at Smyrna."),
    (["cyprus", "genoa"], "rivalry", "The Genoese hold Famagusta, the kingdom's great port."),
    (["ioannina", "spata"], "war", "The Despot of Ioannina and the Spata of Arta fight over Epirus."),
    (["tocco", "spata"], "rivalry", "Carlo Tocco has his eyes on Arta."),
    (["athens", "venice"], "war", "Antonio Acciaioli besieges the Venetians on the Acropolis."),
]


def main():
    realms = build()
    relations = [{"tags": tags, "kind": kind, "note": note} for tags, kind, note in RELATIONS]
    for rel in relations:
        for t in rel["tags"]:
            assert t in REALM_COLORS, t
    path = ROOT / "crowns" / "data" / "realms.json"
    path.write_text(json.dumps({"realms": realms, "relations": relations}, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"wrote {len(realms)} realms and {len(relations)} relations to {path}")


if __name__ == "__main__":
    main()
