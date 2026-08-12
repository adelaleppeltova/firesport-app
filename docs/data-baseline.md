# Data baseline

Tento dokument zachycuje současný datový stav M0. Popisuje verzované vstupy, MongoDB kolekce a importní pravidla; není datovým katalogem ani výsledkem nové analýzy.

## Zdroje dat

Vstupem jsou strukturované JSON soubory v `data/<rok>/<soutěž>/*.json`, vytvořené ze zdrojových výsledkových listin. Pokrývají roky 2019–2025 a zejména disciplínu běh na 100 m s překážkami. Obsahují metadata soutěže, kategorie a jednotlivé výsledky: závodníka, tým, rok narození, FS kód, startovní číslo, pokusy, finální čas, stav času a pořadí.

Každý verzovaný soubor má pole `source_file` s názvem původního souboru a `generated_at`; řada souborů obsahuje také `warnings` a `parsing_notes`. Původní výsledkové listiny ani jejich URL však v repozitáři nejsou, takže přesnou externí provenienci nelze pouze z repozitáře znovu ověřit.

Reprodukovatelný obsah adresáře `data` v této baseline:

- 329 JSON souborů,
- 394 bloků kategorií,
- 13 854 zdrojových výsledkových řádků,
- datum soutěží od 2019-05-04 do 2025-10-04.

Jeden JSON soubor nemusí odpovídat jedné unikátní soutěži: více souborů může obsahovat různé kategorie stejné soutěže.

## Hlavní databázové kolekce

MongoDB databáze se jmenuje `firesport`. Vazby jsou spravované aplikačním kódem; MongoDB schéma ani referenční integrita nejsou vynucené databázovou validací.

| Kolekce | Účel | Nejdůležitější pole a vazby |
| --- | --- | --- |
| `athletes` | Sjednocené identity závodníků. | `first_name`, `last_name`, volitelný `birth_year`, pole `fs_codes` a `teams`, `is_active`, případně `merged_into_athlete_id`; na atleta odkazují `results.athlete`, `anomaly_scores.athlete_id` a volitelně `users.athlete_id`. |
| `competitions` | Soutěže a jejich základní metadata. | `name`, `place`, `date`, `league`, `created_at`; na soutěž odkazuje `results.competition`. |
| `categories` | Kategorie výsledkové listiny. | `name`, volitelný `discipline`, `created_at`; na kategorii odkazuje `results.category`. |
| `results` | Jeden závodní výsledek v konkrétní soutěži a kategorii. | Odkazy `athlete` (volitelný), `competition` a `category`; dále `date`, `team`, původní `imported_athlete`, `match_status`, `match_reason`, `start_number`, `times`, `final_time`, `final_time_status`, `rank`, `quality_flag` a časová razítka. |
| `anomaly_runs` | Metadata jednoho přepočtu ML pro časové okno. | `run_id`, `created_at`, `window_type`, `window`, `model`, `status`, agregované `stats`; starší nahrazený běh může mít `is_superseded` a `superseded_at`. |
| `anomaly_scores` | Skóre jednotlivých výsledků vytvořená ML během. | `run_id`, `athlete_id`, `result_id`, `competition_date`, `final_time`, `score`, `median_time`, `is_anomaly`, `direction`, `contamination_mode`, `category_group`; propojuje běh, atleta a původní výsledek. |
| `users` | Uživatelské účty a autentizační stav. | `email`, `hashed_password`, `role`, `is_active`, `created_at`, `refresh_tokens`, volitelný `athlete_id`; při obnově hesla dočasně také resetovací identifikátor a expirace. |

Odkazy z `results` a `anomaly_scores` používají převážně MongoDB `ObjectId`. `users.athlete_id` je v současném kódu ukládán jako řetězec.

## Import dat

Import zajišťuje `DataImporter` v `backend/app/services/data_import.py`. Data lze dodat jako nahraný JSON (`/v1/data/import`), JSON tělo (`/v1/data/import/raw`), administrátorský hromadný import (`/v1/admin/import`) nebo volitelný Docker seed přes `backend/scripts/load_data.py`.

Seed se spouští jen při `IMPORT_DATA=true`; výchozí `docker-compose.yml` používá `false`. Před seedem skript vyprázdní `results`, `competitions`, `athletes`, `categories`, `anomaly_runs` a `anomaly_scores`, nikoli `users`.

### Normalizace

