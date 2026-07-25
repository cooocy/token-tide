# Python Server Convention

This document defines the durable coding and operational conventions for TokenTide. Read it before changing Python service code, packaging, configuration, migrations, tests, logging, or deployment scripts.

## 1. Project identity

Keep these names distinct and consistent:

```text
Repository directory: token-tide
Distribution name:    token-tide
Python import package: token_tide
Console Script:       token-tide
FastAPI instance:     app
Commit environment:   TOKEN_TIDE_COMMIT
Python version:       3.12
Backend directory:    backend
```

- Use `token-tide` for the distribution and Console Script.
- Use `token_tide` for imports, tests, Alembic imports, the wheel, and Uvicorn target.
- Keep the Console Script target `token_tide.main:main` and Uvicorn target `token_tide.main:app`.
- Do not use `PYTHONPATH` to compensate for incorrect packaging.

## 2. Source layout and boundaries

The independently deployed Python service lives under `backend/`. Use a single application package:

```text
backend/token_tide/
├── main.py
├── bootstrap.py
├── config.py
├── database.py
├── logging.py
├── response.py
├── bookstore/
└── providers/
```

- `main.py` owns application assembly, lifespan, Router registration, and the Console Script.
- `bootstrap.py` owns remote configuration initialization order.
- `config.py` owns typed YAML settings.
- `database.py` owns Engine and Session construction and disposal.
- `logging.py` owns application, Uvicorn, and Alembic log routing.
- Router functions adapt HTTP; Service owns workflows; persistence queries stay outside Router.
- Avoid generic `utils.py`, `common.py`, and `helpers.py`; name modules after their responsibility.

## 3. Packaging

- Declare metadata and dependencies in `backend/pyproject.toml` with PEP 621.
- Build with Hatchling and package only `token_tide`.
- Local development may use `pip install -e .`.
- Server deployment must use `.venv/bin/python -m pip install --upgrade .`.
- Start production through `.venv/bin/token-tide`, not a source file.
- Reinstall after deployed source changes.

## 4. FastAPI

- Keep the FastAPI instance named `app`.
- Use lifespan for schedulers and database disposal.
- Read host and port from typed configuration.
- Register exception handlers and business Routers centrally.
- Keep reverse-proxy prefixes outside Python Router paths.
- Preserve the `R<T>` response envelope.
- `GET /` returns `app`, UTC `ts` ending in `Z`, and `TOKEN_TIDE_COMMIT`, falling back to `unknown`.
- Never expose stack traces, connection strings, secrets, or internal details in responses.

## 5. Configuration

- Business settings come from strongly typed YAML, not scattered environment variables.
- Environment variables are limited to bootstrap information and process metadata.
- `application-example.yaml` contains structure only and never real credentials.
- Production configuration is downloaded from `token-tide/application-:tail.yaml`.
- Bootstrap order is download, clear Settings cache, then load Settings.
- Both the Console Script and Alembic must bootstrap before reading settings.
- Download, decode, write, or validation failure must stop startup.
- Downloaded `application-*.yaml` files stay ignored by Git.
- Never log Bookstore tokens, Provider API keys, Authorization headers, or complete sensitive payloads.

## 6. Database and migrations

- Use SQLAlchemy 2.x.
- Keep Engine and Session construction in `token_tide.database`.
- Change schema only through Alembic revisions.
- Alembic reuses `bootstrap_settings()` to obtain the database URL.
- Import all models needed by Alembic metadata.
- Do not use `create_all()` in production.
- Run `alembic upgrade head` before starting a newly installed build.
- Migration failure must prevent application startup.

## 7. Logging

Use:

```text
backend/logs/app.log
backend/logs/uvicorn.log
backend/logs/alembic.log
```

- Use Python `logging` with UTF-8 `RotatingFileHandler`.
- Rotate at 20 MiB and retain 10 backups.
- Include time, level, logger name, and message.
- Prevent Uvicorn logs from propagating into `app.log`.
- Keep Alembic and SQLAlchemy migration logs separate.
- Redirect `nohup` stdout and stderr to `/dev/null`; Python owns runtime log files.

## 8. Server startup

Maintain an idempotent `backend/start.sh` that:

- uses `set -Eeuo pipefail` and `umask 027`;
- resolves paths from the script location;
- creates or reuses a Python 3.12 virtual environment;
- validates PID contents and ownership before stopping a process;
- attempts graceful shutdown before forced termination;
- installs the current project with normal `pip install --upgrade`;
- applies migrations before starting;
- injects the short Git commit through `TOKEN_TIDE_COMMIT`;
- starts `.venv/bin/token-tide` with `nohup`;
- records and verifies the new PID.

Do not weaken PID checks or allow migration failure to fall through.

## 9. Testing

- Add deterministic tests at changed boundaries.
- Use temporary directories and mocks for remote configuration and Provider APIs.
- Never require production credentials.
- For configuration changes, update typed models, examples, bootstrap behavior, tests, and README together.
- For migration changes, validate offline SQL when a live database is unavailable.
- Verify wheel contents and the installed Console Script when packaging changes.
- Run repository tests and static checks allowed by repository rules.
- Never run frontend build, dev, preview, TypeScript, or lint commands unless the user explicitly allows them.
- Always run `git diff --check` before handoff.

## 10. Change discipline

- Read `AGENTS.md`, `CLAUDE.md`, and this document before backend changes.
- Preserve unrelated user changes.
- Make the narrowest change that fully satisfies the request.
- Do not add queues, caches, containers, or orchestration unless requested.
- Keep documentation, examples, migrations, and tests synchronized.
- Persist a finalized plan under `docs/plan/` before implementing non-trivial planned work.
- Follow `<type>: <scope>: <description>` commit conventions.
- Do not commit or push unless requested.
