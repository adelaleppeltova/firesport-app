**EN** · [CZ](reproducibility.cs.md) · [Project](../README.md)

# Local reproducibility

This procedure is checked against repository scripts/configuration. **The complete Docker startup → seed → ML sequence was not executed during the 2026-10-22 documentation audit**, because the Docker daemon was unavailable. Do not treat the commands below as a passed integration test. [Validation details](documentation-audit.md) distinguish executed checks from unverified steps.

## 1. Prerequisites and versions

Use a disposable local environment with Git, a running Docker Engine/Desktop, Compose, curl supporting `--fail-with-body` (7.76+), and Python 3 for secret generation. Shell examples target Bash/zsh on macOS/Linux; keep the same shell open for the `dc` function and variables. No GPU is needed. Disk/memory requirements have not been benchmarked.

The backend Dockerfile and CI use Python **3.12**, frontend Dockerfile and [`.nvmrc`](../frontend/.nvmrc) use Node **20**. Host-only tests need those runtimes; `nvm use` assumes nvm is installed. Node is not needed on the host for Docker startup. Compose was syntax-checked with **5.3.1**, not established as a minimum version. MongoDB, Mailpit and nginx images use mutable tags; backend requirements are not pinned. Frontend dependency versions are captured by `package-lock.json` and installed with `npm ci`.

## 2. Clone and record the version

Use a new clone or a clean worktree; record `git rev-parse HEAD` with results. The public clone command checks out the default branch; select the reviewed documentation branch/commit if it has not been merged. Do not overwrite an existing `.env` while following this fresh-clone example.

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

## 3. Understand configuration before startup

The command replaces the example placeholder with a random 64-byte URL-safe secret without printing it. `.env` is ignored by Git. Keep it private and do not share resolved config output containing secrets.

[`app/__init__.py`](../backend/app/__init__.py) calls `load_dotenv()` before auth imports. The bind mount makes `backend/.env` available as `/app/.env`; `SECRET_KEY` is read from the resulting process environment. [`auth.py`](../backend/app/services/auth.py) rejects missing/placeholder secrets at import. Compose does **not** explicitly declare an `env_file`.

Existing environment values override `.env`: Compose supplies `MONGO_URL=mongodb://mongo:27017`, Mailpit SMTP settings and `FRONTEND_URL=http://localhost:3000`. MongoDB database selection is fixed to `firesport` in code. Tokens and expiry options can be configured through the example; host-native execution additionally needs a suitable exported MongoDB URI because module initialization order is not a general settings system. Prefer the documented Docker path.

## 4. Create an isolated Compose project

The seed is destructive. A project name alone does not isolate the repository's fixed `container_name` values, so this temporary override gives **all four services** distinct names and a fresh project-scoped `mongo-data` volume. Verify the generated project name is unused. Record the two printed values if you need to reconnect later. Standard host ports 3000, 8000, 5679, 27017, 1025 and 8025 must be free; container renaming does not change port mappings.

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

Expected root response: `{"message":"Firesport API"}`. Startup waits for MongoDB and creates indexes. `IMPORT_DATA=false` means the new database has no imported sports results. Service startup can take time; inspect logs and retry the root request after the backend is ready. The backend and data bind mounts still reference this checkout; only the database volume and container names are isolated.

## 5. Open services

