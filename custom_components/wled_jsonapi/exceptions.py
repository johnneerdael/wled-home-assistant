"""Custom exceptions for WLED integration."""
from typing import Optional


class WLEDConnectionError(Exception):
    """Base exception raised when connection to WLED device fails."""

    def __init__(self, message: str, host: Optional[str] = None, operation: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.host = host
        self.operation = operation
        self.original_error = original_error


class WLEDTimeoutError(WLEDConnectionError):
    """Exception raised when WLED device request times out."""


class WLEDNetworkError(WLEDConnectionError):
    """Exception raised when network-related errors occur."""


class WLEDInvalidResponseError(Exception):
    """Base exception raised when WLED device returns invalid response."""

    def __init__(self, message: str, host: Optional[str] = None, endpoint: Optional[str] = None, response_data: Optional[str] = None):
        super().__init__(message)
        self.host = host
        self.endpoint = endpoint
        self.response_data = response_data


class WLEDInvalidJSONError(WLEDInvalidResponseError):
    """Exception raised when WLED device returns invalid JSON."""


class WLEDInvalidStateError(WLEDInvalidResponseError):
    """Exception raised when WLED device response has invalid state structure."""


class WLEDCommandError(Exception):
    """Base exception raised when WLED command fails."""

    def __init__(self, message: str, command: Optional[dict] = None, host: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.command = command
        self.host = host
        self.original_error = original_error


class WLEDInvalidCommandError(WLEDCommandError):
    """Exception raised when an invalid command is sent to WLED device."""


class WLEDUnsupportedCommandError(WLEDCommandError):
    """Exception raised when WLED device doesn't support a command."""


class WLEDDeviceUnavailableError(Exception):
    """Exception raised when WLED device is unavailable."""

    def __init__(self, message: str, host: Optional[str] = None, last_seen: Optional[str] = None):
        super().__init__(message)
        self.host = host
        self.last_seen = last_seen


class WLEDAuthenticationError(Exception):
    """Exception raised when WLED device requires authentication."""

    def __init__(self, message: str, host: Optional[str] = None):
        super().__init__(message)
        self.host = host


class WLEDConfigurationError(Exception):
    """Exception raised when there's a configuration issue."""

    def __init__(self, message: str, config_key: Optional[str] = None, config_value: Optional[str] = None):
        super().__init__(message)
        self.config_key = config_key
        self.config_value = config_value


class WLEDPresetError(Exception):
    """Exception raised when there's an issue with presets."""

    def __init__(self, message: str, preset_id: Optional[int] = None, preset_name: Optional[str] = None):
        super().__init__(message)
        self.preset_id = preset_id
        self.preset_name = preset_name


class WLEDPresetNotFoundError(WLEDPresetError):
    """Exception raised when a preset is not found."""


class WLEDPresetLoadError(WLEDPresetError):
    """Exception raised when a preset cannot be loaded or applied."""


class WLEDPlaylistError(Exception):
    """Exception raised when there's an issue with playlists."""

    def __init__(self, message: str, playlist_id: Optional[int] = None, playlist_name: Optional[str] = None):
        super().__init__(message)
        self.playlist_id = playlist_id
        self.playlist_name = playlist_name


class WLEDPlaylistNotFoundError(WLEDPlaylistError):
    """Exception raised when a playlist is not found."""


class WLEDPlaylistLoadError(WLEDPlaylistError):
    """Exception raised when a playlist cannot be loaded or applied."""