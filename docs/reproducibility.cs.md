[EN](reproducibility.md) · **CZ** · [Projekt](../README.cs.md)

# Lokální reprodukovatelnost

Postup je ověřen proti skriptům a konfiguraci repozitáře. **Úplná sekvence Docker → seed → ML nebyla při auditu 22. 10. 2026 spuštěna**, protože Docker daemon nebyl dostupný. Příkazy nejsou potvrzeným integračním testem. [Výsledky ověření](documentation-audit.cs.md) oddělují provedené kontroly od neověřených kroků.

## 1. Požadavky a verze

Použijte jednorázové lokální prostředí s Gitem, běžícím Docker Engine/Desktop, Compose, curl s `--fail-with-body` (7.76+) a Pythonem 3 pro tajný klíč. Ukázky předpokládají Bash/zsh na macOS/Linuxu; kvůli funkci `dc` a proměnným ponechte stejný shell. GPU není potřeba. Požadavky na RAM/disk nebyly měřeny.

Backendový Dockerfile a CI používají Python **3.12**, frontendový Dockerfile a [`.nvmrc`](../frontend/.nvmrc) Node **20**. Pro testy na hostiteli potřebujete tyto verze; `nvm use` předpokládá nainstalované nvm. Pro Docker start hostitelský Node nepotřebujete. Syntaxe Compose byla ověřena verzí **5.3.1**, která není stanovena jako minimum. MongoDB, Mailpit a nginx používají proměnlivé tagy a Python závislosti nejsou uzamčené. Frontend má `package-lock.json` a používá `npm ci`.

## 2. Klon a záznam verze

Použijte nový klon či čistý worktree a uložte `git rev-parse HEAD` s výsledky. Veřejný clone příkaz vybírá výchozí větev; pokud dokumentační větev není sloučena, vyberte posuzovanou větev/commit. Příklad pro nový klon nemá přepisovat existující `.env`.

```bash
git clone https://github.com/adelaleppeltova/firesport-app.git
cd firesport-app
git rev-parse HEAD
cp backend/.env.example backend/.env
python3 - <<'PYSECRET'
from pathlib import Path
import secrets
p = Path("backend/.env")
p.write_text(p.read_text().replace("replace-with-a-random-secret", secrets.token_urlsafe(64)))
PYSECRET
```

## 3. Konfigurace před spuštěním

Příkaz nahrazuje zástupnou hodnotu náhodným URL-safe tajemstvím ze 64 bajtů a nevypisuje je. `.env` je ignorován Gitem. Uchovejte jej soukromě; nesdílejte výstup rozbalené konfigurace obsahující tajemství.

[`app/__init__.py`](../backend/app/__init__.py) volá `load_dotenv()` před načtením autentizace. Připojení backendu zpřístupní `backend/.env` jako `/app/.env`; [`auth.py`](../backend/app/services/auth.py) čte `SECRET_KEY` z výsledného prostředí a při importu odmítá chybějící/zástupné hodnoty. Compose nemá explicitní `env_file`.

Existující hodnoty prostředí mají přednost před `.env`: Compose dodává `MONGO_URL=mongodb://mongo:27017`, SMTP Mailpit a `FRONTEND_URL=http://localhost:3000`. Název databáze je v kódu pevně `firesport`. Příklad obsahuje i expirace tokenů. Pro běh přímo na hostiteli je třeba vhodně exportovat MongoDB URI; pořadí inicializace modulů není obecným systémem konfigurace. Preferujte tento Docker postup.

## 4. Izolovaný projekt Compose

Seed je destruktivní. Samotný název projektu neizoluje pevné `container_name` v repozitáři, proto dočasný override přejmenuje **všechny čtyři služby** a nový projekt získá vlastní `mongo-data` volume. Ověřte, že název projektu dosud neexistuje. Dvě vypsané hodnoty si uchovejte pro pozdější připojení. Porty hostitele 3000, 8000, 5679, 27017, 1025 a 8025 musejí být volné; přejmenování kontejnerů je nemění.

