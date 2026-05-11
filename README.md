# SyncOrSwim

Sync your pool data or swim alone! Monitor your pool dosing units and share generic Home Assistant sensors with your neighbors using a central backend.

## Features
- **Producer Role:** Captures images from a camera and sends them to the backend for analysis. Also shares selected generic sensors with consumers.
- **Consumer Role:** Polls the shared backend for the latest pool status and shared sensors.
- **Generic Sensor Sharing:** Share any Home Assistant sensor (e.g., cellar temperature) with a consumer installation.
- **Computer Vision Analysis:** Recognizes LED patterns to determine dosing vs. measurement modes and error states.
- **Status Sensors:** Provides detailed sensors for pool chemistry.
- **Problem Detection:** Binary sensor for dosing problems and data staleness.

## Requirements
- Home Assistant ≥ 2024.4.1
- [HACS](https://hacs.xyz/) installed
- (Optional) Camera pointed at dosing units
- (Optional) Spotlight/Light entity for night-time analysis
- Backend server (Python/FastAPI)

## Quality Gates
The repository's validation workflow runs:
- `ruff check custom_components backend scripts`
- `ruff format --check custom_components backend scripts`
- `mypy backend/src custom_components/sync_or_swim`
- `python scripts/generate_api_types.py --check`
- `pytest`
- HACS validation
- hassfest validation

## Installation

### 1. Install Integration
1. Add this repository as a custom repository in HACS.
2. Install the "SyncOrSwim" integration.
3. Restart Home Assistant.

## Backend Flow
- Producers send data to the backend via analysis bursts or direct sensor pushes.
- Consumers poll the latest state for an installation ID.
- The backend serves a small shared-sensors web UI at `/` and `/ui`. Configure
  `WEB_UI_TOKEN` for this read-only UI; it can only read certain pool values and shared sensors through specific routes. The UI uses htmx from jsDelivr and does not require a frontend build step.

### 2. Configuration
- **Producer:** Select "Producer". Configure your camera (optional), shared sensors, backend URL, and token.
- **Consumer:** Select "Consumer". Configure the backend URL, token, and the installation ID to follow.

## Entities
Shared sensors are automatically discovered and created on the consumer side with full metadata (units, device classes).

## License
MIT
