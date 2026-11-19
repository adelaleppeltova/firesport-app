# Kanonické kategorie a migrace MongoDB

[Následná analýza historických kategorií a duplicit](category-migration-review.cs.md) obsahuje novější dry-run a doplnění postupu pro doložené duplicity.

## Dopad a výsledky analýzy

Dne 18. 11. 2026 proběhl dry-run nad běžící projektovou MongoDB `firesport` na localhostu. Použil pouze výpis kolekcí a čtení dokumentů. Produkční migrace čeká na schválení. Zápisový scénář byl ověřen v izolované MongoDB se syntetickými výsledky.

| Kontrola | Počet |
| --- | ---: |
| Stávající kategorie | 90 |
| Automaticky převoditelné / vyžadující kontrolu jednotlivých řádků / nejednoznačné / nepodporované kategorie | 20 / 44 / 19 / 7 |
| Kanonické kategorie po migraci | 22 |
| Historické výsledky před migrací i po ní | 25 951 |
| Aktivní po migraci | 21 244 |
| Z toho bezpečně zařazené bez individuálního rozdělení | 19 655 |
| Výsledky posuzované jednotlivě kvůli ročníku či rozdělení kategorie | 3 678 |
| Výsledky ke kontrole | 4 641 |
| Výsledky archivované pro disciplínu `vez` | 66 |
| Dotčené soutěže / přiřazení závodníci | 119 / 4 422 |
| Skupiny možných duplicit výsledků / shodných názvů kategorií | 396 / 10 |
| Chybějící reference na soutěž, kategorii nebo přiřazeného závodníka | 0 |

Detailní místní report `.extraction-diagnostics/category-migration/mongodb-dry-run-final.json` obsahuje všech 90 variant, počty výsledků a přiřazených závodníků po kategoriích, cílové kategorie, odkazované identifikátory a seznam řádků k rozhodnutí. Počet přiřazených závodníků vychází ze skutečných referencí na profily. Export je uložený mimo verzovaná data. Dvě kategorie družstev jsou součástí katalogu. Projektová data v tomto dry-runu neposkytla průkaznou družstevní výsledkovou listinu, kterou by plán do těchto kategorií zařadil.

### Co vyžaduje rozhodnutí

| Počet | Důvod a podklad pro kontrolu |
| ---: | --- |
| 1 765 | Smíšená nebo obecná kategorie 100 m bez spolehlivého ročníku či doloženého individuálního řádku. Ověřit ročník a strukturu původní listiny. |
| 982 | Neověřený systém 60 m, např. názvy s označením A/B bez rozmezí. Dohledat pravidla konkrétního ročníku či výsledkovou listinu. |
| 905 | Rozmezí 60 m se liší od schválených rozmezí nebo je v rozporu s kategorií. Případy 6–8 let zahrnují i šestileté závodníky. |
| 525 | Jinak bezpečně zařaditelné řádky v možných duplicitách. Porovnat publikované listiny a potvrdit identitu případných samostatných startů. Plán uchovává všechny řádky. |
| 389 | Doložený ročník nesouhlasí s přesným kanonickým rozmezím. Ověřit ročník a skutečná pravidla závodu. |
| 29 | U kategorie 100 m chybí věkové rozmezí nebo doložené pohlaví, např. u označení `Střední dorost`. |
| 24 | Zdánlivě platný výsledný čas odpovídá možnému zástupnému času. Ověřit oficiální listinu. Čas a stav zůstávají uložené. |
| 21 | Jednotlivý výsledek nesplňuje publikované nebo kanonické rozmezí kombinované kategorie. |
| 1 | Řádek s klubem bez identifikace osoby a bez spolehlivého doložení družstevní výsledkové listiny. |

## Datový model a chování

