# Konečný audit migrace kategorií

Audit 18. listopadu 2026 porovnal dva čtecí exporty projektové MongoDB kolem vytvoření zálohy a předchozí snímek. Kolekce v rozsahu migrace mají stejná ID i úplný obsah dokumentů jako předchozí snímek. Nepřibyl, nezměnil se ani neubyl žádný dokument v tomto rozsahu. Pro ostatní kolekce předchozí migrační snímek neobsahoval srovnávací podklady. Úplné manifesty celé databáze před zálohou a po ní se shodují.

| Kolekce | Dokumenty | Indexy včetně _id |
| --- | ---: | ---: |
| anomaly_runs | 21 | 3 |
| anomaly_scores | 5 477 | 4 |
| athletes | 4 438 | 4 |
| categories | 90 | 1 |
| competitions | 119 | 1 |
| results | 25 951 | 6 |
| sessions | 0 | 3 |
| users | 9 | 3 |
| canonical_categories | dosud neexistuje | 0 |
| Celkem | 36 105 | 25 |

## Výsledek dry-runu a plánované operace

Otisk V4 z aktuálního exportu se shoduje s předchozím auditem. `df8daa1f6fd6b92a57b49966f19c50daf019ab5229e2e082071ba4cc944e98e4`.

| Stav výsledků | Počet |
| --- | ---: |
| Aktivní | 22 742 |
| Běhy členů družstev | 1 242 |
| Historické skupiny 60 m | 929 |
| K ruční kontrole | 576 |
| Nadbytečné kopie s přímým odkazem | 396 |
| Archiv věže | 66 |
| Celkem původních řádků | 25 951 |
| Řádky po odečtení potvrzených kopií | 25 555 |
| Chybějící reference | 0 |

První čisté spuštění naplánuje 25 951 aktualizací výsledků, 6 aktualizací soutěží včetně uložení 180 oficiálních týmových položek, 22 vložení kanonických kategorií přes upsert, vytvoření jedné kolekce s validátorem a vytvoření jednoho unikátního indexu. Celkem **25 981 příkazů měnících stav**, z nichž 25 979 zapisuje dokumenty a dva nastavují katalog. Plán obsahuje nula smazání. Stávajících 90 původních dokumentů kategorií zůstane dostupných pro audit. Jejich obsah se nemění.

## Identita a osobní rekordy

