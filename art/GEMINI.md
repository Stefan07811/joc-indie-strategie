# Imagini de la Gemini pentru Crowns of the Balkans

Imaginile intră în folderul `art/incoming/`, pe branch-ul `claude/stoic-dijkstra-caik1v`, fiecare cu numele
exact din listă. De restul (decupare, potrivire, punere în joc) mă ocup eu.

## Cum se face

1. Deschide Gemini și începe **o conversație nouă pentru fiecare lot** (A, B, C).
2. Trimite întâi **mesajul de pregătire** al lotului (o singură dată).
3. Apoi trimite **pe rând** cererile lotului, câte un mesaj pentru fiecare imagine. Așteaptă imaginea
   înainte să trimiți următoarea cerere.
4. Verifică imaginea după regulile lotului. Dacă nu le respectă, scrie-i: `Regenerate it, following the rules
   from my first message.`
5. Descarcă imaginea la dimensiunea maximă și redenumește fișierul cu numele din listă (exact, cu litere mici).
6. Pe GitHub: deschide repository-ul, alege branch-ul `claude/stoic-dijkstra-caik1v`, intră în folderul
   `art/incoming/`, apoi „Add file → Upload files”. Trage imaginile în pagină și apasă „Commit changes”.
7. Spune-mi în chat când sunt încărcate (poate fi și doar o parte dintre ele).

Dacă Gemini „uită” regulile după câteva imagini, folosește varianta completă a cererii, de la finalul
fișierului.

---

## Lotul A: texturi de teren (6 imagini)

**Mesajul de pregătire:**

```
I am making a medieval strategy game set in the Balkans in the year 1402. In this chat I will ask you, one at a time, for ground textures for the battlefield. Rules for every image:
- one square image, 1024x1024
- a seamless tileable texture: the left edge must continue the right edge, and the top edge the bottom edge
- seen straight from above (top-down, orthographic), no perspective, no horizon
- evenly lit, no shadows, no light direction
- no objects, no people, no animals, no text, no border, no frame
- hand-painted game texture, painterly but detailed, muted natural colours
Reply only with the image.
```

**Cererile** (câte una pe mesaj):

| Fișier | Mesajul de trimis |
|---|---|
| `ground_meadow.png` | `Texture: green meadow grass with small clover and a few wildflowers, a Balkan plain in late summer.` |
| `ground_steppe.png` | `Texture: dry yellow steppe grass, sparse and sunburnt.` |
| `ground_dirt.png` | `Texture: bare packed brown earth of a country road, with small pebbles.` |
| `ground_mud.png` | `Texture: trampled mud churned by boots and hooves, wet dark earth.` |
| `ground_rock.png` | `Texture: grey limestone rocky ground with small patches of grass.` |
| `ground_forest.png` | `Texture: forest floor with fallen oak leaves, moss and twigs.` |

**Verifică:** imaginea e văzută de sus, fără umbre și fără obiecte.

---

## Lotul B: copaci și plante (9 imagini)

**Mesajul de pregătire:**

```
I am making a medieval strategy game set in the Balkans in the year 1402. In this chat I will ask you, one at a time, for sprites of trees and plants. Rules for every image:
- one square image, 1024x1024
- exactly one plant, seen from the side at eye level, the whole plant visible from its base to its top, centered, not touching the edges of the image
- the background is a solid flat pure magenta colour (#FF00FF) everywhere around the plant
- no ground, no grass under it, no shadow on the background, no other objects, no text, no border
- hand-painted gouache style like a medieval miniature painting, soft daylight from the upper left, muted natural colours, clean sharp edges
Reply only with the image.
```

**Cererile:**

| Fișier | Mesajul de trimis |
|---|---|
| `tree_oak.png` | `Sprite: a broad old oak tree in summer.` |
| `tree_beech.png` | `Sprite: a tall beech tree in summer.` |
| `tree_pine.png` | `Sprite: a Balkan black pine tree.` |
| `tree_poplar.png` | `Sprite: a tall slender poplar tree.` |
| `tree_willow.png` | `Sprite: a willow tree as found along a river bank.` |
| `bush_1.png` | `Sprite: a blackthorn bush.` |
| `bush_2.png` | `Sprite: a hazel bush.` |
| `grass_tuft.png` | `Sprite: a tuft of tall wild grass with a few seed heads.` |
| `reeds.png` | `Sprite: a clump of river reeds.` |

