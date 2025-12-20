# Firesport App - AI Coding Guidelines

## Architecture Overview
- **Full-stack app**: FastAPI backend (Python) + React frontend, MongoDB database
- **Backend structure**: `app/` contains `api/v1/` (routers), `models/` (Pydantic schemas), `services/` (business logic), `db/` (CRUD), `ml/` (performance analysis)
- **Frontend structure**: React with `pages/`, `components/`, `hooks/`, `layouts/`, SCSS styling
- **Data flow**: API endpoints call services, which use ML utils for trend/stability analysis; frontend uses TanStack Query for caching

## Key Patterns
- **Models**: Use Pydantic Base/Create/InDB pattern (e.g., `AthleteBase`, `AthleteCreate`, `AthleteInDB`); alias `_id` to `id` with `populate_by_name=True`
- **Authentication**: JWT tokens stored in localStorage; axios interceptor sets `Authorization` header; check `/auth/me` on app load
- **MongoDB**: Use `ObjectId` for IDs, convert to string; collections: athletes, results, competitions, categories
- **ML Integration**: Import from `ml.utils` for performance trends (improving/declining/stable) and stability ratings
- **Routing**: Czech paths (e.g., `/zavodnici` for athletes); protected routes in `AppLayout`, public in `BasicLayout`
- **Styling**: SCSS with BEM-like classes; mixins/variables in `assets/styles/abstracts/`

## Developer Workflows
- **Run full app**: `docker-compose up` (backend:8000, frontend:3000, mongo:27017)
- **Backend dev**: `uvicorn main:app --reload` (requires MongoDB)
- **Frontend dev**: `npm start` (proxies API to localhost:8000)
- **Database**: MongoDB with collections for athletes/results/competitions/categories; no migrations, schema-less
- **Testing**: No automated tests; validate with API calls and UI checks

## Conventions
- **Backend**: snake_case files/functions; async/await everywhere; log with `logging`; raise `HTTPException` for errors
- **Frontend**: camelCase; use hooks (`useApi`, `usePersistedState`); TanStack Query for data fetching
- **Commits**: No specific pattern observed; focus on feature branches
- **Dependencies**: Backend uses motor (async Mongo), argon2 for passwords; frontend uses axios + TanStack Query

## Common Tasks
- **Add new model**: Create in `models/`, add CRUD in `db/crud.py`, service in `services/`, router in `api/v1/`
- **New API endpoint**: Add to router, call service; use Depends for auth
- **Frontend page**: Add route in `App.js`, create in `pages/`, use `useApi` hook
- **ML feature**: Add to `ml/tasks/` or `utils/`, integrate in services

Reference: `docker-compose.yml`, `backend/main.py`, `frontend/src/App.js`, `backend/app/models/athlete.py`