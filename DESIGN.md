# Legendele Carpaților — document de design (propunere v0.1)

> Joc de strategie indie în stilul Total War, inspirat din folclorul românesc.
> Python + Pygame · un jucător contra AI · grafică pixel art (la început forme desenate din cod).
>
> Acesta e un **draft de discutat**. Tot ce e aici se poate schimba.

---

## 1. Ideea pe scurt

Carpații sunt împărțiți între patru puteri din legende. Fiecare vrea să stăpânească
**Inima Munților**, o provincie din centrul hărții. Joci o facțiune, îți conduci armatele
pe harta de campanie, construiești în provincii, faci pace sau război cu celelalte
facțiuni și cucerești pământuri.

**Ce ne face diferiți:** facțiunile sunt foarte asimetrice. Nu sunt „oameni cu alte culori”:
fiecare legendă are alt fel de economie, alte unități și o altă cale spre victorie.

---

## 2. Facțiunile

Numele din joc sunt în engleză. În paranteză e legenda românească din care vin.

| Facțiune | Teritoriu de start | Stil de joc | Mecanică unică (M4) |
|---|---|---|---|
| **The Principality** (Voievodatul, oameni) | Văi și câmpii | Echilibrat, economie puternică (+25% venit), cetăți solide | **Cetăți:** zidurile dau bonus mare la apărare; poate ridica **biserici** care slăbesc creaturile din jur |
| **The Dragonkin** (Zmeii) | Munți | Puține armate, dar foarte puternice și scumpe | **Comoara:** venitul crește cu aurul strâns (dobândă); un general Dragonkin poate **răpi** moștenitorul unui conducător, pentru răscumpărare sau ca ostatic |
| **The Fae Court** (Ielele) | Păduri și poieni | Rapide, slabe în luptă directă, magie | **Hora:** armatele inamice care intră în provinciile lor pierd moral și oameni în fiecare tură; nu pot fi văzute în păduri |
| **The Revenants** (Strigoii) | Mlaștini și cimitire | Ieftini, mulți, lenți; nu suferă de frig | **Ridicarea morților:** după fiecare bătălie, o parte din morți (de ambele tabere) se ridică în rândurile lor; mai puternici iarna |

**Outlaws** (Haiducii) sunt o forță neutră, nu o facțiune jucabilă. Păzesc provinciile neutre;
din M4 se vor ridica la răscoală în provinciile cu ordine publică scăzută.

### Unități (câte 5 pe facțiune)

Nivelul 1 se recrutează oriunde, nivelul 2 cere **Barracks**, nivelul 3 cere **Barracks** în capitală.
Eroii (★) sunt unici: unul singur pe facțiune.

- **The Principality:** Levy Spearmen (Oșteni) 1, Archers (Arcași) 1, Noble Horsemen (Călăreți) 2,
  Monster Hunters (Vânători de strigoi) 2, Gunners (Tunari) 3
- **The Dragonkin:** Dragon Whelps (Pui de zmeu) 1, Imp Scouts (Spiriduși) 1, Mace Drakes (Zmei cu buzdugan) 2,
  Three-Headed Wyrms (Balauri) 3, The Dragon Lord (Zmeul cel Mare) 3★
- **The Fae Court:** Dancing Fae (Iele dansatoare) 1, Woodland Spirits (Vâlve) 1, Midsummer Maidens (Sânziene) 2,
  Wrathful Sprites (Rusalii) 2, Mother of the Forest (Muma Pădurii) 3★
- **The Revenants:** Risen Dead (Morți ridicați) 1, Vampires (Strigoi) 2, Dread Wraiths (Moroi) 2,
  Werewolves (Vârcolaci) 2, The Elder Vampire (Strigoiul Bătrân) 3★
- **Outlaws:** Outlaw Brigands, Outlaw Marksmen (doar garnizoane)

