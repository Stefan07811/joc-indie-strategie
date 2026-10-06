# Legendele Carpaților (*Legends of the Carpathians*)

Joc indie de strategie în stilul Total War, inspirat din folclorul românesc. Patru legende își
dispută Carpații: **The Principality** (Voievodatul), **The Dragonkin** (Zmeii), **The Fae Court** (Ielele)
și **The Revenants** (Strigoii). Textele din joc sunt în engleză.

![Harta campaniei](docs/screenshot.png)

![Raport de bătălie](docs/battle_report.png)

![Administrarea unei provincii](docs/province.png)

Designul complet și planul pe etape sunt în [DESIGN.md](DESIGN.md).

## Cum pornești jocul

Ai nevoie de Python 3.10 sau mai nou.

```bash
pip install -r requirements.txt
python -m legendele
```

### Comenzi

| Acțiune | Cum |
|---|---|
| Selectezi o armată | clic pe steagul ei |
| Mărșăluiești | cu armata selectată, clic pe o provincie luminată (cercul arată costul) |
| Treci la următoarea armată | `Tab` |
| Inspectezi o provincie | clic pe ea (sau ții mouse-ul deasupra) |
| Deselectezi | clic dreapta sau `Esc` |
| Termini tura | butonul **End Turn**, `Enter` sau `Space` |

## Stadiul actual: etapa M3 (economia)

**Harta și mișcarea**
- Hartă fixă cu 20 de provincii și 5 tipuri de teren, desenată în stil pixel art.
- Armatele au 4 puncte de mișcare pe tură. Câmpia costă 1, dealurile, pădurea și mlaștina 2, munții 3.
  Fiecare facțiune se mișcă ieftin (cost 1) pe terenul ei: Dragonkin prin munți, Fae Court prin păduri,
  Revenants prin mlaștini. Excepție: Inima Munților nu aparține niciunei legende.
- Prin provinciile tale treci liber. Intrarea în orice altă provincie oprește marșul.
  Cercul de pe hartă e **auriu** pentru un marș liber și **roșu** dacă te așteaptă o luptă sau un asediu.

**Războiul**
- **Bătălii calculate automat.** Contează atacul și apărarea unităților, terenul, zidurile,
  generalul, terenul de acasă și moralul. O tabără fuge când pierde mai mult decât poate îndura.
  Înainte de atac, panoul îți arată o **prognoză**: victorie clară, victorie costisitoare sau înfrângere probabilă.
- **Cucerire:** o provincie fără apărare devine a ta când intri în ea.
- **Asedii:** provinciile neutre sunt păzite de haiduci, iar capitalele au ziduri și garnizoană.
  Armata ta rămâne la asediu și apărătorii slăbesc în fiecare anotimp. Poți da și asaltul (butonul **Assault the walls**).
- **Retragere:** cine pierde se retrage într-o provincie vecină care e a lui. Dacă nu are unde, armata e distrusă.
- Regimentele se refac câte puțin în fiecare tură pe teritoriul propriu.
- **Raport de bătălie** după fiecare luptă la care participi.

**Victorie și înfrângere**
- **Cucerire:** 14 din 20 de provincii.
- **Victorie de legendă:** ții Inima Munților și capitala ta 8 ture la rând.
- O facțiune care își pierde toate provinciile e eliminată. Dacă ești tu, ai pierdut.

**AI-ul** alege ținte valoroase și apropiate (Inima Munților, capitalele dușmane), își calculează
șansele cu aceeași formulă de luptă și atacă doar când crede că poate câștiga.

**Economia**
- **Aur și hrană**, afișate sus în panou, cu câștigul sau pierderea pe tură.
  Aurul vine din taxe și clădiri și pleacă pe întreținerea armatelor. Hrana vine din teren și ferme,
  iar unitățile mari mănâncă mai mult.
- **Provinciile tale:** selectează una și apasă **Manage province** (sau `M`). Fereastra are două părți:
  - **construcții:** Farmsteads, Market, Mine, Barracks, Stone Walls (3 locuri, gata în 1–2 anotimpuri);
  - **recrutare:** cel mult 2 regimente pe tură, care sosesc în anotimpul următor.
    Unitățile de nivel 2 cer Barracks, iar cele de nivel 3 și eroii cer Barracks în capitală.
- **Armate noi:** recruții se alătură armatei din provincie sau pornesc o armată nouă, cu un general nou.
  Armatele aflate în aceeași provincie se pot uni (**Merge the armies here**), până la 12 regimente.
- **Garnizoane:** orașele cu ziduri își refac garnizoana, celelalte provincii ridică o miliție.
  Orice cucerire cere acum un asediu sau un asalt.
- **Anotimpurile contează:** vara aduce o recoltă bogată, iarna hrană puțină și zăpadă pe hartă.
  Armatele aflate iarna departe de casă pierd oameni din cauza frigului, mai puțin Revenants.
- **Lipsuri:** fără hrană armatele flămânzesc, iar cu tezaurul pe minus soldații dezertează.
- **AI-ul** construiește, recrutează fără să intre pe minus și vânează facțiunea care ține Inima Munților.

**Ce urmează (M4):** mecanicile speciale ale fiecărei facțiuni (Hora, ridicarea morților, comoara
Dragonkin, bisericile), clădiri specifice și răscoalele Outlaws.

## Pentru dezvoltare

```bash
pip install -r requirements-dev.txt
python -m pytest                      # testele (regulile, harta și interfața, fără să deschidă fereastra)
python -m legendele --faction zmei    # sari peste ecranul de alegere a facțiunii
python -m legendele --faction iele --turns 4 --select-army --screenshot ecran.png
python tools/simulate.py 40 100       # AI contra AI pe 40 de partide, pentru echilibrare
python tools/duel.py                  # armate de același cost, facțiune contra facțiune
python tools/fair_costs.py            # cât valorează fiecare unitate în luptă, față de cost
```

### Structura

```
legendele/
  game/        regulile jocului (fără pygame): date, stare, mișcare, ture, AI
  ui/          ecranele pygame: alegerea facțiunii, harta, panoul lateral
  data/        JSON: factions.json, units.json, buildings.json, map.json
  assets/      sprite-uri opționale (vezi assets/README.md)
  mapshape.py  forma provinciilor, calculată din punctele din map.json
tools/
  build_adjacency.py   recalculează vecinii provinciilor după ce muți/adaugi una în map.json
  simulate.py          partide AI contra AI, cu statistici despre cine câștigă și cât durează
  duel.py, fair_costs.py   unelte de echilibrare a unităților
tests/
```

Ca să schimbi harta, editează pozițiile (`x`, `y`) sau proprietarii din `legendele/data/map.json`, apoi rulează
`python tools/build_adjacency.py`. Testele verifică dacă vecinii din fișier se potrivesc cu harta desenată.
