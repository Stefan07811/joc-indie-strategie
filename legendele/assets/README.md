# Grafică și sunet

Jocul își desenează singur toată grafica și își generează singur sunetele și muzica.
Pentru a înlocui ceva cu propriile fișiere, pune în acest folder un fișier cu numele potrivit.
Jocul îl folosește automat în locul variantei generate.

## Sprite-uri (PNG cu transparență)

Desenele generate sunt făcute din „pixeli” de 3×3 pixeli de ecran.
Desenează la rezoluție mică și mărește de 3× fără netezire, ca să se potrivească cu restul.

| Fișier | Ce este | Mărime (pixeli de desen) |
|---|---|---|
| `army_voievodat.png`, `army_zmei.png`, `army_iele.png`, `army_strigoi.png`, `army_haiduci.png` | Armata pe harta campaniei (în locul generalului cu stindard desenat din cod) | ~40×50 px de ecran |
| `emblem_<facțiune>.png` | Emblema singură | 5×5 |
| `siege.png` | Asediu | 9×9 |
| `unit_<icon>.png` | Pictograma unei unități (vezi câmpul `icon` din `data/units.json`) | ~8×8 |

Harta campaniei (relief, păduri, munți, râuri, cetăți, sate) e pictată de `ui/painter.py` și `ui/figures.py`
și se păstrează gata pictată în `~/.legendele/cache/`.

Pictogramele existente: spear, bow, horse, stake, gun, whelp, mace, wyrm, imp, crown, flower, tree, star, bolt,
skull, fang, ghost, wolf, axe.

## Fonturi

`fonts/` conține Liberation Serif (licența SIL Open Font License, vezi `fonts/LICENSE-Liberation.txt`),
folosit pentru nume și titluri.

## Sunete (`sounds/<nume>.ogg` sau `.wav`)

click, select, march, battle, victory, defeat, build, recruit, turn, alarm, coins, peace

## Muzică (`music/<temă>.ogg` sau `.wav`, se repetă în buclă)

| Temă | Când se aude | Modul generat |
|---|---|---|
| `menu` | meniurile | minorul românesc (doina) |
| `voievodat` | campania Principatului | doric |
| `zmei` | campania Dragonkin | frigic dominant |
| `iele` | campania Fae Court | lidic |
| `strigoi` | campania Revenants | locrian |
