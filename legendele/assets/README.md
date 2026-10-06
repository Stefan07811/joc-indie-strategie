# Grafică și sunet

Jocul își desenează singur toată grafica și își generează singur sunetele și muzica.
Pentru a înlocui ceva cu propriile fișiere, pune în acest folder un fișier cu numele potrivit.
Jocul îl folosește automat în locul variantei generate.

## Sprite-uri (PNG cu transparență)

Desenele generate sunt făcute din „pixeli” de 3×3 pixeli de ecran.
Desenează la rezoluție mică și mărește de 3× fără netezire, ca să se potrivească cu restul.

| Fișier | Ce este | Mărime (pixeli de desen) |
|---|---|---|
| `army_voievodat.png`, `army_zmei.png`, `army_iele.png`, `army_strigoi.png`, `army_haiduci.png` | Steagul armatei, cu emblema facțiunii | 12×14 |
| `emblem_<facțiune>.png` | Emblema singură | 5×5 |
| `castle.png` | Oraș cu ziduri | 13×7 |
| `camp.png` | Garnizoană fără ziduri | 9×6 |
| `heart.png` | Inima Munților | 9×9 |
| `siege.png` | Asediu | 9×9 |
| `unit_<icon>.png` | Pictograma unei unități (vezi câmpul `icon` din `data/units.json`) | ~8×8 |

Pictogramele existente: spear, bow, horse, stake, gun, whelp, mace, wyrm, imp, crown, flower, tree, star, bolt,
skull, fang, ghost, wolf, axe.

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