Fiecare unitate are: atac, apărare, viață, moral, cost de recrutare, întreținere în aur, hrană
(unitățile mari mănâncă mai mult) și eventual o abilitate. Costurile sunt măsurate prin simulare
(`tools/fair_costs.py`), ca fiecare unitate să valoreze în luptă cât costă.

---

## 3. Harta de campanie

- **~20 de provincii** pe o **hartă fixă**, desenată de mână, stilizată a Carpaților (munți, păduri, câmpii, râuri, mlaștini).
- Fiecare provincie are: **proprietar**, **oraș/așezare**, **3 sloturi de clădiri**, **ordine publică**, **tip de teren**.
- Jocul e pe ture. **O tură = un anotimp** (primăvară → vară → toamnă → iarnă).
  - Iarna: armatele în afara orașelor pierd oameni (în afară de Strigoi, care devin mai puternici).
  - Vara: recolta dă hrană în plus.

### Armatele

- O armată = un **general** + până la **12 regimente**.
- Armatele au **puncte de mișcare** pe tură; terenul le influențează (munții costă mult, cu excepția Zmeilor).
- Când două armate dușmane se întâlnesc → **bătălie**.
- Când o armată intră într-o provincie cu oraș dușman → **asediu** (câteva ture) sau asalt direct.

### Generalii

- Câștigă experiență din bătălii → **niveluri** și **trăsături** (ex: „Bun strateg”, „Lacom”, „Îi e frică de iele”).
- Dacă generalul moare, armata pierde moral.

---

## 4. Economia

Două resurse, strânse la începutul fiecărui anotimp:

- **Aur:** taxe din provincii (după teren, plus bonus pentru capitale) și din clădiri.
  Plătește clădirile, recrutările și întreținerea armatelor. Dacă tezaurul e pe minus, câte un regiment dezertează în fiecare tură.
- **Hrană:** din teren și ferme. Fiecare regiment mănâncă după mărime (dragonii mult, lăncierii puțin).
  Vara recolta e cu 50% mai mare, iarna doar pe jumătate. Când grânarele se golesc, armatele flămânzesc și pierd oameni.

**Clădiri** (3 locuri pe provincie, gata în 1–2 anotimpuri): Farmsteads (+hrană), Market (+aur),
Mine (+aur, doar pe dealuri și munți), Barracks (unități de nivel 2–3), Stone Walls (ziduri și garnizoană).
Clădirile specifice fiecărei facțiuni vin în M4.

**Recrutare:** cel mult 2 regimente pe provincie pe tură. Sosesc în anotimpul următor: se alătură unei armate
din provincie sau formează una nouă, cu un general nou. Armatele au cel mult 12 regimente și se pot uni.

**Garnizoane:** orașele cu ziduri își refac garnizoana (2 regimente), celelalte provincii ridică o miliție (1 regiment).
Astfel, orice cucerire cere un asediu sau un asalt.

**Iarna:** armatele aflate în afara teritoriului propriu pierd oameni din cauza frigului (Revenants nu).

---

## 5. Bătăliile (în prima fază: rezolvate automat)

Cum am stabilit, **începem cu campania**. Bătăliile se calculează automat:

1. Se compară puterea fiecărei armate (atac, apărare, număr, moral), cu bonusuri de
   teren, general, ziduri și abilități de facțiune.
2. Lupta se simulează în câteva „runde” scurte. După fiecare rundă, moralul scade cu pierderile.
3. Tabăra care rămâne fără moral fuge. Învingătorul poate urmări și cauza pierderi în plus.
4. Ecranul de rezultat arată pierderile, experiența câștigată și efectele speciale (ex: Strigoii ridică morți).

Mai târziu, se poate adăuga un **ecran de luptă în timp real**. Formula automată rămâne pentru „rezolvare automată”.

---

## 6. Diplomația (simplă)

Relații între facțiuni: **Război / Pace / Alianță**. Fiecare facțiune AI are o „atitudine”
față de tine, influențată de granițe comune, putere militară, istoric (ai rupt pacea?) și
tensiunile din legende (Voievodatul și Strigoii nu fac niciodată alianță).

