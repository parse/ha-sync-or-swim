DOMAIN = "pahlen_monitor"

# Roles
ROLE_PRODUCER = "producer"
ROLE_CONSUMER = "consumer"

# Config keys
CONF_ROLE = "role"
CONF_INSTALLATION_ID = "installation_id"
CONF_BACKEND_URL = "backend_url"
CONF_CAMERA_ENTITY = "camera_entity"
CONF_LIGHT_ENTITY = "light_entity"
CONF_OPENAI_API_KEY = "openai_api_key"
CONF_PUSH_TOKEN = "push_token"
CONF_SCAN_INTERVAL = "scan_interval"  # minutes
CONF_POLL_INTERVAL = "poll_interval"  # minutes
CONF_IMAGE_DETAIL = "image_detail"
CONF_STALENESS_THRESHOLD = "staleness_threshold"  # minutes

# Defaults
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_POLL_INTERVAL = 30
DEFAULT_IMAGE_DETAIL = "low"
DEFAULT_STALENESS_THRESHOLD = 120
LIGHT_WARMUP_SECONDS = 1.5
BURST_COUNT = 8
BURST_INTERVAL_SECONDS = 0.4

# Status values
STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_ERROR = "error"
STATUS_UNKNOWN = "unknown"

# Platforms
PLATFORMS = ["sensor", "binary_sensor", "button"]