- `app/category_catalog.py` definuje ID, názvy, disciplíny, pohlaví, věk, typ a systém rozdělení. Každý stabilní klíč má deterministické MongoDB ObjectId. Kolekce `canonical_categories` má povolený přesný obsah a unikátní index klíče. Import katalog pouze čte.
- Aktivní `results.category` odkazuje do `canonical_categories`. `results.discipline` a `results.result_type` určuje klasifikace. U stavů `review` a `unsupported` je aktivní odkaz prázdný. Originální odkaz a dostupné jméno, disciplínu, rozsah a příslušnost ukládá `source_category`. Historická kolekce `categories` slouží jako archiv. Původní identifikátor výsledku, pokusy, časy, stav a pořadí zůstávají zachované.
- `app/services/category_normalization.py` normalizuje zápis a zachovává rozdíl mezi čtyřmi obecnými a osmi přesnými kategoriemi 60 m. Samotný ročník obecné kategorie nerozděluje. U individuálních kombinací 100 m používá rozdíl roku soutěže a zdrojového ročníku narození. Pohlaví získává z doložené kategorie nebo z explicitních údajů. Družstvo vyžaduje prokazatelnou formu řádku a postupový závod. Jmenovité řádky skupiny `Muži HZS` v doloženém kontextu MČR v požárním sportu přiřazuje k mužům a zachovává příslušnost HZS.
- `app/extraction/` uchovává původní popisy podle stávajícího JSON schématu. Schéma dovoluje zachytit historické nebo nepodporované disciplíny pro audit. Databázový import v `app/services/data_import.py` takové řádky izoluje a zachovává také přesný vstupní řádek. U starých MongoDB záznamů je zdrojový název zapsán v podobě, v jaké se dochoval v databázi.
- Veřejná API, profily a statistiky používají aktivní katalog. Osobní rekord v každé disciplíně bere nejnižší platný oficiální individuální čas napříč kategoriemi. Přehledy sezón, trend a stabilita jsou filtrovány podle disciplíny. Skóre modelu z doby před zavedením katalogu zůstávají v databázi a nové API zobrazí nové výpočty. Frontend zobrazuje disciplínu, schválenou kategorii a původní skupinu s publikovaným pořadím.
- Admin má stránkovaný přehled nevyřešených klasifikací v `/v1/admin/import/category-review`. Změny sportovního zařazení podložte původní listinou a schváleným plánem. U stávajících závodů bez doložené shody URL může import zastavit konflikt identity události k ručnímu ověření.
- `scripts/fix_final_times.py` pouze kontroluje konzistenci zapsaného výsledného času. Oficiální čas se přebírá ze zdroje.

## Přehled změn a ověření

- Backendové modely v `app/models/`, filtry v `app/services/{results,competitions,athletes}.py` a související routery API používají stabilní identitu kategorií a výslovné disciplíny. `app/db/database.py` přidává index výsledků podle klasifikace, disciplíny, kategorie a soutěže.
- Výkonnostní výpočty v `app/services/{anomaly_service,quality_flag_service}.py`, `app/ml/anomaly_config.py` a API anomálií odvozují údaje z aktivních individuálních výsledků. Správa importu používá `app/services/admin.py` a oddělené přehledy pro párování osob a klasifikaci kategorií.
- Frontendové stránky závodů, výsledků, profilu, statistik a administrace používají ověřené možnosti z API. `DisciplineSelect.jsx` načítá seznam disciplín z katalogu a `groupResultLists.js` seskupuje původní listiny při zachování pořadí.
- Regresní testy jsou v `app/tests/test_category_catalog.py`, `app/tests/test_incremental_import.py` a `frontend/src/utils/groupResultLists.test.js`. Ověřeny byly lint a testy backendu i frontendu, produkční build frontendu a integrační scénář MongoDB s přerušením, opakováním, validátorem katalogu a oddělenými rekordy.

## Schválení a bezpečný postup

