# První import: závod 1034

Ověřený zdroj: https://pozarnisporty.cz/races/1034.
Živé HTML a 412 propojených veřejných profilů bylo načteno při importu
13. 11. 2026. JSON byl vygenerován v `2026-11-13T22:10:05Z`.

Původní výstup: `data/results/a7bb4dd25257b4f5.json`. Tento soubor zatím zůstává
v původním umístění kvůli konfliktu s odlišným
`data/2026/chomutov-stimax/komplet.json`; nové importy sem nikdy neukládat.
Podrobnosti: [souhrn migrace](extraction-storage-migration.cs.md).

| Kontrola | Výsledek |
| --- | ---: |
| Zadané URL / úspěšně zpracované závody | 1 / 1 |
| Kategorie | 12 |
| Výsledky | 416 |
| Platné / neplatné / nezveřejněné pokusy | 755 / 77 / 0 |
| Očíslované důvody penalizace | 76 |
| Závodníci s důvodem penalizace | 68 |
| Doplněné / chybějící roky narození | 412 / 4 |
| Chybějící FSCode | 416 |
| Chybějící okres | 416 |
| Nerozdělená nejednoznačná víceslovná jména | 8 |
| Warnings | 36 |
| Chyby strukturální / obsahové validace | 0 / 0 |

Počty kategorií a řádků odpovídají tabulkám i deklarovaným počtům kategorií na
živém zdroji. Počet důvodů odpovídá nezávislému počítání očíslovaných označení v
původních řádcích. Výstup byl znovu porovnán s extrakcí uloženého živého HTML;
všechna pole kromě obohaceného roku narození odpovídají zdrojovým tabulkám.

Všech 412 propojených profilů bylo úspěšně načteno; čtyři další výsledky nemají
odkaz na profil a rok narození není v tabulce. FSCode ani okres nejsou uvedeny.
Kraje nebyly převedeny na okresy, ID profilů nebyla použita jako FSCode. Osm
víceslovných jmen bez jednoznačného oddělení zůstává v first_name/last_name null;
celý původní text je v warnings. Původní pořadí a oficiální výsledné časy byly
zachovány. Prokázané zástupné finální časy 30:00.00 u dvou neplatných pokusů jsou
null/invalid. Další dva sloupce pokusů jsou zaznamenány a ignorovány.

Ověření implementace: 184 backend testů (82 nových extrakčních), backend lint,
frontend test a lint. Lokální frontend kontroly použily dostupný Node 18, protože
místní Node 20 nelze spustit. GitHub CI pro implementační commit `20f45fb4`
úspěšně ověřilo backend na Python 3.12 a frontend na projektovém Node 20, včetně
produkčního buildu. Regresní testy běží bez sítě; skutečný import byl ověřen živě.

Surové HTML a provozní audit zůstávají v ignorovaném adresáři
`.extraction-diagnostics/a7bb4dd25257b4f5/`. Žádný profilový HTML snapshot se
neukládá do Git. Původní nesouvisející necommitované datové soubory nebyly změněny.