---

## 7. Victoria

- **Victorie prin cucerire:** controlezi 14 din 20 de provincii, **sau**
- **Victorie de legendă:** controlezi **Inima Munților** + capitala ta timp de 8 ture.
- **Înfrângere:** îți pierzi toate provinciile.

---

## 8. AI-ul

Pentru fiecare facțiune AI, la fiecare tură:

1. **Economie:** construiește după o listă de priorități specifică facțiunii.
2. **Recrutare:** menține armate proporționale cu amenințarea de la granițe.
3. **Armate:** alege ținte (provincii slab apărate, armate dușmane mai slabe) și evaluează riscul prin aceeași formulă ca la rezolvarea automată a bătăliilor.
4. **Diplomație:** cere pace când pierde, declară război când e mult mai puternică.

Fiecare facțiune are o „personalitate” (Zmeii: lacomi și agresivi; Ielele: defensive; Strigoii: se extind constant).

---

## 9. Tehnologie și structura codului

- **Python 3.11+**, **pygame-ce** (varianta întreținută activ a Pygame).
- Logica jocului e **separată de grafică**, ca s-o putem testa automat și ca AI-ul să folosească aceleași reguli.
- Datele (facțiuni, unități, clădiri, hartă) sunt în fișiere **JSON**, ca să putem echilibra jocul fără să schimbăm codul.
- Grafica: la început forme simple. Codul încearcă să încarce un sprite din `assets/` și, dacă nu-l găsește, desenează o formă. Astfel pixel art-ul se poate adăuga treptat.

```
legendele/
  __main__.py          # pornire: python -m legendele
  game/                # logica (fără pygame)
    state.py           # starea campaniei
    province.py, army.py, faction.py, battle.py, economy.py, diplomacy.py
    ai/                # AI-ul facțiunilor
  ui/                  # ecrane pygame (hartă, provincie, armată, rezultat bătălie)
  data/                # JSON: units.json, factions.json, buildings.json, map.json
  assets/              # sprite-uri pixel art (opțional)
tests/                 # teste pentru reguli și AI
```

---

## 10. Plan pe etape

| Etapă | Ce conține | Rezultat |
|---|---|---|
| **M1 — Harta** ✅ | Hartă cu provincii, selecție, armate care se mișcă, ture | Te poți plimba pe hartă |
| **M2 — Război** ✅ | Bătălii automate, cucerire, asedii simple, condiții de victorie | Prima partidă jucabilă cap-coadă (2 facțiuni) |
| **M3 — Economie** ✅ | Aur, hrană, clădiri, recrutare, anotimpuri | Decizii reale între construcție și armată |
| **M4 — Legende** | Cele 4 facțiuni cu mecanicile unice, Haiducii | Asimetria care face jocul special |
| **M5 — AI și diplomație** | Personalități, pace/alianță | Adversari credibili |
| **M6 — Aspect** | Pixel art, sunete, meniu, salvare/încărcare | Arată ca un joc |
| *(opțional)* **M7** | Bătălii în timp real | Ce lipsește ca să fie un Total War complet |

---

## 11. Decizii luate

| Întrebare | Decizie |
|---|---|
| Harta | **Fixă**, desenată de mână (`data/map.json`), aceeași în fiecare partidă |
| Victoria | **Da**: cucerire (14/20 provincii) **sau** Inima Munților + capitala timp de 8 ture |
| Limba jocului | **Engleză** (textele din joc). Documentația poate rămâne în română |

### Încă deschise (până se hotărăște altceva, folosim varianta propusă)

1. **Numele jocului:** provizoriu „Legendele Carpaților”, în engleză *Legends of the Carpathians*.
2. **Facțiunile:** cele patru propuse (Voievodatul, Zmeii, Ielele, Strigoii) + Haiducii ca rebeli.
3. **Durata:** 60–100 de ture.
