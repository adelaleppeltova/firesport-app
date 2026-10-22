# Firesport App - AI Coding Guidelines

## Current architecture

- FastAPI backend, React frontend and MongoDB run together through Docker Compose.
- `backend/app/` contains `api/v1/`, `models/`, `services/`, `db/`, `ml/` and `tests/`.
- The backend exposes REST endpoints under `/v1/`; its ML layer includes anomaly detection with Isolation Forest.
- The frontend uses React, React Router, TanStack Query, Axios, Recharts and SCSS.
- Docker builds the frontend in a Node stage. Nginx serves the production build and proxies `/v1/` to the backend.

## Development checks

Use Python 3.12 for the backend:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest app/tests
```

Use the Node.js version from `frontend/.nvmrc` for the frontend:

```bash
cd frontend
npm ci
CI=true npm test -- --watchAll=false
npm run build
```

Before Docker startup, create `backend/.env` from `backend/.env.example` and
replace `SECRET_KEY` with a random non-placeholder value. `app/__init__.py`
loads it with python-dotenv; the backend mount exposes it at `/app/.env`.
Existing container environment values take precedence.

Run the local development stack with `docker compose up --build`. The frontend
is available on port 3000 and the backend on port 8000. Data import is off by
default. `scripts/load_data.py` deletes six collections and retains users;
never run it on a dataset that must be preserved. Follow the isolated workflow
in `docs/reproducibility.md` before seeding.

GitHub Actions in `.github/workflows/ci.yml` runs backend tests, frontend tests
and the frontend production build for the configured pushes and pull requests.

Keep changes minimal and follow the existing router, service, model and component
patterns. Do not assume files or layers that are not present in the repository.

## Documentation and factual accuracy

- English landing page: `README.md`; equivalent Czech landing page: `README.cs.md`.
- Essential guides have linked English/Czech versions in `docs/`; preserve parity when changing behaviour.
- Source-level data counts differ from imported MongoDB counts. Date any snapshot and recount inputs with `python3 docs/scripts/check_documentation.py`.
- Keep deterministic `quality_flag` rules distinct from Isolation Forest classifications and notebook EDA flags.
- Import and ML recomputation routes currently lack the admin router's permission dependency; do not describe this Compose setup as production-ready.
- Do not invent evaluation metrics, source permissions, software licenses or thesis citation metadata. Record uncertainties in the documentation audit.
