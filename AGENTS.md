# Agent Guidelines

## Project Shape

SyncOrSwim watches Pahlen MiniMaster pool dosing units using camera images.
The Home Assistant integration captures image bursts, sends them to the
FastAPI backend, and exposes the latest reading as sensors, buttons, switches,
and a problem binary sensor.

The backend is the source of truth. It analyzes LED patterns, decides dosing or
measurement state, validates and shapes API responses, and stores measurements.
Readings are persisted through SQLAlchemy using `DATABASE_URL`; tests use an
in-memory SQLite database, while deployed environments provide the real database
connection.

Home Assistant has two roles. Producers capture camera bursts and send them to
`POST /api/analyze/{installation_id}/burst`. Consumers poll
`GET /api/latest/{installation_id}` for the latest stored backend reading. Both
use the same backend response contract. Routes should prefer `/api/...` routes
and `/ui/...` for fragments.

The backend serves a small shared-sensors web UI at `/` and `/ui`.
Configure `WEB_UI_TOKEN` for this read-only UI; it can only read certain pool
values and shared sensors through specific routes. The UI uses htmx from
jsDelivr and does not require a frontend build step.

Keep changes simple, strict, and easy to review. Read the nearby code before
changing it, make sure the goal is clear, and avoid guessing about behavior or
API shape when the code can answer the question.

This project prefers a fat backend and a thin client. Put business rules,
validation, data shaping, persistence, analysis, and API response shape in the
backend unless there is a clear reason not to. Client-side code should mostly
display state, collect input, and call the backend.

Prefer plain, direct code over clever abstractions. Do not add speculative
features, broad frameworks, or unused extension points. Reuse existing project
patterns before introducing new ones.

Keep edits scoped to the requested goal. Avoid unrelated formatting, renames,
refactors, or style changes. Do not touch code you do not need to touch.

Favor strict typing, explicit data contracts, small functions, clear names, and
useful errors. Before finishing, verify the change with focused tests or checks
when practical. If verification cannot be run, say what was skipped and why.

## Quality Checks

Use the relevant local checks for the files you changed. Common checks include:

- `ruff check custom_components backend scripts`
- `ruff format --check custom_components backend scripts`
- `mypy backend/src custom_components/sync_or_swim`
- `python scripts/generate_api_types.py --check`
- `pytest`
