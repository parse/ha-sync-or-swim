from typing import Final, Literal

DOMAIN = "sync_or_swim"
INSTALLATION_ID_PATTERN = r"^[a-z0-9-]{1,64}$"

# Roles
ROLE_PRODUCER = "producer"
ROLE_CONSUMER = "consumer"

# Config keys
CONF_ROLE = "role"
CONF_INSTALLATION_ID = "installation_id"
CONF_BACKEND_URL = "backend_url"
CONF_CAMERA_ENTITY = "camera_entity"
CONF_PUSH_TOKEN = "push_token"
CONF_SCAN_INTERVAL = "scan_interval"  # minutes
CONF_POLL_INTERVAL = "poll_interval"  # minutes
CONF_STALENESS_THRESHOLD = "staleness_threshold"  # minutes
CONF_INSTALLATION_ENABLED = "installation_enabled"
CONF_SHARED_SENSORS = "shared_sensors"
CONF_SHARED_SENSOR_INTERVALS = "shared_sensor_intervals"

# Defaults
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_POLL_INTERVAL = 5
DEFAULT_STALENESS_THRESHOLD = 120
DEFAULT_INSTALLATION_ENABLED = True
DEFAULT_SHARED_SENSORS_INTERVAL = 15
LIGHT_WARMUP_SECONDS = 1.5
BURST_COUNT = 8
BURST_INTERVAL_SECONDS = 0.4

# Status values
STATUS_OK: Final[Literal["ok"]] = "ok"
STATUS_WARNING: Final[Literal["warning"]] = "warning"
STATUS_ERROR: Final[Literal["error"]] = "error"
STATUS_UNKNOWN: Final[Literal["unknown"]] = "unknown"

# Platforms
PLATFORMS = ["sensor", "binary_sensor", "button", "switch"]
