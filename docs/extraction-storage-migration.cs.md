# Změna ukládání a migrace výsledků

Výsledky nových importů patří výhradně do `data/{year}/{competition-folder}/`,
nikdy do `data/results/`. Rok pochází z `competition.date`. HTML/PDF extrakce,
pravidla interpretace a JSON schéma se nezměnily. Žádný další závod nebyl importován.

## Provedené přesuny

Všechny tři přesuny proběhly pomocí `git mv`. Úplný obsah souborů včetně
formátování a `generated_at` zůstal shodný po jednotlivých bajtech.

| Původní cesta | Nová cesta |
| --- | --- |
| `data/results/1c9bfcfe2eb34eb4.json` | `data/2026/stimax-cup-lovosice/2026-05-09-stimax-cup-lovosice.json` |
| `data/results/66e0f6c5dc0e2535.json` | `data/2026/stimax-cup-decin/2026-08-29-stimax-cup-decin.json` |
| `data/results/6b6d3056fb0aa913.json` | `data/2026/stimax-cup-usti-nad-labem/2026-04-26-stimax-cup-usti-nad-labem.json` |

Kontrolní SHA-256 jsou shodné před přesunem i po něm:

- Lovosice: `e05a09d07d07d7b66b1d67c3dd254357922a7cb1cbd585d19d120c80cbf7033e`
- Děčín: `32899c664d7157c2a847c3c62421877715c0f7ad4a76767cbf7817fc92242b34`
- Ústí nad Labem: `35fab6385dc67587991218e1838dd8f894327e1e0b44326234fac6ce4156b69a`

## Konflikt: Chomutov, závod 1034

`data/results/a7bb4dd25257b4f5.json` nebyl přesunut ani změněn, protože již existuje
místní necommitovaný `data/2026/chomutov-stimax/komplet.json` se stejnou zdrojovou URL, datem, názvem
a místem závodu, ale odlišným obsahem. Existující složka je správně rozpoznána;
nevznikla druhá složka pro tento závod. Obě verze zůstaly beze změn.

| Kontrola | Import v data/results | Existující komplet.json |
| --- | ---: | ---: |
| Výsledky | 416 | 416 |
| Chybějící roky narození | 4 | 415 |
| Nejednoznačně nerozdělená jména | 8 | 0 |
| Důvody penalizace | 76 | 76 |

Liší se 411 polí birth_year a osm dvojic first_name/last_name; odlišné jsou také
čas generování a diagnostické poznámky. Automatický přepis ani sloučení by
nesplňovaly požadavek zachovat obsah a nezničit existující data. Konflikt vyžaduje
výslovné rozhodnutí o kanonické verzi/archivaci. Dokud není vyřešený, nelze prázdnou
`data/results/` odstranit — obsahuje právě tento jeden dosud nezmigrovaný soubor.
Nové importy do ní nikdy nezapisují.

## Pipeline a kompatibilita

- `paths.py`: rok, stávající složky, čitelné názvy, stejné URL, kolize a konflikty.
- `storage.py`: používá nový resolver; zachovává validační a ochranné kontroly
  i atomické uložení do cílové složky.
- `__main__.py`: výchozí kořen `data/`; při neznámém datu/konfliktu uchová připravený
  JSON jako `pending.json` v ignorované diagnostice mimo finální data.
- `migrate.py`: plánování a bezpečné přesuny beze změny obsahu, s kontrolou bajtů,
  JSON validací, podporou git mv a samostatným hlášením konfliktů.

`backend/scripts/load_data.py` již používá `DATA_DIR.rglob("*.json")`; manifest ani
pevný seznam cest neexistuje a načítání nebylo třeba měnit. Databázový seed nebyl
spuštěn. Zbývající konfliktní duplicita Chomutova byla přítomná už před migrací;
pro čisté načtení tohoto závodu je nutné nejprve vyřešit volbu kanonické verze.

## Ověření

Prošlo 208 backendových testů včetně 24 nových testů ukládání/migrace; backend lint
prošel. Testy pokrývají skutečný rok závodu, vlastní existující složku, vytvoření
složky, ASCII názvy, opakovaný import a opravu názvu stejné URL, kolize se stabilním
ID, různé závody v jednom místě, nejednoznačné složky, neznámé datum a pending JSON,
migraci, shodu bajtů, ochranu obou verzí při konfliktu a ignorování nesouvisejícího
nečitelného historického JSON z jiného roku. Všechny přesunuté JSON byly znovu
validovány. Nesouvisející necommitované soubory zůstaly beze změny.
