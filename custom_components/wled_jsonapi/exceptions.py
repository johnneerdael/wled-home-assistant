"""Simplified custom exceptions for WLED integration."""
from typing import Optional


class WLEDConnectionError(Exception):
    """Base exception raised when connection to WLED device fails."""

    def __init__(self, message: str, host: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.host = host
        self.original_error = original_error


class WLEDTimeoutError(WLEDConnectionError):
    """Exception raised when WLED device request times out."""


class WLEDNetworkError(WLEDConnectionError):
    """Exception raised when network-related errors occur."""


class WLEDAuthenticationError(Exception):
    """Exception raised when WLED device requires authentication."""

    def __init__(self, message: str, host: Optional[str] = None):
        super().__init__(message)
        self.host = host


class WLEDInvalidResponseError(Exception):
    """Exception raised when WLED device returns invalid response."""

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
    """Exception raised when WLED command fails."""

    def __init__(self, message: str, command: Optional[dict] = None, host: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.command = command
        self.host = host
        self.original_error = original_error


class WLEDPresetError(Exception):
    """Exception raised when there's an issue with presets."""

    def __init__(self, message: str, preset_id: Optional[int] = None):
        super().__init__(message)
        self.preset_id = preset_id


class WLEDPresetLoadError(WLEDPresetError):
    """Exception raised when a preset cannot be loaded or applied."""


class WLEDPlaylistError(Exception):
    """Exception raised when there's an issue with playlists."""

    def __init__(self, message: str, playlist_id: Optional[int] = None):
        super().__init__(message)
        self.playlist_id = playlist_id


class WLEDPlaylistLoadError(WLEDPlaylistError):
    """Exception raised when a playlist cannot be loaded or applied."""


class WLEDPresetNotFoundError(WLEDPresetError):
    """Raised when a requested preset is not found."""

    def __init__(self, preset_id: str, message: str | None = None) -> None:
        """Initialize preset not found error."""
        super().__init__(message or f"Preset '{preset_id}' not found", preset_id)


class WLEDPlaylistNotFoundError(WLEDPlaylistError):
    """Exception raised when a playlist is not found on the device."""