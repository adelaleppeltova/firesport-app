# Import závodů STIMAX CUP 2026: 1031–1033

Import tří uživatelem zadaných URL do samostatných JSON souborů. Každý zdroj byl nově načten; propojené veřejné profily sloužily výhradně k doplnění roku narození. Cache se sdílela pouze během tohoto běhu.

| Závod | Datum | Kategorie | Výsledky | Platné / neplatné pokusy | Důvody penalizace | Chybějící roky narození | Warnings |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [STIMAX CUP 2026 - 1. kolo - Ústí nad Labem](https://pozarnisporty.cz/races/1031) | 2026-04-26 | 12 | 442 | 770 / 114 | 105 | 10 | 51 |
| [STIMAX CUP 2026 - 2. kolo - Lovosice](https://pozarnisporty.cz/races/1032) | 2026-05-09 | 12 | 391 | 705 / 77 | 76 | 7 | 40 |
| [STIMAX CUP 2026 - 3. kolo - Děčín](https://pozarnisporty.cz/races/1033) | 2026-08-29 | 12 | 396 | 719 / 73 | 70 | 5 | 38 |

## Výstupy

- `data/results/6b6d3056fb0aa913.json` — UTC čas generování `2026-11-13T22:30:24Z`; Profiles inspected: 432; failed: 0. Only birth year extracted.
- `data/results/1c9bfcfe2eb34eb4.json` — UTC čas generování `2026-11-13T22:28:42Z`; Profiles inspected: 384; failed: 0. Only birth year extracted.
- `data/results/66e0f6c5dc0e2535.json` — UTC čas generování `2026-11-13T22:25:52Z`; Profiles inspected: 391; failed: 0. Only birth year extracted.

## Ověření

Celkem 36 kategorií, 1229 výsledků a 251 očíslovaných důvodů u 228 výsledkových záznamů. Všechny JSON prošly strukturální i obsahovou validací bez chyb.

Počty kategorií byly porovnány s přepínači kategorií a počty závodníků v každé kategorii se zdrojovými tabulkami. Počty řádků a očíslovaných důvodů byly navíc nezávisle zkontrolovány přímo v původních HTML buňkách. Nová extrakce uložených zdrojů odpovídá všem polím JSON kromě dodatečně ověřeného roku narození. Opakované uložení stejných dat nezměnilo obsah souborů (ověřená idempotence).

Chybí 22 roků narození. FSCode ani okres nejsou v žádném z 1229 výsledků explicitně dostupné; hodnoty jsou null a upozornění jsou agregována podle kategorií. Nejednoznačně rozdělitelných jmen je 30 (výsledkových záznamů, nikoli unikátních osob). Jejich původní text zůstává ve warnings. Neúspěšných načtení profilů: 0.

Oficiální pořadí, výsledné časy, kategorie a přiřazení penalizací byly zachovány. Všechny závody mají osm žákovských kategorií na 60 m a čtyři kategorie dorostu/dospělých na 100 m podle explicitních propozic. Další pokusy se nepromítají do prvních dvou.

Prošlo 184 backendových testů, backend lint, frontendový test a frontend lint. Lokální frontend kontroly použily dostupný Node 18. Formát zdroje nevyžadoval změnu parseru. Surové zdroje a provozní audity zůstávají v ignorovaném adresáři `.extraction-diagnostics/`; profilové HTML se neukládá do Git. Stávající JSON závodu 1034 ani nesouvisející necommitovaná data nebyla změněna.

Další upozornění závodu 1031:

- mladší žáci A – chlapci – od 6 do 8 let / Pinka Matěj (Ústecký) (110) / rank 12.: penalty on valid try 2: obouruč
- starší žáci B – dívky – 14 a 15 let / Kosmová Nikola (Ústecký) (242) / rank 17.: unassigned penalty: 'kladina'
- starší žáci B – chlapci – 14 a 15 let / Souček Matěj (Ústecký) (326) / rank 24.: penalty on valid try 2: rozpojeno
- dorost chlapci + muži – 17 – 100 let / Sobota Milan (Ústecký) (465) / rank 43.: unassigned penalty: 'rozdělovač'
- dorost chlapci + muži – 17 – 100 let / Kitner Sebastian (Ústecký) (461) / rank 44.: unassigned penalty: 'rozdělovač'
- dorost chlapci + muži – 17 – 100 let / Janoušek Karel (Ústecký) (437) / rank 46.: unassigned penalty: 'nenastoupil'
- dorost chlapci + muži – 17 – 100 let / Němec Petr (Středočeský) (435) / rank 48.: unassigned penalty: 'nenastoupil'
