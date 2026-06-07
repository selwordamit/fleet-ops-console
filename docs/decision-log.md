# Decision Log

A running log of significant technical decisions made during implementation.

Use this document to show deliberate engineering thinking. Each entry should explain the decision, alternatives, reason, and tradeoff.

Major stack choices are already described in `docs/onboarding-project-spec.md` and `docs/architecture.md`. This log is for decisions made during the build: folder structure, implementation tradeoffs, temporary shortcuts, fallbacks, and scope decisions.

---

## Entry Template

```md
## YYYY-MM-DD | Short title

Context: What the step was and why a decision was needed.

Decision: What was decided.

Alternatives: What else was considered.

Reason: Why this choice was made.

Tradeoff: What this choice gives up or postpones.

Verification: How we checked that the decision works in practice.

Impact: What this affects going forward.
```

---

## Entries

## 2026-06-07 | Single source of truth: onboarding-project-spec.md

Context: We had confusion between `onboarding-project-spec.md` and `project-spec.md`.

Decision: Keep `onboarding-project-spec.md` as the only authoritative original requirements document and remove `project-spec.md` to avoid ambiguity.

Alternatives: Keep both specs; use `project-spec.md` as a separate working spec.

Reason: One spec avoids contradictions and makes project/Claude reasoning simpler.

Tradeoff: Less separation between original requirements and working interpretation, so implementation notes must live in `architecture.md`, `PROJECT_STATE.md`, and this decision log instead.

Verification: Stale references updated across `CLAUDE.md` and `docs/decision-log.md`; no remaining links to `project-spec.md`.

Impact: All docs and future work reference one spec; working interpretation now lives in `architecture.md`, `PROJECT_STATE.md`, and this log.

---

## 2026-06-07 | Docker Postgres for local runtime

Context: We needed a reproducible local PostgreSQL environment.

Decision: Run PostgreSQL through docker-compose using the `fleetops` database/user/password.

Alternatives: Use a locally installed Postgres service.

Reason: Docker gives a predictable, project-specific DB environment.

Tradeoff: Requires Docker running and port management. We hit a local Postgres conflict on port 5432 and resolved it by stopping the local service.

Verification: `docker compose exec postgres psql -U fleetops -d fleetops -c "SELECT 1;"` returned `1`.

Impact: Local development depends on Docker; the `fleetops` credentials and port 5432 are the shared baseline for backend and Alembic connections.

---

## 2026-06-07 | SQLAlchemy async with asyncpg

Context: The backend is FastAPI async and needs DB access.

Decision: Use the SQLAlchemy async engine/session with the asyncpg driver.

Alternatives: Use a synchronous SQLAlchemy driver; use raw asyncpg directly.

Reason: SQLAlchemy gives ORM/session structure while asyncpg matches the async backend.

Tradeoff: Async setup is slightly more complex than sync SQLAlchemy.

Verification: `check_db_connection()` returned `True` and `python -m pytest tests/ -q` passed.

Impact: All DB access goes through async SQLAlchemy sessions; repositories and models built later must be async-aware.

---

## 2026-06-07 | Alembic async migration infrastructure

Context: We need reproducible database schema changes before creating business tables.

Decision: Add Alembic configured for async SQLAlchemy.

Alternatives: Create tables manually; delay migrations until later; use a sync migration driver.

Reason: Alembic gives versioned, reviewable schema changes and keeps the DB reproducible.

Tradeoff: The async `env.py` is more complex than the default sync template.

Verification: `python -m alembic history`, `python -m alembic upgrade head --sql`, and `python -m alembic current` completed without errors.

Impact: Schema changes now flow through Alembic revisions; future models register on `Base.metadata` and are migrated, not hand-created.

---

## 2026-06-07 | Alembic reads DATABASE_URL from application settings

Context: Alembic needs the DB URL.

Decision: `env.py` reads `settings.database_url` instead of storing the URL in `alembic.ini`.

Alternatives: Put `sqlalchemy.url` directly in `alembic.ini`.

Reason: Keeps one source of truth for DB configuration and avoids credentials in static config.

Tradeoff: Someone reading `alembic.ini` alone will not see the DB URL; they must know `env.py` injects it from settings.

Verification: Alembic commands loaded `env.py` and connected successfully.

Impact: `settings.database_url` is the single source of DB config; changing the connection string requires no edits to `alembic.ini`.

