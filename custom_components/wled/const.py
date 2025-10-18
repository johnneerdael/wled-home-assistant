"""Constants for WLED integration."""
from datetime import timedelta

DOMAIN = "wled"

# Configuration keys
CONF_HOST = "host"

# API endpoints
API_STATE = "/json/state"
API_INFO = "/json/info"
API_EFFECTS = "/json/eff"
API_PALETTES = "/json/pal"
API_BASE = "/json"

# Retry configuration
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 30.0  # seconds
RETRY_BACKOFF_MULTIPLIER = 2.0

# Timeouts
REQUEST_TIMEOUT = 10.0  # seconds
CONNECTION_TIMEOUT = 5.0  # seconds

# Polling
UPDATE_INTERVAL = timedelta(minutes=1)

# Device availability
MAX_FAILED_POLLS = 3

# WLED JSON API keys
KEY_ON = "on"
KEY_BRIGHTNESS = "bri"
KEY_PRESET = "ps"
KEY_PLAYLIST = "pl"
KEY_TRANSITION = "transition"
KEY_SEGMENTS = "seg"
KEY_EFFECT = "fx"
KEY_SPEED = "sx"
KEY_INTENSITY = "ix"
KEY_PALETTE = "pal"

# Info keys
KEY_NAME = "name"
KEY_VERSION = "ver"
KEY_LED_COUNT = "leds"
KEY_MAC = "mac"
KEY_IP = "ip"

# Default values
DEFAULT_BRIGHTNESS = 255
DEFAULT_TRANSITION = 0

# Error messages
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVALID_AUTH = "invalid_auth"
ERROR_UNKNOWN = "unknown"