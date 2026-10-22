**EN** · [CZ](documentation-audit.cs.md) · [Project](../README.md)

# Documentation audit and validation

Audit date: **2026-10-22**. Implementation inspected from starting commit `5eafc43e` on the dedicated branch `docs/bilingual-portfolio-overhaul`. This is a documentation change; application logic, model behaviour, data files and existing notebooks were preserved. No database import, recomputation, collection deletion or volume reset was executed.

## Evidence reviewed and corrections

| Area | Repository evidence / documentation outcome |
| --- | --- |
| Landing page and author | Original README, screenshot assets and application footer; English/Czech pages now share the same ten-section structure and four images. Thesis title/context retained; no external academic identifiers invented. |
| Configuration and runtime | Compose, both Dockerfiles, entrypoint, `app/__init__.py`, database and auth services; documented actual dotenv discovery, environment precedence, service URLs and development-only runtime. |
| API/authentication | All v1 routers, auth dependencies, frontend password helper and models; distinguished admin protection from unprotected import and ML routes. |
| Data ingestion | Seed, DataImporter, matching/identity/merge services, models and indexes; documented normalization, deduplication, review state, dropped provenance and partial writes. |
| ML | Config, numerical helper, windows, orchestration and anomaly routers; retained Czech baseline detail and added English methodology, exact defaults, scoring, storage and failure boundaries. |
| EDA | Notebook and `docs/analysis` loaders/queries/transforms; documented inputs, imports, cell order and definitions that differ from the application. |
| Tests/CI | Backend suite, frontend test/scripts, `.nvmrc`, CI workflow; removed a hard-coded test count from evergreen architecture prose and clarified actual CI branch triggers. |
| Licensing | No software LICENSE or formal CITATION metadata found in the audited checkout; source permissions remain unspecified. |

The original quick start's `.env` mechanism is supported by `load_dotenv()`; an explicit Compose `env_file` is not required in the current bind-mounted layout. The documentation makes the mechanism visible rather than adding redundant configuration.

Historical local MongoDB counts from **2026-08-12** were retained as a dated, previously reported snapshot, not reverified or presented as fresh-import expectations. Source JSON counts were independently recalculated (329 files, 394 category blocks, 13,854 rows; competition dates 2019-05-04–2025-10-04).

## Executed checks

| Check | Outcome and practical limits |
| --- | --- |
| `python3 docs/scripts/check_documentation.py` | Passed local relative links, local Markdown anchors, language navigation and README heading/image parity; recounted all JSON and completeness fields. Does not fetch external URLs or judge translated meaning. |
| `git diff --check` | Passed; no whitespace errors. |
| Shell examples | All 30 Bash blocks syntax-checked with `bash -n`; commands matched against scripts/configuration. Syntax is not runtime verification. |
| OpenAPI generation without DB connection | FastAPI import with an ephemeral process-only secret and eight documented API operations passed; this is not an HTTP test. |
| `docker compose config --quiet` | Passed with Compose 5.3.1; isolated override configuration also checked without starting containers. |
| `python -m ruff check app main.py scripts` from backend | Passed, Ruff 0.15.22. |
| `python -m pytest app/tests` from backend | **102 passed**, 24 existing datetime deprecation warnings; Python **3.13.14**, pytest 9.1.1, temporary environment. The required Python 3.12 CI environment was not reproduced locally. |
| `npm run lint` | Passed with Node **20.20.1**, existing `node_modules`. |
| `CI=true npm test -- --watchAll=false` | **1 suite / 1 test passed**, existing dependencies. |
| `npm run build` | Passed; existing Browserslist data-age notice. No lockfile changes or dependency upgrade. |
| EDA headless execution | **27 code cells executed successfully**, in order, on repository JSON using nbclient; executed copy saved outside the repository. |

Backend test dependencies were installed into a temporary environment from the existing requirements, not added to the project. Notable versions: FastAPI 0.159.1, Pydantic 2.14.1, Motor 3.7.1, PyMongo 4.19.0, NumPy 2.5.4, scikit-learn 1.9.1. These record this audit, not a supported dependency lock.