**Verifică:** fondul e magenta peste tot, fără pământ și fără umbră sub plantă, iar planta nu e tăiată de
marginea imaginii.

---

## Lotul C: steme pentru steaguri și scuturi (12 imagini)

**Mesajul de pregătire:**

```
I am making a medieval strategy game set in the Balkans in the year 1402. In this chat I will ask you, one at a time, for the heraldry of the realms, to be painted on banners and shields. Rules for every image:
- one square image, 1024x1024
- the design fills the whole image edge to edge, as a flat square banner seen straight from the front
- no shield outline, no pole, no cloth folds, no perspective, no shading, no background around it
- no text, no letters, no border, no frame
- flat bold colours and clear shapes like a page of a medieval armorial (roll of arms), so it still reads when small
Reply only with the image.
```

**Cererile:**

| Fișier | Mesajul de trimis |
|---|---|
| `arms_wallachia.png` | `Heraldry of Wallachia: a black eagle holding a golden cross in its beak, a golden sun at the upper left and a silver crescent moon at the upper right, on a blue field.` |
| `arms_moldavia.png` | `Heraldry of Moldavia: a black aurochs head seen from the front with a golden six-pointed star between its horns, a rose on its left and a crescent moon on its right, on a red field.` |
| `arms_hungary.png` | `Heraldry of the Kingdom of Hungary: divided vertically; the left half has eight horizontal stripes alternating red and silver; the right half has a silver double cross rising from a green triple hill, on a red field.` |
| `arms_serbia.png` | `Heraldry of the Serbian Despotate: a white double-headed eagle with spread wings, on a red field.` |
| `arms_ottoman.png` | `Heraldry of the early Ottoman sultans: a white crescent moon on a deep red field.` |
| `arms_byzantium.png` | `Heraldry of the Byzantine Empire under the Palaiologos: a golden cross, with a golden firesteel shaped like the letter B in each of the four quarters, on a red field.` |
| `arms_venice.png` | `Heraldry of the Republic of Venice: the golden winged lion of Saint Mark holding an open book, on a red field.` |
| `arms_genoa.png` | `Heraldry of the Republic of Genoa: a red cross on a white field.` |
| `arms_bosnia.png` | `Heraldry of the Kingdom of Bosnia (Kotromanić): a white diagonal band from the upper left to the lower right, with golden fleurs-de-lis on both sides of the band, on a blue field.` |
| `arms_poland.png` | `Heraldry of the Kingdom of Poland: a white crowned eagle with spread wings, on a red field.` |
| `arms_lithuania.png` | `Heraldry of the Grand Duchy of Lithuania: a white armoured knight on a white galloping horse, raising a sword, on a red field.` |
| `arms_knights.png` | `Heraldry of the Knights Hospitaller of Rhodes: a white cross on a red field.` |

**Verifică:** desenul umple tot pătratul, fără contur de scut și fără steag fluturând.

Celelalte țări primesc deocamdată steaguri desenate de mine, din culorile lor.

---

## Varianta completă (dacă Gemini uită regulile)

Lotul A, se înlocuiește `[X]` cu descrierea texturii din tabel:

```
Seamless tileable texture of [X], square 1024x1024, seen straight from above (top-down, orthographic), evenly lit, no shadows, no perspective, no objects, no text, no border. Hand-painted game texture, painterly but detailed, muted natural colours. The edges must tile seamlessly.
```

Lotul B, se înlocuiește `[X]` cu planta din tabel:

```
A single [X], seen from the side at eye level, the whole plant visible from its base to its top, centered, not touching the edges, on a solid flat pure magenta background (#FF00FF), no ground, no shadow on the background, no text, no border. Hand-painted gouache style like a medieval miniature painting, soft daylight from the upper left, muted natural colours, clean sharp edges. Square 1024x1024.
```

Lotul C, se înlocuiește `[X]` cu descrierea stemei din tabel:

```
[X] Flat square banner design filling the whole image edge to edge, seen straight from the front, no shield outline, no pole, no cloth folds, no perspective, no shading, no text, no border. Flat bold colours and clear shapes like a page of a medieval armorial. Square 1024x1024.
```