Pravidla Českého poháru definují FScode v rámci své registrace jako jedinečný a neměnný identifikátor. V lokální databázi je mezi aktivními nesloučenými profily 2 142 různých normalizovaných kódů, z toho 67 má více vlastníků. Samotná hodnota tedy pro zpětnou identifikaci v databázi aplikace nestačí. [Pravidla Českého poháru 2026](https://sport.dh.cz/images/Dokumenty/sport/pozarni-sport/CP/2026/Pravidla_CP_2026.pdf)

Běžný matcher už přijímá také přesné jméno s doloženým shodným ročníkem, pokud zůstane jediný kompatibilní profil. Má i ruční přiřazení. Migrace pro doplňkové rekordy vyžaduje přísnější důkaz. Ruční označení vazby samo o sobě ji pro rekord nedokládá a žádný z 2 171 posuzovaných záznamů nemá zdrojový FSCode. Kontrola platnosti času je v kódu samostatná a absence kódu nemění výsledek ani jeho zdroj. Diagnostická položka `identity_or_source_unverified` ale spojuje dva různé důvody a sama o sobě neurčuje, zda jde o problém zdroje. U družstev zůstává samostatný požadavek na pravidla srovnatelnosti.

Minimální budoucí změna je připustit vedle ověřeného kódu výslovně schválený důkaz ke konkrétnímu výsledku a profilu, například stabilní profilový identifikátor pořadatele potvrzený v registraci i příslušné listině nebo přímé potvrzení pořadatele. Doklad by měl obsahovat odkaz a otisk podkladu, typ důkazu a kdo vazbu schválil. Samotné jméno ani klub nestačí. Platnost času, původ výsledku, duplicity a u družstev srovnatelnost se ověřují samostatně. Pravidla ani vazby se v tomto auditu neměnily.

## Záloha, obnova a návrat

Čtecí `mongodump` vytvořil celý archiv databáze `firesport`. SHA-256 ověřeného archivu je `bbf9770c303f21241ba5388bc3fd47f1250a7567bc777a76a043f1325fb5b7da`. Obnova na samostatné MongoDB stejného obrazu se samostatným dočasným úložištěm zapsala 36 105 dokumentů s nulou chyb. Počty, otisk úplných dokumentů, typy a konfigurace kolekcí i všech 25 indexů se shodovaly pro všech osm kolekcí. U složených indexů bylo zahrnuto i pořadí polí. Archiv i manifesty zůstávají v neveřejné diagnostice s omezenými oprávněními.

V ověřené izolované obnově proběhla skutečná migrace a následné druhé spuštění stejného plánu. Kontrola porovnala všech 25 951 původních ID, pořadí, startovní čísla, časy, pokusy, vazby na závodníky a původní kategorie. Sleduje i přímé cíle 396 duplicit a ověřuje skutečnými MongoDB dotazy, že veřejný a statistický filtr nevrátí žádnou nadbytečnou kopii. Zachovány byly historické skupiny, všech 576 položek k ruční kontrole a oddělení 180 týmových součtů od výkonů členů. Nový katalog měl 22 položek a unikátní index. Opakování zachovalo přesně stejný obsah a nový dry-run naplánoval nula aktualizací.

Pro návrat udržet importy a aplikaci v odstávce. Obnovit zálohu pořízenou těsně před nasazením do čisté náhradní instance MongoDB pod databází `firesport`. Porovnat úplný obsah, kolekce, reference a indexy s manifestem, nasadit původní verzi aplikace a přesměrovat její `MONGO_URL` na náhradní instanci. Tím se po migraci nepřenese nová kolekce katalogu. Zachovat původní migrovanou instanci pro audit. Pokud byl po nasazení povolen provoz se zápisy, před návratem samostatně zajistit novější změny. Obnova předmigračního archivu je nezahrnuje.

## Příkazy pro schválené okno

Pozastavit zapisující části aplikace a importy. Zadat tajné URI v prostředí příslušného účtu a držet zálohy mimo Git. Následující příkazy spouštět z `backend/` s aktivním virtuálním prostředím. Nejdříve použít pouze čtecí variantu a zkontrolovat otisk, doklady a počty.

```bash
set -e
umask 077
P=../.extraction-diagnostics/category-migration
SNAP="$P/approved-window-snapshot.ndjson"
REPORT="$P/approved-window-report.json"
DUPE="$P/verified-duplicate-pairs.json"
TEAM="$P/verified-mcr-standings.json"
INDIVIDUAL="$P/verified-individual-rows.json"

python -m scripts.migrate_category_catalog --dry-run --live-read-only \
  --database firesport --save-snapshot "$SNAP" --report "$REPORT" \
  --evidence "$DUPE" --team-evidence "$TEAM" --individual-evidence "$INDIVIDUAL"
jq '{plan_sha256, counts}' "$REPORT"

# Čtecí záloha současného kontejneru pro právě schválené okno
docker exec firesport-mongodb mongodump --host 127.0.0.1 \
  --db firesport --archive --gzip > "$P/approved-window-backup.archive.gz"
shasum -a 256 "$P/approved-window-backup.archive.gz"
```

Ověřit čerstvý archiv ve výhradně testovací instanci a porovnat manifesty. Při změně otisku nebo dokladů získat nové schválení. Příkaz zápisu používá pevně zadaný schválený otisk. Hodnota v příkladu odpovídá tomuto auditu.

```bash
APPROVED_SHA=df8daa1f6fd6b92a57b49966f19c50daf019ab5229e2e082071ba4cc944e98e4
python -m scripts.migrate_category_catalog --apply --database firesport \
  --snapshot "$SNAP" --approve-plan "$APPROVED_SHA" \
  --evidence "$DUPE" --team-evidence "$TEAM" --individual-evidence "$INDIVIDUAL"

python -m scripts.migrate_category_catalog --dry-run --live-read-only --database firesport \
  --report "$P/post-migration-check.json"
jq '{counts, personal_record_audit}' "$P/post-migration-check.json"
```

Po zápisu očekávat nula dalších aktualizací a nula chybějících referencí. Před obnovením provozu ověřit výsledky a statistiky. Rizikem je zejména souběžný zápis, změna zdrojových dokladů, přerušení vícekolekční operace a nesprávný cíl při obnově. Migrační skript při zápisu kontroluje množinu dokumentů i jednotlivé hodnoty. Za běhu může být stav částečný, proto má odstávka trvat do úplné kontroly. Opakuje se stejný schválený plán nad stejným snímkem.

## Testy

Backend 808 úspěšných testů včetně reálného 24stránkového jihočeského PDF. Frontend čtyři úspěšné testy. Lint obou částí a `git diff --check` prošly.

## Závěr

Plán je technicky připraven ke schválenému produkčnímu spuštění. Nebyl zjištěn blokující problém s obsahem migrovaných kolekcí, obnovitelností zálohy ani opakovatelností. Podmínkou spuštění zůstává schválení a shoda čerstvého snímku a schváleného otisku v okně bez souběžných zápisů. Projektová databáze během auditu sloužila výhradně ke čtení.
