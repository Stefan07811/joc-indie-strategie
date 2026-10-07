# Crowns of the Balkans — jocul nou (în lucru)

Joc de mare strategie istoric, fără elemente fantastice: Balcanii, Dunărea și Anatolia după bătălia de la
Ankara (iulie 1402). Se inspiră din Europa Universalis și Crusader Kings pentru campanie și din Total War
pentru bătălii. Textele din joc sunt în engleză.

Jocul vechi cu legende (`legendele/`) rămâne în depozit până când cel nou devine jucabil.

![Harta în 1402](docs/crowns/overview.png)

![Alegerea statului: fiecare țară are povestea ei din 1402](docs/crowns/choose.png)

![Târgoviștea: clădiri, recrutare, venituri](docs/crowns/province.png)

![Oastea Țării Românești pornește spre Nicopole: raza de marș pe o lună și drumul](docs/crowns/army.png)

![Războiul cu Rumelia otomană: ținuturile ocupate sunt hașurate în culoarea ocupantului](docs/crowns/war.png)

## Deciziile de bază

| Ce | Alegerea |
|---|---|
| Grafica | 3D cu Panda3D (Python): relieful real, cameră care se înclină, se rotește și se apropie |
| Timpul | Ture lunare (septembrie 1402 → 1500 și mai departe) |
| Startul | Septembrie 1402: Interregnul otoman, statele mici au o șansă |
| Harta | Balcanii, Dunărea, toată Ungaria, sudul Poloniei și al Lituaniei, Crimeea, Anatolia, Caucazul de vest |
| Ritmul | Războaiele se încheie cu păci negociate (scor de război), nu cu cucerirea tuturor provinciilor |
| Bătăliile | La început se rezolvă automat pe hartă; bătăliile tactice 3D vin la final |
| Stilul | „Codex”: harta e o hartă portulan gravată și colorată de mână, pe pergament. Armatele sunt figurine pictate 3D, cu contur de cerneală |
| Mișcarea | Ca în Total War: armatele merg liber pe hartă, cu un buget lunar de marș |

## Stilul „Codex”

Ca să nu semene cu Europa Universalis sau Crusader Kings, harta arată ca un manuscris din secolul al XV-lea:
pergament, relief desenat cu hașuri de cerneală care se îndesesc la umbră, state colorate în acuarelă care
se adună mai închis la margini, granițe trase cu pana (punctate între provincii, ferme între state). Marea
are liniile de coastă gravate și liniile de vânt ale hărților portulane, pornind din roze ale vânturilor.
Armatele sunt miniaturi pictate: un călăreț și pedestrași pe un soclu, cu steagul statului care flutură.

## Lumea în 1402 (etapa B2)

- **64 de state** (`tools/realms_1402.py` → `crowns/data/realms.json`). Fiecare are: numele întreg, forma
  de guvernare, titlul conducătorului, rangul (imperiu, regat, ducat, comitat), capitala, conducătorul cu
  dinastia și anul nașterii, moștenitorul, soția sau soțul, suzeranul (vasal, tributar, protectorat sau
  uniune), situația din 1402 și ce urmărește, plus evenimentele care l-au așteptat în istorie.
  Unde izvoarele nu se pun de acord, intrarea o spune.
- **28 de relații** în curs: Sigismund contra lui Ladislau de Neapole, uniunea polono-lituaniană, frații
  otomani, Ștefan Lazarević contra Brankovićilor, Veneția contra Genovei și altele.
- **Provinciile** au acum relieful lor (câmpie, deal, munte, pădure, stepă, mlaștină, deșert), populația
  estimată pentru 1402 (vreo 21 de milioane de oameni pe toată harta), orașul mare, marfa (grâu, vite, vin,
  sare, argint, aur, mătase…) și cetatea.

## Mișcarea armatelor

Pământul e o rețea de pătrate de 3 km. Câmpia se străbate ușor; pădurea, dealul, muntele și mlaștina cer
mai mult. Râurile mari (Dunărea, Nistrul, Niprul, Tisa, Sava…) se trec greu, cu bărci, în afara vadurilor
și podurilor istorice (Nicopole, Giurgiu, Vidin, Silistra, Belgrad…). Strâmtorile se trec cu bacul. Când
alegi o armată, harta arată cu cerneală roșie până unde poate ajunge luna asta și o linie fină pentru
fiecare săptămână de marș. Cu clic dreapta îi dai ordin. Merge cât poate luna asta, iar restul drumului
rămâne ordin pentru lunile următoare, cu săgeți și apoi puncte. Tasta Space încheie luna.

## Harta (etapa B1)

- **Relief real:** altitudinile vin din Mapzen Terrain Tiles (date deschise, de pe AWS). Coastele, râurile
  și lacurile vin din Natural Earth (domeniu public). Proiecția e echidistantă, fidelă la 42,5°N, cu
  1,5 km pe pixel (1778 × 1312 pixeli). Relieful e exagerat de 8 ori, ca pe orice hartă de strategie.
