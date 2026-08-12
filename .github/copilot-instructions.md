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

Run the complete local stack with `docker compose up --build`. The frontend is
available on port 3000 and the backend on port 8000.

GitHub Actions in `.github/workflows/ci.yml` runs backend tests, frontend tests
and the frontend production build for the configured pushes and pull requests.

Keep changes minimal and follow the existing router, service, model and component
patterns. Do not assume files or layers that are not present in the repository.