```bash
export FLAMMA_REPRO_PROJECT="flamma-repro-$(date +%s)"
FLAMMA_REPRO_OVERRIDE="$(mktemp /tmp/flamma-repro.XXXXXX)"
cat > "$FLAMMA_REPRO_OVERRIDE" <<'YAML'
services:
  backend:
    container_name: ${FLAMMA_REPRO_PROJECT}-backend
  frontend:
    container_name: ${FLAMMA_REPRO_PROJECT}-frontend
  mongo:
    container_name: ${FLAMMA_REPRO_PROJECT}-mongo
  mailpit:
    container_name: ${FLAMMA_REPRO_PROJECT}-mailpit
YAML
dc() {
  docker compose -p "$FLAMMA_REPRO_PROJECT" -f docker-compose.yml -f "$FLAMMA_REPRO_OVERRIDE" "$@"
}
printf '%s\n' "$FLAMMA_REPRO_PROJECT" "$FLAMMA_REPRO_OVERRIDE"
dc config --quiet
dc up --build -d
dc ps
dc logs --tail=80 backend
curl --fail-with-body http://localhost:8000/
```

Očekávaná odpověď kořene API je `{"message":"Firesport API"}`. Start čeká na MongoDB a vytváří indexy. `IMPORT_DATA=false` znamená, že nová databáze nemá importované sportovní výsledky. Spuštění může trvat; zkontrolujte log a po připravení backendu zopakujte požadavek. Připojené adresáře backendu a dat stále odkazují na tento checkout; izolují se databázové volume a názvy kontejnerů.

## 5. Služby

