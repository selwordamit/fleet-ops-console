# Decision Log

A running log of significant technical decisions made during implementation.

Use this document to show deliberate engineering thinking. Each entry should explain the decision, alternatives, reason, and tradeoff.

Major stack choices are already described in `docs/onboarding-project-spec.md` and `docs/architecture.md`. This log is for decisions made during the build: folder structure, implementation tradeoffs, temporary shortcuts, fallbacks, and scope decisions.

---

## Entry Template

```md
## YYYY-MM-DD | Short title

Decision: What was decided.

Alternatives: What else was considered.

Reason: Why this choice was made.

Tradeoff: What this choice gives up or postpones.

Verification: How we checked that the decision works in practice.
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

---

## 2026-06-07 | Docker Postgres for local runtime

Context: We needed a reproducible local PostgreSQL environment.

Decision: Run PostgreSQL through docker-compose using the `fleetops` database/user/password.

Alternatives: Use a locally installed Postgres service.

Reason: Docker gives a predictable, project-specific DB environment.

Tradeoff: Requires Docker running and port management. We hit a local Postgres conflict on port 5432 and resolved it by stopping the local service.

Verification: `docker compose exec postgres psql -U fleetops -d fleetops -c "SELECT 1;"` returned `1`.

---

## 2026-06-07 | SQLAlchemy async with asyncpg

Context: The backend is FastAPI async and needs DB access.

Decision: Use the SQLAlchemy async engine/session with the asyncpg driver.

Alternatives: Use a synchronous SQLAlchemy driver; use raw asyncpg directly.

Reason: SQLAlchemy gives ORM/session structure while asyncpg matches the async backend.

Tradeoff: Async setup is slightly more complex than sync SQLAlchemy.

Verification: `check_db_connection()` returned `True` and `python -m pytest tests/ -q` passed.

---

## 2026-06-07 | Alembic async migration infrastructure

Context: We need reproducible database schema changes before creating business tables.

Decision: Add Alembic configured for async SQLAlchemy.

Alternatives: Create tables manually; delay migrations until later; use a sync migration driver.

Reason: Alembic gives versioned, reviewable schema changes and keeps the DB reproducible.

Tradeoff: The async `env.py` is more complex than the default sync template.

Verification: `python -m alembic history`, `python -m alembic upgrade head --sql`, and `python -m alembic current` completed without errors.

---

## 2026-06-07 | Alembic reads DATABASE_URL from application settings

Context: Alembic needs the DB URL.

Decision: `env.py` reads `settings.database_url` instead of storing the URL in `alembic.ini`.

Alternatives: Put `sqlalchemy.url` directly in `alembic.ini`.

Reason: Keeps one source of truth for DB configuration and avoids credentials in static config.

Tradeoff: Someone reading `alembic.ini` alone will not see the DB URL; they must know `env.py` injects it from settings.

Verification: Alembic commands loaded `env.py` and connected successfully.

---

## 2026-06-07 | First Agent model: integer PK, free-form string status

Context: First real business model (`agents`) needed to prove the model -> metadata -> migration -> table pipeline, without over-engineering fields.

Decision: Use an integer surrogate primary key and a plain `String(20)` `status` (server default `offline`), with `name`, `type`, nullable `last_seen`, and `created_at`/`updated_at` timestamps.

Alternatives: UUID primary key; a database enum or `CheckConstraint` to restrict `status` to idle/en-route/stopped/offline.

Reason: Simplest reasonable first version. Integer PK and a string status keep the first migration readable and easy to evolve; constraints can be added deliberately later.

Tradeoff: No DB-level guarantee of valid `status` values yet; switching the PK type later would require a migration. Validation will live in Pydantic/services for now.

Verification: `alembic revision --autogenerate` detected the table; `alembic upgrade head` applied it; `psql \d agents` shows all 7 columns with `status` defaulting to `offline`; `pytest` confirms `agents` is in `Base.metadata`.

---

## 2026-06-07 | Keep alembic.ini ASCII-only and comments on their own line

Context: Alembic broke completely (`UnicodeDecodeError`, then a bad `script_location`) after documentation comments were added to `alembic.ini`.

Decision: Keep `alembic.ini` ASCII-only and never place inline comments after a value.

Alternatives: Force a UTF-8 read of the ini; leave the rich comments and work around them.

Reason: Alembic reads `alembic.ini` with the OS locale encoding (cp1255 on this Windows machine), which cannot decode non-ASCII bytes such as emoji; and Python's configparser does not strip inline comments, so a trailing `# ...` becomes part of the value (`script_location`).

Tradeoff: Comments in `alembic.ini` must stay plain ASCII and on their own lines, which is slightly less expressive.

Verification: After removing the emoji and moving the inline comment, `alembic current`, `revision --autogenerate`, and `upgrade head` all ran successfully.

