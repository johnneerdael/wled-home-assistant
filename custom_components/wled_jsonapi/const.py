"""Constants for WLED integration."""
from datetime import timedelta

DOMAIN = "wled_jsonapi"

# Configuration keys
CONF_HOST = "host"

# API endpoints
API_STATE = "/json/state"
API_INFO = "/json/info"
API_EFFECTS = "/json/eff"
API_PALETTES = "/json/pal"
API_PRESETS = "/presets.json"
API_BASE = "/json"

# Timeouts
TIMEOUT = 10.0  # seconds

# Polling
UPDATE_INTERVAL = timedelta(minutes=1)
PRESETS_UPDATE_INTERVAL = timedelta(hours=1)

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

# Hostname validation constants
MAX_HOSTNAME_LENGTH = 253
MIN_HOSTNAME_LENGTH = 1
MAX_LABEL_LENGTH = 63

# Dangerous characters for hostname validation
DANGEROUS_HOSTNAME_CHARS = [';', '&', '|', '`', '$', '(', ')', '{', '}', '[', ']', '<', '>', '"', "'"]

# Security validation patterns
PROTOCOL_PATTERN = "://"
PATH_TRAVERSAL_PATTERN = "../"
PATH_TRAVERSANCE_WINDOWS_PATTERN = "..\\"
CONSECUTIVE_DOTS_PATTERN = ".."
INVALID_HOSTNAME_START_CHARS = ['.', '-']
INVALID_HOSTNAME_END_CHARS = ['.', '-']

# Network security messages
MSG_PUBLIC_IP_WARNING = "Public IP addresses not recommended for IoT devices for security reasons"
MSG_PROTOCOL_INJECTION = "Protocol not allowed in hostname. Only enter IP address or hostname."
MSG_DANGEROUS_CHARS = "Invalid characters detected in hostname"
MSG_PATH_TRAVERSAL = "Invalid hostname format"
MSG_INVALID_LENGTH = "Invalid hostname length (must be 1-253 characters)"
MSG_INVALID_FORMAT = "Invalid hostname format"
MSG_VALID_HOSTNAME = "Valid hostname"
MSG_PRIVATE_IP = "Private IP address"
MSG_LOCALHOST_IP = "Localhost address"
MSG_LINK_LOCAL_IP = "Link-local address"