1. Ověřte cílovou instanci a verzi kódu. Zastavte backend, periodické úlohy, importy i další zapisující klienty. Zachovejte servisní okno do ověření výsledků. Nové API očekává dokončenou migraci a záznamy bez klasifikace před migrací nezobrazuje.
2. Po zastavení zápisů zálohujte databázi včetně všech kolekcí a indexů. Použijte chráněné konfigurační soubory s připojením, dostupné pouze operátorovi, a uzavřený adresář záloh. Ověřte kontrolní součet a plně obnovte kopii do prázdné izolované instance. Porovnejte počty, indexy a vzorky původních výsledků. [MongoDB mongodump](https://www.mongodb.com/docs/database-tools/mongodump/) · [MongoDB mongorestore](https://www.mongodb.com/docs/database-tools/mongorestore/)

   ```bash
   umask 077
   mongodump --config "$DUMP_CONFIG" --db firesport --gzip --archive="$BACKUP"
   shasum -a 256 "$BACKUP" > "$BACKUP.sha256"
   shasum -a 256 -c "$BACKUP.sha256"
   mongorestore --config "$RESTORE_TEST_CONFIG" --gzip --archive="$BACKUP" --nsInclude='firesport.*'
   ```

3. Ze stejné zastavené databáze pořiďte nový snímek a dry-run. Spusťte z adresáře `backend/` s `CATEGORY_MIGRATION_READ_URI` nastaveným na připojení pouze pro čtení. Výstupní soubory se vytvářejí s oprávněním `0600` a musí mít nové cesty.

   ```bash
   python -m scripts.migrate_category_catalog --dry-run --live-read-only \
     --database firesport --save-snapshot "$SNAPSHOT" --report "$REPORT"
   ```

   Na ověřené kopii proveďte zkušební aplikaci téhož plánu a porovnejte počty dokumentů, referenční integritu, vzorky pořadí a časů, konfiguraci indexů a API. Přezkoumejte ruční případy i očekávaný počet veřejných výsledků. Po změně pravidel znovu sestavte plán. Schvalte aktuální `plan_sha256` z nového reportu.

4. Po výslovném schválení nastavte `CATEGORY_MIGRATION_WRITE_URI` na cílovou instanci a spusťte následující příkaz ze stejné verze kódu a s původním schváleným snímkem.

   ```bash
   python -m scripts.migrate_category_catalog --apply --database firesport \
     --snapshot "$SNAPSHOT" --approve-plan "$APPROVED_PLAN_SHA256"
   ```

   Skript zkontroluje celý cílový obsah proti snímku, vytvoří validovaný katalog a podmíněně aktualizuje jednotlivé dokumenty. Žádný historický dokument nemaže. Při přerušení neobnovujte provoz. Opakujte příkaz se stejným snímkem a otiskem. Akceptovány jsou původní řádky a řádky už aktualizované přesně podle plánu. Při jiné změně skript zastaví.

5. Po úspěšném dokončení spusťte druhý dry-run nad cílem do nového souboru. Ověřte 22 kanonických kategorií, nulu plánovaných oprav referencí, shodné počty výsledků a stejné platné výsledné časy, pokusy i pořadí. Po nasazení ověřte filtry, družstva, archiv `vez`, oba osobní rekordy a přepočítejte odvozené statistiky podle nové verze katalogu. Pro starší databázi ponechte archivní snímek k dohledání výsledků. Přepočet spusťte ještě v servisním okně se správným `MONGO_URL` v prostředí backendu.

   ```bash
   python - <<'PY'
   import asyncio
   from app.db.database import get_db
   from app.services.anomaly_service import recompute_yearly_batch
   from app.services.quality_flag_service import recompute_quality_flags

   async def main():
       db = get_db()
       print(await recompute_quality_flags(db))
       print((await recompute_yearly_batch(db)).model_dump())

   asyncio.run(main())
   PY
   ```
6. Pokud je potřeba návrat, ponechte servisní okno a ověřenou zálohu obnovte do nové izolované instance. Proveďte shodné kontroly počtů a vzorků. Předchozí verzi aplikace přepojte na ověřenou obnovenou instanci až po schválení operátorem. Uchovejte migrovanou instanci pro porovnání. Pokud mezitím vznikly nové zápisy, nejdříve je identifikujte a schvalte jejich případný přenos.

Stejný postup s prázdným snímkem slouží k inicializaci úplně nové databáze před prvním importem.
