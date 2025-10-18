"""Custom exceptions for WLED integration."""


class WLEDConnectionError(Exception):
    """Exception raised when connection to WLED device fails."""


class WLEDInvalidResponseError(Exception):
    """Exception raised when WLED device returns invalid response."""


class WLEDCommandError(Exception):
    """Exception raised when WLED command fails."""


class WLEDDeviceUnavailableError(Exception):
    """Exception raised when WLED device is unavailable."""