- datum soutěže se převádí z `YYYY-MM-DD` na `datetime` a `league` na seznam řetězců,
- názvy kategorií dostávají jednotnou kapitalizaci; `HZS` zůstává velkými písmeny,
- ze jména týmu se odstraňuje `SDH`, upravuje se kapitalizace a zachovávají se vybrané zkratky,
- jména závodníků se oříznou a normalizuje se velikost písmen,
- FS kód se převádí na oříznutý řetězec,
- pokusy se při uložení mapují z pole `try` na `attempt`,
- vstupní hodnota roku narození `0` se při importu chápe jako chybějící údaj.

Pole `source_file`, `generated_at`, `warnings`, `parsing_notes` a vstupní `district` se do hlavních databázových dokumentů tímto importerem nepřenášejí.

### Párování závodníků

Párování pracuje pouze s aktivními atlety a postupně vyhodnocuje normalizované jméno, rok narození, tým a FS kód. Jednoznačná shoda jména a roku narození se páruje automaticky; při chybějícím roku lze automaticky použít jedinou shodu jména a týmu. Více kandidátů nebo pouze slabá shoda vede na `needs_review`. Chybějící jméno či žádná shoda vede na `unmatched`; pokud jsou jméno a příjmení k dispozici, importer pro takový výsledek vytvoří nového atleta a výsledek označí jako spárovaný.

Při úspěšné shodě může být existující atlet doplněn o dosud chybějící rok narození, FS kód nebo tým. Nejednoznačné výsledky lze následně řešit v administraci ručním přiřazením, vytvořením atleta nebo sloučením duplicitních identit.

### Deduplikace výsledků

Soutěž se znovu použije při shodě `name`, `place` a `date`; kategorie primárně při shodě názvu, včetně kontroly bez ohledu na velikost písmen. Výsledek se před vložením hledá podle soutěže, kategorie, importovaného jména a příjmení a startovního čísla; je-li dostupný rok narození nebo FS kód, přidává se i do tohoto dotazu. Pro výsledky není definován unikátní databázový index, takže jde o aplikační deduplikační pravidlo, nikoli úplnou garanci unikátnosti.

### Quality flag

Při importu se do `results.quality_flag` ukládá `ok` nebo `suspicious`. Kontrola používá validní finální časy ve stejné konkrétní kategorii: čas mimo hranice odvozené z 1. a 99. percentilu, omezené absolutním intervalem 11–45 s, je podezřelý. Druhé pravidlo označí čas, který je více než o 25 % horší než medián posledních pěti dřívějších validních výsledků stejného atleta ve stejné kategorii. Invalidní nebo chybějící finální čas dostává `ok`. Quality flag lze také hromadně přepočítat službou `recompute_quality_flags`.

## Počty v lokální databázi

Read-only kontrola právě běžícího lokálního Docker volume dne 12. 8. 2026 zjistila:

| Kolekce | Počet |
| --- | ---: |
| `athletes` | 4 350 |
| `competitions` | 65 |
| `categories` | 13 |
| `results` | 13 785 |
| `anomaly_runs` | 21 |
| `anomaly_scores` | 5 477 |
| `users` | 9 |

Tyto hodnoty jsou pouze snapshot lokálního perzistentního volume. Volume není verzované, běžný Docker start data automaticky neseeduje a import i uživatelské operace jeho obsah mění. Počty databázových kolekcí proto nejsou součástí reprodukovatelného repository baseline. Z 21 lokálních ML běhů bylo 7 aktivních a 14 označených jako nahrazené.

## Doložená omezení dat

- Původní zdrojové soubory nejsou v repozitáři; k dispozici je jen jejich název a poznámky v odvozeném JSON.
- Vstupní data nejsou úplná ve všech identifikačních polích: 6 233 zdrojových řádků má chybějící nebo nulový rok narození a 6 155 nemá FS kód.
- Ve zdrojových datech je 504 výsledků s jiným stavem než `valid`; 26 z 394 bloků kategorií nemá explicitní `discipline`.
- Ruční `warnings` a `parsing_notes` dokládají rozdíly ve formátu a kvalitě původních výsledkových listin, ale importer je neukládá do MongoDB.
- Párování a deduplikace jsou heuristické. Nejednoznačné identity zůstávají k administrátorské kontrole a databáze nevynucuje unikátnost výsledků.
- Počty v lokální MongoDB nelze odvodit jen z klonu repozitáře bez explicitního čistého importu a stejné historie následných změn.
