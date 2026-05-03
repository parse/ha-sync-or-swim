# Agent Guidelines

## Project Shape

Pahlen Monitor watches Pahlen MiniMaster pool dosing units using camera images.
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
`GET /latest/{installation_id}` for the latest stored backend reading. Both use
the same backend response contract.

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
- `mypy backend/src custom_components/pahlen_monitor`
- `python scripts/generate_api_types.py --check`
- `pytest`