| Služba | Lokální URL |
| --- | --- |
| React aplikace | [localhost:3000](http://localhost:3000) |
| Kořen FastAPI | [localhost:8000](http://localhost:8000) |
| Swagger / OpenAPI | [/docs](http://localhost:8000/docs) / [/openapi.json](http://localhost:8000/openapi.json) |
| ReDoc | [/redoc](http://localhost:8000/redoc) |
| Mailpit schránka | [localhost:8025](http://localhost:8025) |

MongoDB je zveřejněno na portu 27017, SMTP Mailpit na 1025 a při `DEBUG=true` debugpy na 5679. Jde o lokální vývojovou konfiguraci s reloadem, nikoli hotové produkční nasazení. Importní a ML zápisové endpointy nemají autentizační závislost; stack veřejně nezpřístupňujte.

## 6. Import verzovaných dat

**Pouze v izolovaném jednorázovém projektu výše:** tento příkaz ihned vyprázdní `results`, `competitions`, `athletes`, `categories`, `anomaly_runs` a `anomaly_scores`, ještě před kontrolou `/app/data`. Ponechá `users`, takže dřívější párování účtů může přestat platit. Nepoužívejte jej na existující sadě, kterou potřebujete zachovat.

```bash
dc exec backend python /app/scripts/load_data.py
```

[Seed](../backend/scripts/load_data.py) rekurzivně prochází seřazené JSON v `/app/data`. Pro tento snapshot očekávejte nalezení 329 souborů, logy jednotlivých importů a závěrečný souhrn. Kontrolujte `errors`: skript může skončit i s chybami souborů či výsledků. Neočekávejte přesně 13 854 vložených výsledků ani počty historického volume. Normalizace, párování a deduplikace je mění. Alternativní import jediného souboru bez mazání seedem:

```bash
curl --fail-with-body -F 'file=@data/2019/beloves/komplet.json' \
  http://localhost:8000/v1/data/import
```

Jde o alternativu, nikoli povinný import navíc po seedu. Kontrolujte `data.errors` a `data.results_created`; `success=true` nezaručuje import každého řádku. Varianta s tělem JSON používá `POST /v1/data/import/raw`, `Content-Type: application/json` a obsah stejného souboru.

## 7. Kontrola záznamů a dořešení identit

```bash
dc exec mongo mongosh firesport --quiet --eval '
for (const c of ["athletes", "competitions", "categories", "results", "anomaly_runs", "anomaly_scores"]) {
  print(c + ": " + db.getCollection(c).countDocuments({}));
}
print("eligible without athlete: " + db.results.countDocuments({
  final_time_status: "valid", final_time: {$ne: null}, athlete: {$exists: false}
}));
printjson(db.results.findOne({}, {imported_athlete: 1, match_status: 1, match_reason: 1, final_time: 1, quality_flag: 1}));
'
```

Dotazy jsou pouze čtecí. `eligible without athlete` musí být před ML **nula**: výběr takové výsledky zahrnuje, ale seskupení předpokládá `athlete`. Nejisté výsledky nemažte jen kvůli spuštění ML. Zkontrolujte `match_status`, `match_reason` a `imported_athlete` a podle zdrojů proveďte administrační přiřazení či vytvoření atleta.

Existují `GET /v1/admin/import/review`, `POST /v1/admin/results/{result_id}/assign-athlete` s `{"athlete_id":"..."}` a `POST /v1/admin/results/{result_id}/create-athlete`. Vyžadují administrátorský Bearer token. Registrace v UI vytváří běžného uživatele; dokumentovaný automatický bootstrap prvního administrátora chybí. Přidělení role vyžaduje lokální databázové rozhodnutí vlastníka. Schémata uvádí [Swagger](http://localhost:8000/docs). Jde o ruční závislost reprodukce. Pokud ji nelze vyřešit, analytickou sekvenci zastavte a zaznamenejte překážku; úspěšný běh nad nedotčeným čerstvým importem není zaručen.

## 8. Spuštění a přepočet detekce

Po úspěšné kontrole z předchozího kroku:

```bash
curl --fail-with-body -X POST 'http://localhost:8000/v1/ml/recompute-yearly?force=false'
curl --fail-with-body 'http://localhost:8000/v1/ml/windows'
dc exec mongo mongosh firesport --quiet --eval '
printjson(db.anomaly_runs.findOne({}, {run_id: 1, window: 1, model: 1, stats: 1}));
printjson(db.anomaly_scores.findOne({}, {athlete_id: 1, result_id: 1, run_id: 1, score: 1, is_anomaly: 1, direction: 1}));
'
```

Pro zdrojový rozsah generátor zkouší sedm prosincových anchorů 2019–2025, včetně prosince 2025, i když poslední soutěž je z října. Kontrolujte `computed`, `skipped_existing`, `failed` a stav/počítadla každé položky. Vypočtené okno nemusí mít skóre, pokud žádná skupina nesplní podmínky. `processed` a `skipped` počítají skupiny závodník/kategorie, nikoli řádky výsledků.

Po změnách dat či identit výslovně nahraďte existující výstupy:

```bash
curl --fail-with-body -X POST 'http://localhost:8000/v1/ml/recompute-yearly?force=true'
```

Požadavek označí staré běhy jako nahrazené a smaže jejich skóre; není pouze čtecí. Volitelné datumové parametry jsou `from` a `to`, například `&from=2023-01-01&to=2025-12-31`. Běžný import ML automaticky neaktualizuje.

## 9. Čtení API a zobrazení v aplikaci

Vyberte skutečně skórovaného závodníka:

```bash
FLAMMA_ATHLETE_ID="$(dc exec -T mongo mongosh firesport --quiet --eval 'const s=db.anomaly_scores.findOne(); if(s) print(s.athlete_id.toString());')"
if [ -n "$FLAMMA_ATHLETE_ID" ]; then
  curl --fail-with-body "http://localhost:8000/v1/ml/windows?athlete_id=$FLAMMA_ATHLETE_ID"
  curl --fail-with-body "http://localhost:8000/v1/athletes/$FLAMMA_ATHLETE_ID/anomalies"
fi
```

Seznam oken obsahuje `run_id`, anchor, hranice a popisek. Odpověď anomálií obsahuje metadata běhu a skórované položky; kontrolujte `score`, `is_anomaly`, `direction` a doplněné příznaky kvality. Výchozí volba bere nejnovější aktivní běh globálně. Pokud závodník v něm skóre nemá, předejte `run_id` z jeho seznamu oken. Prázdný seznam není důkaz běžného výkonu, ale absence vhodných uložených skóre. Na stránce statistik vyberte závodníka, kategorii a období. Viz [interpretace ML](ml-baseline.md).

## 10. Testy a EDA

```bash
# From the repository root
python3.12 -m venv backend/.venv
. backend/.venv/bin/activate
(cd backend && python -m pip install -r requirements-dev.txt)
(cd backend && python -m ruff check app main.py scripts)
(cd backend && python -m pytest app/tests)
deactivate

cd frontend
nvm use
npm ci
npm run lint
CI=true npm test -- --watchAll=false
npm run build
cd ..
```

Backendové unit testy používají náhrady databáze a nevyžadují běžící MongoDB. Příkazy odpovídají [CI](../.github/workflows/ci.yml); instalace závislostí potřebuje síť. Čerstvé `npm ci` nebylo při auditu provedeno, frontendové kontroly používaly existující závislosti. Backendové kontroly běžely na Pythonu 3.13, protože 3.12 nebyl lokálně dostupný; výsledky a hranice uvádí audit. [EDA závislosti a pořadí buněk](notebooks/README.cs.md) mají samostatný popis.

## 11. Vypnutí, persistence a bezpečný úklid

```bash
dc stop        # retain containers and data; resume with dc start
dc down        # remove this project's containers/network, retain its named volume
```

V novém shellu obnovte uložené `FLAMMA_REPRO_PROJECT`, `FLAMMA_REPRO_OVERRIDE` a definici `dc`. Nový timestamp vytvoří jiné volume, neotevře původní data. Dočasný override nemažte, dokud se potřebujete připojovat.

Pro **nevratné smazání databáze právě tohoto jednorázového projektu** nejprve ověřte projekt a volume:

```bash
dc config --volumes
docker volume ls --filter "label=com.docker.compose.project=$FLAMMA_REPRO_PROJECT"
# Teprve po ověření jednorázového projektu:
dc down --volumes
rm "$FLAMMA_REPRO_OVERRIDE"
```

Při auditu nebylo žádné volume smazáno. Nepoužívejte plošné promazávání Docker volumes.

## 12. Řešení potíží a hranice reprodukce

| Projev | Kontrola / postup |
| --- | --- |
| Chyba socketu či nedostupný Docker daemon | Spusťte Docker a ověřte `docker info`; bez něj nelze ověřit import. |
| Konflikt názvů či portů | Override řeší pevné názvy; uvolněte nebo výslovně přemapujte porty v izolovaném prostředí. |
| `SECRET_KEY must be set...` | Zkontrolujte `backend/.env`, nahrazení placeholderu a připojení backendu. Proměnná shellu se sama automaticky do Compose nepředává. |
| Nedostupná MongoDB | Kontejner používá URI s `mongo`, nikoli localhost; databáze se pevně jmenuje `firesport`. |
| Prázdné seznamy po startu | Seed je vypnutý; ověřte importní log a počty. |
| Admin vrací 401/403 | Je třeba Bearer token a vlastníkem přidělená role; registrace vytváří `user`. |
| Selhané ML anchory / chybějící `athlete` | Dořešte validní nespárované výsledky. HTTP úspěch může obsahovat selhané anchory. |
| Chybějící okna/skóre nebo stará analýza | Zkontrolujte podmínky a vynechané skupiny; po změně dat použijte `force=true`. |
| Selhání hashování hesla mimo localhost | Web Crypto potřebuje bezpečný kontext; lokálně používejte localhost, navržené nasazení potřebuje HTTPS. |
| Node/npm hlásí `Bad CPU type` | Použijte binárku pro architekturu počítače a ověřte PATH / `node --version`. |

Původní stav databáze nelze přesně rekonstruovat: chybí volume, účty a ruční změny identit. Extrakci nelze zopakovat bez listin, nástrojů a URL. Python závislosti a obrazy nejsou uzamčené; seed 42 sám negarantuje shodná skóre. Kvalita při importu závisí na pořadí/cache a analýzu mohou ovlivnit nestandardní či ne-konečné hodnoty a částečné zápisy. Běhy nejsou transakčně archivované. EDA příznaky se liší od aplikace. Chybějí rozhodnutí o licencích a zdrojích i formální citační metadata; viz [data](data-baseline.md), [ML](ml-baseline.md) a [audit](documentation-audit.cs.md).
