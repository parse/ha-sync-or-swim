# Pahlen Monitor

Monitor your Pahlen pool dosing units using a camera and AI. This project uses Home Assistant, a Node.js backend, and OpenAI Vision to interpret the LED status on Pahlen MiniMaster units.

## Features
- **Producer Role:** Captures images from a camera (e.g., Reolink CX410), analyzes them using GPT-4o, and pushes the results to a backend.
- **Consumer Role:** Polls the shared backend for the latest status. Perfect for sharing status with neighbors.
- **AI Analysis:** Recognizes LED patterns (steady, flashing) to determine dosing vs. measurement modes and error states.
- **Status Sensors:** Provides detailed sensors for Free Chlorine and pH status.
- **Problem Detection:** Binary sensor for dosing problems and data staleness.

## Requirements
- Home Assistant ≥ 2024.4.1
- [HACS](https://hacs.xyz/) installed
- Camera pointed at dosing units (tested with Reolink PoE cameras)
- Spotlight/Light entity for night-time analysis
- OpenAI API key
- Backend server (Node.js/Hono)

## Installation

### 1. Install Integration
1. Add this repository as a custom repository in HACS.
2. Install the "Pahlen Monitor" integration.
3. Restart Home Assistant.

## Contract
- The backend OpenAPI contract is generated to `backend/openapi.json` with `npm run generate:openapi` from `backend/`.
- Generate the Python types used by the Home Assistant integration with `python3 scripts/generate_python_contract.py`.
- Run `python3 scripts/check_openapi_contract.py` from the repository root to verify `custom_components/pahlen_monitor/generated_api.py` is up to date with `backend/openapi.json`.

### 2. Configuration
- **Producer:** Add the integration and select "Producer". You'll need your OpenAI API key, camera entity, and backend URL.
- **Consumer:** Add the integration and select "Consumer". You only need the backend URL and the same Installation ID as the producer.

## Entities
| Entity | Role | Description |
| --- | --- | --- |
| `sensor.free_chlorine_dosing_status` | Both | Status (ok, warning, error) |
| `sensor.free_chlorine_dosing_action` | Both | Whether action is required |
| `sensor.ph_dosing_status` | Both | Status (ok, warning, error) |
| `sensor.ph_dosing_action` | Both | Whether action is required |
| `binary_sensor.dosing_problem` | Both | Turns on if status is warning/error or data is stale |
| `button.dosing_analyze_now` | Producer | Trigger analysis manually |

## License
MIT