- **Culoarea pământului** e calculată din relief și climă: stepa ucraineană, podișul anatolian, câmpiile
  Ungariei, pădurile Carpaților și ale Balcanilor, stâncă și zăpadă pe crestele înalte.
- **320 de provincii** în 1402, pe 64 de state și stăpâniri: regate, despotate, beylik-uri, republici
  maritime, ordine cavalerești, principate albaneze și marii nobili ai Bosniei. Lista e în
  `tools/history_1402.py`.
- **Granițele** nu sunt desenate de mână. Fiecare provincie crește din orașul ei peste relief, iar munții,
  râurile mari, marea și strâmtorile o frânează, așa că granițele se așază pe creste și pe râuri.
  Instrumentul e `tools/provinces.py`.
- **Moduri de hartă:** `1` relief, `2` politic. Granițele, selecția și culorile se calculează pe placa
  video, deci o cucerire se vede imediat.

```bash
pip install -r requirements.txt
python -m crowns                 # campania: alegi un stat pe hartă și îl conduci
python -m crowns --realm hungary # direct cu un stat (wallachia, moldavia, hungary, ott_rum, serbia, venice…)
python -m crowns --shots DIR     # capturi de verificare, fără ecran
python tools/terrain.py          # descarcă relieful și apele, refac harta de altitudini
python tools/provinces.py        # refac provinciile după tools/history_1402.py
python tools/realms_1402.py      # refac crowns/data/realms.json
```

## Campania (etapa B3)

Fiecare tură e o lună. Joci un stat și toate celelalte sunt conduse de AI.

- **Banii:** taxe de la oameni, valoarea mărfii fiecărei provincii (grâu, vite, vin, sare, argint, aur,
  mătase…) și comerțul orașelor; se plătesc curtea, armatele, zidurile noi și tributul către suzeran.
  Statele care trec dincolo de marginea hărții (mamelucii cu Egiptul, Timur, Hoarda, Polonia, Lituania,
  Genova) primesc și venitul de acolo.
- **Clădiri:** 9 feluri, fiecare cu 3 niveluri (ogoare, târg, meșteșugari, mină, port, ziduri, cetate,
  grajduri, biserică sau moschee). Se construiesc în luni, o lucrare odată pe provincie; orașele mari au
  loc pentru mai multe.
- **Oaste:** 7 tradiții militare. Țara Românească și Moldova au boieri, călărași, arcași și oastea cea
  mare; latinii au cavaleri, oșteni în armură și arbaletrieri; otomanii au sipahi, akıncı, azapi și
  ieniceri; Hoarda are arcași călare; mamelucii, cavaleria de elită. Recruții vin luna următoare.
- **Război:** se declară cu un scop (o provincie, tribut sau independență). Suzeranul, vasalii și aliații
  sunt chemați. Armatele care se întâlnesc dau bătălie, iar terenul contează (cavaleria e bună la câmpie,
  pedestrimea la munte). O armată oprită la un oraș dușman îl asediază câteva luni, după ziduri și
  garnizoană, mai încet iarna. Iarna în țară străină omoară oameni. Bătăliile, pământul ținut și scopul
  războiului dau scorul de război, iar scorul hotărăște ce pace acceptă fiecare.
- **Diplomație:** opinia dintre state ține de credință, de vechile prietenii și dușmănii, de granițe și de
  războaiele recente. Poți face alianțe, cere tribut unui vecin mult mai slab și trimite daruri.
- **AI-ul** construiește, recrutează, atacă vecinii slabi pe care nu-i iubește, asediază, se retrage din
  fața armatelor mai mari și face pace când scorul o cere. Îți poate oferi pace: primești o întrebare.
- **Salvare:** F5 salvează, F9 încarcă.

## Etapele

| Etapă | Ce aduce |
|---|---|
| **B1 — Harta 3D** (gata) | relief, ape, provincii, granițe, nume, cameră, selecție |
| **B2 — Lumea în 1402** (gata) | toate statele cu conducătorii, dinastiile, vasalii și tributul lor; dezvoltarea provinciilor |
| **B3 — Campania** (jucabilă; urmează echilibrul) | ture lunare, economie, clădiri, armate pe hartă, asedii, războaie și păci, diplomație, AI |
| **B4 — Oameni** | conducători și moștenitori care îmbătrânesc și mor, dinastii, căsătorii, nobili |
| **B5 — Istoria** | misiuni pentru fiecare țară, evenimente istorice (Interregnul, Varna, Constantinopol), decizii |
| **B6 — Interfața și sunetul** | ferestre în stil medieval, sfaturi, muzică cu instrumente reale |
| **B7 — Bătălii tactice 3D** | după ce campania e gata |
| **B8 — Lansarea** | executabil pentru Windows, echilibru |