EDA execution used Python 3.13.14, pandas 3.0.6, Matplotlib 3.11.2, seaborn 0.13.2, IPython 9.17.1, nbformat 5.11.1, nbclient 0.11.0 and ipykernel 7.4.0. Packages were installed only into the temporary environment. Runtime/cache files and the executed notebook copy were placed under `/tmp`. Historical plot equivalence was not asserted.

The first frontend attempt failed because the active PATH selected an incompatible executable; selecting the installed native Node 20 binary resolved it. Initial dependency installation was network-restricted, then completed with approved access. The first notebook attempt could not open a local kernel socket inside the sandbox; the same read-only notebook execution completed with approved local-kernel access.

## Commands and operations not executed

- Docker `up --build`, seed import, MongoDB inspection, real HTTP API smoke checks, ML recomputation and shutdown/cleanup: `docker info` confirmed the daemon was not running. No live database count or analytical result was claimed.
- A fresh `npm ci`: frontend validation used existing installed dependencies. This verifies the available tree, not a clean installation.
- Tests on Python 3.12: only Python 3.13 was available for the temporary test environment.
- External links, GitHub badge/live workflow state and thesis/source retrieval: not fetched; repository file targets were checked locally.
- Production deployment: not attempted or specified by the existing development configuration.

## Reproducibility blockers and implementation limitations

1. Valid unresolved results can lack `athlete`; ML grouping dereferences it without filtering. A complete fresh import cannot be promised to produce successful ML runs until identity review is complete. This needs an explicit ML eligibility policy and regression coverage in future engineering work.
2. Admin review requires a provisioned administrator; UI registration produces `user`, and an automated first-admin bootstrap is absent.
3. The seed deletes six collections and preserves users; it can leave stale account pairing. Import error accumulation and quality-flag caches complicate exact reconstruction.
4. Non-finite time cleaning can misalign persisted scores with source rows. Run superseding and score persistence are not transactional; prior scores are deleted.
5. Original source sheets, retrieval URLs, extraction code, dependency locks and manual database-edit history are absent. Local historical state cannot be reconstructed exactly.

These issues are documented without changing application semantics under a documentation-only scope.

## Decisions for the repository owner

- Choose a software license; separately establish dataset/source redistribution rights and privacy/retention/correction handling, including identifiable screenshots.
- Supply verified formal thesis citation metadata and a thesis link if intended for publication; confirm the preferred citation format.
- Decide how initial administrators are provisioned and who may import or recompute analysis before any public deployment.
- Decide whether unresolved valid results should be excluded, rejected or resolved before ML; do not silently discard them.

## Suggested follow-up

Prioritize an isolated Docker import/identity/ML integration run on Python 3.12, with explicit eligibility and partial-failure checks. Then lock backend/EDA dependencies and container versions, add a provenance manifest with source permissions, correct notebook coverage titles and missing-year handling, and improve transactional model-run retention. Context-aware or hierarchical performance modelling and labelled evaluation are research proposals, not implemented functionality.

For ongoing documentation maintenance, run:

```bash
python3 docs/scripts/check_documentation.py
git diff --check
```

## Modified and created files

| Status | Files |
| --- | --- |
| Modified | [README](../README.md), [Copilot instructions](../.github/copilot-instructions.md), Czech [architecture](architecture.md), [data](data-baseline.md), [ML](ml-baseline.md) |
| New landing/technical documents | [Czech README](../README.cs.md), English [architecture](architecture.en.md), [data](data-baseline.en.md), [ML](ml-baseline.en.md) |
| New reproducibility guides | [EN](reproducibility.md), [CZ](reproducibility.cs.md) |
| New EDA guides | [EN](notebooks/README.md), [CZ](notebooks/README.cs.md) |
| New supporting materials | [Gallery](screenshots/README.md), [documentation checker](scripts/check_documentation.py), audit [EN](documentation-audit.md) and [CZ](documentation-audit.cs.md) |

Total: 5 modified and 12 new files. The new documentation checker uses only the standard library and performs no database operations.
