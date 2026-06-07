# Phase 01 — Project Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the complete monorepo folder structure and a working `GET /health` FastAPI endpoint with a passing test.

**Architecture:** FastAPI app in `backend/app/`, with layered subpackages (api, core, models, schemas, repositories, services, db, cache, sockets). Frontend, simulator, and infra directories are stubs only. The health route lives in `backend/app/api/routes/health.py` and is registered in `backend/app/main.py`.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, pytest, httpx (test client)

---

## File Map

**Create (backend):**
- `backend/app/__init__.py`
- `backend/app/main.py` — FastAPI app instance, includes routers
- `backend/app/core/__init__.py`
- `backend/app/core/config.py` — placeholder Settings class (pydantic-settings)
- `backend/app/api/__init__.py`
- `backend/app/api/routes/__init__.py`
- `backend/app/api/routes/health.py` — GET /health router
- `backend/app/models/__init__.py`
- `backend/app/schemas/__init__.py`
- `backend/app/repositories/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/db/__init__.py`
- `backend/app/cache/__init__.py`
- `backend/app/sockets/__init__.py`
- `backend/alembic/.gitkeep`
- `backend/tests/__init__.py`
- `backend/tests/test_health.py` — test for GET /health
- `backend/requirements.txt` — runtime deps
- `backend/requirements-dev.txt` — test/dev deps
- `backend/.env.example` — env var template
- `backend/pyproject.toml` — pytest config (pythonpath = ["."])

**Create (frontend stubs):**
- `frontend/src/api/.gitkeep`
- `frontend/src/components/.gitkeep`
- `frontend/src/features/.gitkeep`
- `frontend/src/stores/.gitkeep`
- `frontend/src/sockets/.gitkeep`
- `frontend/src/types/.gitkeep`
- `frontend/src/pages/.gitkeep`

**Create (simulator stub):**
- `simulator/app/__init__.py`

**Create (infra/root):**
- `infra/.gitkeep`
- `.gitignore`
- `docker-compose.yml` — skeleton (services defined, not yet configured)

---

### Task 1: Backend Folder Skeleton

**Files:**
- Create: `backend/app/__init__.py` through `backend/app/sockets/__init__.py` (all listed above)
- Create: `backend/alembic/.gitkeep`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create all backend package `__init__.py` files**

  Run from project root:

  ```powershell
  $dirs = @(
    "backend\app",
    "backend\app\core",
    "backend\app\api",
    "backend\app\api\routes",
    "backend\app\models",
    "backend\app\schemas",
    "backend\app\repositories",
    "backend\app\services",
    "backend\app\db",
    "backend\app\cache",
    "backend\app\sockets",
    "backend\alembic",
    "backend\tests"
  )
  foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force "c:\fleet-ops-console\$d" | Out-Null
  }
  # Create __init__.py in each app subpackage
  $pkgs = @("app","app\core","app\api","app\api\routes","app\models","app\schemas","app\repositories","app\services","app\db","app\cache","app\sockets")
  foreach ($p in $pkgs) {
    New-Item -ItemType File -Force "c:\fleet-ops-console\backend\$p\__init__.py" | Out-Null
  }
  # alembic and tests stubs
  New-Item -ItemType File -Force "c:\fleet-ops-console\backend\alembic\.gitkeep" | Out-Null
  New-Item -ItemType File -Force "c:\fleet-ops-console\backend\tests\__init__.py" | Out-Null
  Write-Output "Done"
  ```

  Expected: `Done`

---

### Task 2: Health Route (TDD)

**Files:**
- Test: `backend/tests/test_health.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/pyproject.toml`

- [ ] **Step 1: Write the failing test**

  `backend/tests/test_health.py`:

  ```python
  from fastapi.testclient import TestClient
  from app.main import app

  client = TestClient(app)


  def test_health_returns_ok():
      response = client.get("/health")
      assert response.status_code == 200
      assert response.json() == {"status": "ok"}
  ```

