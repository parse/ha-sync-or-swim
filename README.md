# Pahlen Monitor

Monitor your Pahlen pool dosing units using a camera and a Python backend. Home Assistant captures camera bursts, the FastAPI backend analyzes the LED status on Pahlen MiniMaster units, stores the reading, and exposes the latest status for sensors.

## Features
- **Producer Role:** Captures images from a camera (e.g., Reolink CX410) and sends one burst to the backend for analysis and storage.
- **Consumer Role:** Polls the shared backend for the latest stored status. Perfect for sharing status with neighbors.
- **Computer Vision Analysis:** Recognizes LED patterns to determine dosing vs. measurement modes and error states.
- **Status Sensors:** Provides detailed sensors for Free Chlorine and pH status.
- **Problem Detection:** Binary sensor for dosing problems and data staleness.

## Requirements
- Home Assistant ≥ 2024.4.1
- [HACS](https://hacs.xyz/) installed
- Camera pointed at dosing units (tested with Reolink PoE cameras)
- Spotlight/Light entity for night-time analysis
- Backend server (Python/FastAPI)

## Installation

### 1. Install Integration
1. Add this repository as a custom repository in HACS.
2. Install the "Pahlen Monitor" integration.
3. Restart Home Assistant.

## Backend Flow
- Producers send camera bursts to `POST /api/analyze/{installation_id}/burst` with the configured bearer token.
- The backend analyzes the images, stores the reading, and returns the same response shape used by `GET /latest/{installation_id}`.
- Consumers continue polling `GET /latest/{installation_id}`.

### 2. Configuration
- **Producer:** Add the integration and select "Producer". You'll need your camera entity, spotlight entity, backend URL, push token, and installation ID.
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