| Service | Local URL |
| --- | --- |
| React application | [localhost:3000](http://localhost:3000) |
| FastAPI root | [localhost:8000](http://localhost:8000) |
| Swagger / OpenAPI | [/docs](http://localhost:8000/docs) / [/openapi.json](http://localhost:8000/openapi.json) |
| ReDoc | [/redoc](http://localhost:8000/redoc) |
| Mailpit inbox | [localhost:8025](http://localhost:8025) |

MongoDB is published on port 27017; Mailpit SMTP on 1025. `DEBUG=true` publishes debugpy on 5679. This is a local development configuration with reload, not production readiness. Import and ML mutation routes lack authentication dependencies; do not expose this stack publicly.

## 6. Import the versioned dataset

**Only on the isolated, disposable project created above:** the following command immediately empties `results`, `competitions`, `athletes`, `categories`, `anomaly_runs` and `anomaly_scores`, even before checking `/app/data`. It retains `users`, so previous account-to-athlete pairings can become invalid. Never use it on an existing dataset you need to preserve.

```bash
dc exec backend python /app/scripts/load_data.py
```

The [actual seed](../backend/scripts/load_data.py) recursively imports sorted JSON under `/app/data`. Expect 329 discovered files for this source snapshot, per-file logs and an aggregate summary. Inspect its `errors` list: the script can finish with per-file/per-result errors. Do not expect 13,854 inserted results or the historical local-volume counts. Normalization, identity decisions and duplicate lookup affect records. An alternative single-file import without the seed wipe is:

```bash
curl --fail-with-body -F 'file=@data/2019/beloves/komplet.json' \
  http://localhost:8000/v1/data/import
```

This is an alternative, not an extra required import after seed. Inspect `data.errors` and `data.results_created` in its response; `success=true` does not guarantee every row imported. The raw-body equivalent is `POST /v1/data/import/raw` with `Content-Type: application/json` and the same file body.

## 7. Inspect records and resolve identities

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

The checks are read-only. `eligible without athlete` must be **zero** before attempting the current ML pipeline: its selection includes these rows but grouping assumes `athlete` exists. Do not delete uncertain results merely to make ML run. Inspect `match_status`, `match_reason` and `imported_athlete`, then resolve them through admin review/assignment or new-athlete creation according to source evidence.

The implemented routes include `GET /v1/admin/import/review`, `POST /v1/admin/results/{result_id}/assign-athlete` with `{"athlete_id":"..."}`, and `POST /v1/admin/results/{result_id}/create-athlete`. They require an administrator bearer token. Registering in the UI creates a regular user, and there is no documented automated first-admin bootstrap; provisioning requires an owner-controlled local database role decision. See [Swagger](http://localhost:8000/docs) for schemas. This is a known manual reproducibility dependency. If it cannot be resolved, stop the analytical sequence and record the blocker; successful inference on an untouched fresh import is not guaranteed.

## 8. Run or recompute anomaly detection

Once the preceding check passes:

```bash
curl --fail-with-body -X POST 'http://localhost:8000/v1/ml/recompute-yearly?force=false'
curl --fail-with-body 'http://localhost:8000/v1/ml/windows'
dc exec mongo mongosh firesport --quiet --eval '
printjson(db.anomaly_runs.findOne({}, {run_id: 1, window: 1, model: 1, stats: 1}));
printjson(db.anomaly_scores.findOne({}, {athlete_id: 1, result_id: 1, run_id: 1, score: 1, is_anomaly: 1, direction: 1}));
'
```

For the source date range, the generator attempts seven year-end anchors (2019–2025), including December 2025 despite the latest source competition being in October. Inspect response `computed`, `skipped_existing`, `failed` and each item's status/counters. A computed window may have no scores if all groups are ineligible. `processed` and `skipped` count athlete/category groups, not result rows.

After data/identity changes, explicitly replace existing window outputs:

```bash
curl --fail-with-body -X POST 'http://localhost:8000/v1/ml/recompute-yearly?force=true'
```

This supersedes older runs and deletes their scores. It is not a read-only request. Optional query bounds are named `from` and `to` (dates); for example append `&from=2023-01-01&to=2025-12-31`. Ordinary import does not refresh the ML pipeline.

## 9. Read API outputs and the UI

Select an actual scored athlete rather than inventing an ID:

```bash
FLAMMA_ATHLETE_ID="$(dc exec -T mongo mongosh firesport --quiet --eval 'const s=db.anomaly_scores.findOne(); if(s) print(s.athlete_id.toString());')"
if [ -n "$FLAMMA_ATHLETE_ID" ]; then
  curl --fail-with-body "http://localhost:8000/v1/ml/windows?athlete_id=$FLAMMA_ATHLETE_ID"
  curl --fail-with-body "http://localhost:8000/v1/athletes/$FLAMMA_ATHLETE_ID/anomalies"
fi
```

The windows response is an array with `run_id`, anchor, bounds and label. The anomaly response contains run metadata and scored items; inspect `score`, `is_anomaly`, `direction` and joined quality flags. The default selects the latest active run globally; for a specific athlete use a `run_id` returned by their windows endpoint if the default has no scores. An empty list means no eligible stored scores, not proof of ordinary performance. Use the UI statistics page to select an athlete, category and period. See [ML interpretation](ml-baseline.en.md).

## 10. Tests and EDA

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

Backend unit tests use fakes/monkeypatching rather than a running MongoDB. These commands mirror [CI](../.github/workflows/ci.yml); installing dependencies requires network access. A fresh `npm ci` was not run in the documentation audit; frontend checks used the existing dependency tree. Backend checks ran under Python 3.13 because 3.12 was not available locally; consult the audit for results and limits. [Notebook dependencies and execution order](notebooks/README.md) are documented separately.

## 11. Shutdown, persistence and safe cleanup

```bash
dc stop        # retain containers and data; resume with dc start
dc down        # remove this project's containers/network, retain its named volume
```

To reconnect in a later shell, restore the recorded `FLAMMA_REPRO_PROJECT`, `FLAMMA_REPRO_OVERRIDE` and `dc` definition. A new timestamp creates a different volume, not the old dataset. Do not delete the temporary override until done reconnecting.

For **irreversible deletion of this disposable project's database only**, first confirm its identity and volumes:

```bash
dc config --volumes
docker volume ls --filter "label=com.docker.compose.project=$FLAMMA_REPRO_PROJECT"
# Only after confirming this is the disposable project:
dc down --volumes
rm "$FLAMMA_REPRO_OVERRIDE"
```

No volume removal was executed during the audit. Do not use Docker-wide volume pruning.

## 12. Troubleshooting and reproducibility limits

| Symptom | Check / action |
| --- | --- |
| Docker socket permission / daemon unavailable | Start the Docker daemon and verify `docker info`; no import can be verified until it is available. |
| Container name or port conflict | Use the override for fixed names; free or explicitly remap host ports in an isolated environment. |
| `SECRET_KEY must be set...` | Check `backend/.env` exists, placeholder was replaced and the backend directory is mounted; a host shell variable alone is not automatically passed by Compose. |
| MongoDB connection failure | Container URI uses `mongo`, not localhost; the database name is explicitly `firesport`. |
| Empty lists after startup | Seed is off by default; inspect import logs and counts. |
| Admin request returns 401/403 | Requires a bearer token and owner-provisioned admin role; UI registration creates `user`. |
| ML anchors fail / missing `athlete` | Inspect valid unpaired results; resolve identities before retrying. HTTP success can contain failed anchors. |
| No windows/scores or old results | Inspect eligibility and skipped groups; use `force=true` after import or identity changes. |
| Password hashing fails outside localhost | Browser Web Crypto needs a secure context; use localhost locally and HTTPS for a designed deployment. |
| `Bad CPU type` in Node/npm | Use an executable for the machine architecture and verify the active PATH / `node --version`. |

Exact historical database state is not reproducible: its volume, users and manual identity edits are absent. Source extraction cannot be rerun without original documents/tools/URLs. Python dependencies and image tags are not locked; seed 42 alone does not guarantee identical scores. Import-time quality flags depend on data ordering/cache, and malformed/non-finite records or partially completed writes can affect analysis. Model runs are not transactionally archived. EDA flags differ from application flags. Licensing/source permissions and formal thesis metadata remain unresolved; see [data](data-baseline.en.md), [ML](ml-baseline.en.md) and [audit](documentation-audit.md).