- [ ] **Step 2: Create pyproject.toml so pytest can find `app`**

  `backend/pyproject.toml`:

  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  pythonpath = ["."]
  ```

- [ ] **Step 3: Install dev requirements (needed to run the test)**

  ```powershell
  cd c:\fleet-ops-console\backend
  pip install fastapi uvicorn[standard] pydantic pydantic-settings pytest httpx
  ```

  Expected: packages install without error.

- [ ] **Step 4: Run the test — confirm it FAILS (ImportError on app.main)**

  ```powershell
  cd c:\fleet-ops-console\backend
  pytest tests/test_health.py -v
  ```

  Expected: `ModuleNotFoundError: No module named 'app.main'` or similar ImportError.

- [ ] **Step 5: Implement the health route**

  `backend/app/api/routes/health.py`:

  ```python
  from fastapi import APIRouter

  router = APIRouter()


  @router.get("/health")
  def health() -> dict:
      return {"status": "ok"}
  ```

- [ ] **Step 6: Implement the placeholder settings**

  `backend/app/core/config.py`:

  ```python
  from pydantic_settings import BaseSettings


  class Settings(BaseSettings):
      app_name: str = "Fleet Operations Console"

      model_config = {"env_file": ".env"}


  settings = Settings()
  ```

- [ ] **Step 7: Implement the FastAPI app entry point**

  `backend/app/main.py`:

  ```python
  from fastapi import FastAPI
  from app.api.routes.health import router as health_router

  app = FastAPI(title="Fleet Operations Console")

  app.include_router(health_router)
  ```

- [ ] **Step 8: Run the test — confirm it PASSES**

  ```powershell
  cd c:\fleet-ops-console\backend
  pytest tests/test_health.py -v
  ```

  Expected output:

  ```
  tests/test_health.py::test_health_returns_ok PASSED  [100%]
  1 passed in <Xs>
  ```

- [ ] **Step 9: Commit**

  ```powershell
  cd c:\fleet-ops-console
  git add backend/app backend/tests backend/pyproject.toml
  git commit -m "feat: backend skeleton and GET /health endpoint with test"
  ```

---

### Task 3: Backend Tooling Files

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/.env.example`

- [ ] **Step 1: Write requirements.txt**

  `backend/requirements.txt`:

  ```
  fastapi>=0.111.0
  uvicorn[standard]>=0.30.0
  pydantic>=2.7.0
  pydantic-settings>=2.3.0
  python-dotenv>=1.0.0
  ```

- [ ] **Step 2: Write requirements-dev.txt**

  `backend/requirements-dev.txt`:

  ```
  -r requirements.txt
  pytest>=8.0.0
  pytest-asyncio>=0.23.0
  httpx>=0.27.0
  ```

- [ ] **Step 3: Write .env.example**

  `backend/.env.example`:

  ```
  # Copy to .env and fill in values
  APP_NAME=Fleet Operations Console

  # Phase 02 — Database
  # DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/fleetops

  # Phase 02 — Redis
  # REDIS_URL=redis://localhost:6379/0

  # Phase 11 — Auth
  # SECRET_KEY=change-me
  # ACCESS_TOKEN_EXPIRE_MINUTES=30
  # REFRESH_TOKEN_EXPIRE_DAYS=7
  ```

- [ ] **Step 4: Commit**

  ```powershell
  cd c:\fleet-ops-console
  git add backend/requirements.txt backend/requirements-dev.txt backend/.env.example
  git commit -m "chore: backend requirements and env example"
  ```

---

### Task 4: Frontend, Simulator, and Infra Skeletons

**Files:**
- Create: `frontend/src/api/.gitkeep` through `frontend/src/pages/.gitkeep`
- Create: `simulator/app/__init__.py`
- Create: `infra/.gitkeep`

- [ ] **Step 1: Create frontend directory stubs**

  ```powershell
  $frontendDirs = @("api","components","features","stores","sockets","types","pages")
  foreach ($d in $frontendDirs) {
    New-Item -ItemType Directory -Force "c:\fleet-ops-console\frontend\src\$d" | Out-Null
    New-Item -ItemType File -Force "c:\fleet-ops-console\frontend\src\$d\.gitkeep" | Out-Null
  }
  Write-Output "Done"
  ```

  Expected: `Done`

- [ ] **Step 2: Create simulator stub**

  ```powershell
  New-Item -ItemType Directory -Force "c:\fleet-ops-console\simulator\app" | Out-Null
  New-Item -ItemType File -Force "c:\fleet-ops-console\simulator\app\__init__.py" | Out-Null
  Write-Output "Done"
  ```

- [ ] **Step 3: Create infra stub**

  ```powershell
  New-Item -ItemType Directory -Force "c:\fleet-ops-console\infra" | Out-Null
  New-Item -ItemType File -Force "c:\fleet-ops-console\infra\.gitkeep" | Out-Null
  Write-Output "Done"
  ```

- [ ] **Step 4: Commit**

  ```powershell
  cd c:\fleet-ops-console
  git add frontend simulator infra
  git commit -m "chore: frontend, simulator, infra directory skeletons"
  ```

---

### Task 5: Root Tooling Files

**Files:**
- Create: `.gitignore`
- Create: `docker-compose.yml`

- [ ] **Step 1: Write .gitignore**

  `.gitignore`:

  ```gitignore
  # Python
  __pycache__/
  *.py[cod]
  *.pyo
  .venv/
  venv/
  env/
  *.egg-info/
  dist/
  build/
  .pytest_cache/
  .mypy_cache/

  # Environment
  .env
  *.env.local

  # Node
  node_modules/
  dist/
  .next/

  # OS
  .DS_Store
  Thumbs.db

  # IDE
  .vscode/
  .idea/
  *.swp
  ```

