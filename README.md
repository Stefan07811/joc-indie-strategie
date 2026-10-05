# Legendele Carpaților (*Legends of the Carpathians*)

Joc indie de strategie în stilul Total War, inspirat din folclorul românesc. Patru legende își
dispută Carpații: **Voievodatul**, **Zmeii**, **Ielele** și **Strigoii**. Textele din joc sunt în engleză.

![Harta campaniei](docs/screenshot.png)

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

## Stadiul actual: etapa M1 (harta)

- Hartă fixă cu 20 de provincii și 5 tipuri de teren, desenată în stil pixel art.
- Alegi una dintre cele 4 facțiuni.
- Armatele au 4 puncte de mișcare pe tură. Câmpia costă 1, dealurile, pădurea și mlaștina 2, munții 3.
  Fiecare facțiune se mișcă ieftin (cost 1) pe terenul ei: Zmeii prin munți, Ielele prin păduri, Strigoii prin mlaștini.
- O tură = un anotimp, începând din primăvara anului 1400.
- Facțiunile AI își mută armatele spre provinciile pe care nu le dețin.
- Armatele nu pot încă intra într-o provincie ocupată de o armată străină. Bătăliile și cucerirea vin în etapa M2.

## Pentru dezvoltare

```bash
pip install -r requirements-dev.txt
python -m pytest                      # testele (regulile, harta și interfața, fără să deschidă fereastra)
python -m legendele --faction zmei    # sari peste ecranul de alegere a facțiunii
python -m legendele --faction iele --turns 4 --select-army --screenshot ecran.png
```

### Structura

```
legendele/
  game/        regulile jocului (fără pygame): date, stare, mișcare, ture, AI
  ui/          ecranele pygame: alegerea facțiunii, harta, panoul lateral
  data/        JSON: factions.json, units.json, map.json
  assets/      sprite-uri opționale (vezi assets/README.md)
  mapshape.py  forma provinciilor, calculată din punctele din map.json
tools/
  build_adjacency.py   recalculează vecinii provinciilor după ce muți/adaugi una în map.json
tests/
```

Ca să schimbi harta, editează pozițiile (`x`, `y`) sau proprietarii din `legendele/data/map.json`, apoi rulează
`python tools/build_adjacency.py`. Testele verifică dacă vecinii din fișier se potrivesc cu harta desenată.