- [ ] **Step 2: Write docker-compose.yml skeleton**

  `docker-compose.yml`:

  ```yaml
  version: "3.9"

  services:
    backend:
      build: ./backend
      ports:
        - "8000:8000"
      # environment and volumes configured in Phase 02
      depends_on:
        - postgres
        - redis

    frontend:
      build: ./frontend
      ports:
        - "5173:5173"
      # configured in Phase 06

    simulator:
      build: ./simulator
      # configured in Phase 08
      depends_on:
        - backend

    postgres:
      image: postgres:16-alpine
      environment:
        POSTGRES_USER: fleetops
        POSTGRES_PASSWORD: fleetops
        POSTGRES_DB: fleetops
      ports:
        - "5432:5432"
      volumes:
        - postgres_data:/var/lib/postgresql/data

    redis:
      image: redis:7-alpine
      ports:
        - "6379:6379"

  volumes:
    postgres_data:
  ```

- [ ] **Step 3: Commit**

  ```powershell
  cd c:\fleet-ops-console
  git add .gitignore docker-compose.yml
  git commit -m "chore: gitignore and docker-compose skeleton"
  ```

---

### Task 6: Manual Verification

- [ ] **Step 1: Start the backend with uvicorn**

  ```powershell
  cd c:\fleet-ops-console\backend
  uvicorn app.main:app --reload
  ```

  Expected: server starts on `http://127.0.0.1:8000`

- [ ] **Step 2: Hit the health endpoint**

  Open in a browser or run:

  ```powershell
  Invoke-WebRequest -Uri "http://localhost:8000/health" | Select-Object -ExpandProperty Content
  ```

  Expected:

  ```json
  {"status":"ok"}
  ```

- [ ] **Step 3: Check OpenAPI docs load**

  Open `http://localhost:8000/docs` in a browser. Expected: Swagger UI showing `GET /health`.

---

### Task 7: Update PROJECT_STATE.md

- [ ] **Step 1: Update PROJECT_STATE.md to reflect Phase 01 complete**

  Update `docs/PROJECT_STATE.md`:

  ```markdown
  # FleetOps Project State

  ## Current Phase

  Step 2 — Backend + DB + Cache foundation (FastAPI config, PostgreSQL, Redis, Alembic).

  ---

  ## Completed

  ### Step 1 — Initial project structure ✓
  - Full monorepo folder structure created.
  - Minimal FastAPI app with `GET /health → {"status": "ok"}`.
  - Pytest test passes for health endpoint.
  - requirements.txt, requirements-dev.txt, .env.example in place.
  - docker-compose.yml skeleton (services declared, not yet wired).

  ---

  ## Key Decisions

  - Backend is the only gatekeeper.
  - Simulator talks only to the backend over REST.
  - PostgreSQL stores durable historical/audit data.
  - Redis stores fast operational/ephemeral data.
  - Backend code uses layered structure: API routes, services, repositories, schemas, models, db, cache, sockets.
  - Auth/RBAC are part of the final system but will be implemented only after the core flow is proven.
  - pydantic-settings used for typed config from the start; `.env.example` seeds Phase 02 vars.

  ---

  ## Current Working Proof

  ```text
  GET /health → {"status": "ok"}
  pytest tests/test_health.py — 1 passed
  ```

  ---

  ## Known Issues / Not Implemented Yet

  - No Docker Compose services wired (skeleton only).
  - No PostgreSQL connection.
  - No Redis connection.
  - No SQLAlchemy models.
  - No Alembic migrations.
  - No telemetry ingestion.
  - No WebSocket/Socket.IO.
  - No simulator behavior.
  - No frontend UI.
  - No auth/JWT/RBAC.

  ---

  ## Next Step

  Step 2: Add FastAPI config (typed Settings), PostgreSQL async engine, Redis client,
  SQLAlchemy session factory, and Alembic init. Verify all connections in Postman/health.
  ```

- [ ] **Step 2: Commit**

  ```powershell
  cd c:\fleet-ops-console
  git add docs/PROJECT_STATE.md
  git commit -m "docs: update PROJECT_STATE after Phase 01 complete"
  ```

---

## Self-Review

**Spec coverage check:**
- [x] root project structure — Task 4 + Task 5
- [x] backend folder structure — Task 1
- [x] frontend folder structure — Task 4
- [x] simulator folder structure — Task 4
- [x] docs folder structure — already exists
- [x] minimal FastAPI app — Task 2
- [x] `GET /health → {"status": "ok"}` — Task 2
- [x] placeholder files to keep folders — `.gitkeep` + `__init__.py`

**Out-of-scope confirmed absent:** auth, JWT, RBAC, database models, SQLAlchemy, Alembic, Redis, telemetry, WebSocket, simulator behavior, frontend UI, alerts, commands, performance.

**Placeholder scan:** No TBD, no "implement later", no vague steps — all code is complete.

**Type consistency:** `router` imported from `health.py` and registered in `main.py`. `Settings` defined in `config.py`, not yet imported by `main.py` (not needed in Phase 01). No cross-task type mismatches.
