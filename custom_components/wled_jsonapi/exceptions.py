"""Custom exceptions for WLED integration."""
from typing import Optional, Dict, Any


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


# Connection Diagnostics Exceptions

class WLEDDNSResolutionError(WLEDNetworkError):
    """Exception raised when DNS resolution fails for WLED device."""

    def __init__(self, message: str, host: Optional[str] = None, operation: Optional[str] = None,
                 original_error: Optional[Exception] = None, dns_server: Optional[str] = None):
        super().__init__(message, host, operation, original_error)
        self.dns_server = dns_server
        self.troubleshooting_hint = (
            "DNS Troubleshooting:\n"
            "1. Verify the hostname/IP address is correct\n"
            "2. Check if the device is on the same network\n"
            "3. Try using the IP address directly instead of hostname\n"
            "4. Check your router's DNS configuration\n"
            "5. Restart your router if other devices work fine"
        )


class WLEDConnectionTimeoutError(WLEDTimeoutError):
    """Exception raised when connection establishment times out."""

    def __init__(self, message: str, host: Optional[str] = None, operation: Optional[str] = None,
                 original_error: Optional[Exception] = None, timeout_stage: Optional[str] = None):
        super().__init__(message, host, operation, original_error)
        self.timeout_stage = timeout_stage  # 'connect', 'read', 'total'
        self.troubleshooting_hint = (
            "Connection Timeout Troubleshooting:\n"
            "1. Check if the WLED device is powered on\n"
            "2. Verify network connectivity to the device\n"
            "3. Check for network congestion or high latency\n"
            "4. Restart the WLED device if it's unresponsive\n"
            "5. Check if multiple devices are overwhelming the WLED device"
        )


class WLEDConnectionRefusedError(WLEDNetworkError):
    """Exception raised when WLED device actively refuses connection."""

    def __init__(self, message: str, host: Optional[str] = None, operation: Optional[str] = None,
                 original_error: Optional[Exception] = None, port: Optional[int] = None):
        super().__init__(message, host, operation, original_error)
        self.port = port
        self.troubleshooting_hint = (
            "Connection Refused Troubleshooting:\n"
            "1. Verify the WLED device is running and accessible\n"
            "2. Check if another application is using port 80\n"
            "3. Restart the WLED device\n"
            "4. Check if the device has HTTP access enabled\n"
            "5. Verify no firewall is blocking the connection"
        )


class WLEDConnectionResetError(WLEDNetworkError):
    """Exception raised when WLED device resets the connection unexpectedly."""

    def __init__(self, message: str, host: Optional[str] = None, operation: Optional[str] = None,
                 original_error: Optional[Exception] = None, reset_stage: Optional[str] = None):
        super().__init__(message, host, operation, original_error)
        self.reset_stage = reset_stage  # 'request', 'response'
        self.troubleshooting_hint = (
            "Connection Reset Troubleshooting:\n"
            "1. WLED device may be overloaded or busy\n"
            "2. Wait a moment and try again\n"
            "3. Reduce the frequency of requests\n"
            "4. Restart the WLED device if the issue persists\n"
            "5. Check if the device has enough memory/CPU resources"
        )


class WLEDSSLError(WLEDNetworkError):
    """Exception raised when SSL/TLS issues occur (unlikely for WLED but included for completeness)."""

    def __init__(self, message: str, host: Optional[str] = None, operation: Optional[str] = None,
                 original_error: Optional[Exception] = None, ssl_version: Optional[str] = None):
        super().__init__(message, host, operation, original_error)
        self.ssl_version = ssl_version
        self.troubleshooting_hint = (
            "SSL/TLS Troubleshooting:\n"
            "1. WLED devices typically use HTTP, not HTTPS\n"
            "2. Verify you're not trying to use HTTPS\n"
            "3. Check if a reverse proxy is causing SSL issues\n"
            "4. Ensure the correct protocol (HTTP) is being used"
        )


class WLEDHTTPError(WLEDConnectionError):
    """Exception raised when HTTP protocol errors occur."""

    def __init__(self, message: str, host: Optional[str] = None, operation: Optional[str] = None,
                 original_error: Optional[Exception] = None, http_code: Optional[int] = None,
                 response_headers: Optional[Dict[str, str]] = None):
        super().__init__(message, host, operation, original_error)
        self.http_code = http_code
        self.response_headers = response_headers
        self.troubleshooting_hint = (
            "HTTP Protocol Error Troubleshooting:\n"
            "1. Check WLED device firmware version\n"
            "2. Verify the API endpoint exists and is supported\n"
            "3. Check if the device supports HTTP/1.1\n"
            "4. Restart the WLED device if issues persist\n"
            "5. Consider updating WLED firmware to latest version"
        )


class WLEDSessionError(WLEDConnectionError):
    """Exception raised when aiohttp session issues occur."""

    def __init__(self, message: str, host: Optional[str] = None, operation: Optional[str] = None,
                 original_error: Optional[Exception] = None, session_state: Optional[Dict[str, Any]] = None):
        super().__init__(message, host, operation, original_error)
        self.session_state = session_state
        self.troubleshooting_hint = (
            "Session Error Troubleshooting:\n"
            "1. Restart the Home Assistant integration\n"
            "2. Check system resources (memory, file descriptors)\n"
            "3. Verify no connection limits are being exceeded\n"
            "4. Restart Home Assistant if the issue persists\n"
            "5. Check for memory leaks or resource exhaustion"
        )


class WLEDConnectionStalledError(WLEDTimeoutError):
    """Exception raised when connection appears to be stalled/hanging."""

    def __init__(self, message: str, host: Optional[str] = None, operation: Optional[str] = None,
                 original_error: Optional[Exception] = None, stall_stage: Optional[str] = None,
                 bytes_transferred: Optional[int] = None):
        super().__init__(message, host, operation, original_error)
        self.stall_stage = stall_stage
        self.bytes_transferred = bytes_transferred
        self.troubleshooting_hint = (
            "Connection Stalled Troubleshooting:\n"
            "1. Network may have high latency or packet loss\n"
            "2. WLED device may be processing a complex request\n"
            "3. Check network quality and stability\n"
            "4. Reduce request complexity or frequency\n"
            "5. Consider using shorter timeouts for slow networks"
        )


class WLEDConnectionLifecycleError(WLEDConnectionError):
    """Exception raised when connection lifecycle management detects issues."""

    def __init__(self, message: str, host: Optional[str] = None, lifecycle_stage: Optional[str] = None,
                 connection_state: Optional[str] = None, original_error: Optional[Exception] = None,
                 http_status: Optional[int] = None, connection_closed: Optional[bool] = None):
        super().__init__(message, host, f"lifecycle_{lifecycle_stage}" if lifecycle_stage else "lifecycle_error", original_error)
        self.lifecycle_stage = lifecycle_stage
        self.connection_state = connection_state
        self.http_status = http_status
        self.connection_closed = connection_closed
        self.troubleshooting_hint = (
            "Connection Lifecycle Error Troubleshooting:\n"
            "1. Connection may be closing prematurely during response processing\n"
            "2. WLED device may be experiencing high load or resource constraints\n"
            "3. Network connectivity issues may be interrupting response handling\n"
            "4. Try reducing request frequency or complexity\n"
            "5. Restart the WLED device if issues persist\n"
            "6. Check for network stability and packet loss\n"
            "7. Verify the WLED device has sufficient memory and processing resources"
        )


# Connection Performance Diagnostics

class WLEDConnectionDiagnostics:
    """Contains diagnostic information about connection performance and issues."""

    def __init__(self):
        self.timing_breakdown: Dict[str, float] = {}
        self.connection_state: Dict[str, Any] = {}
        self.session_info: Dict[str, Any] = {}
        self.network_info: Dict[str, Any] = {}
        self.error_history: list = []
        self.performance_metrics: Dict[str, Any] = {}

    def add_timing_step(self, step_name: str, duration_ms: float) -> None:
        """Add a timing step to the breakdown."""
        self.timing_breakdown[step_name] = duration_ms

    def set_connection_state(self, state: Dict[str, Any]) -> None:
        """Set the connection state information."""
        self.connection_state.update(state)

    def set_session_info(self, info: Dict[str, Any]) -> None:
        """Set the session information."""
        self.session_info.update(info)

    def set_network_info(self, info: Dict[str, Any]) -> None:
        """Set the network information."""
        self.network_info.update(info)

    def add_error_to_history(self, error_type: str, details: Dict[str, Any]) -> None:
        """Add an error to the history for pattern analysis."""
        self.error_history.append({
            "error_type": error_type,
            "timestamp": None,  # Will be set when added
            "details": details
        })

    def calculate_performance_metrics(self) -> Dict[str, Any]:
        """Calculate and return performance metrics."""
        total_time = sum(self.timing_breakdown.values())
        slowest_step = max(self.timing_breakdown.items(), key=lambda x: x[1]) if self.timing_breakdown else None

        metrics = {
            "total_request_time_ms": total_time,
            "slowest_step": slowest_step,
            "timing_breakdown": self.timing_breakdown,
            "error_count": len(self.error_history),
            "recent_errors": self.error_history[-5:] if self.error_history else []
        }

        self.performance_metrics.update(metrics)
        return metrics

    def get_troubleshooting_summary(self) -> str:
        """Generate a troubleshooting summary based on diagnostics."""
        summary_parts = []

        if self.timing_breakdown:
            total_time = sum(self.timing_breakdown.values())
            if total_time > 10000:  # > 10 seconds
                summary_parts.append(f"WARNING: Slow connection detected ({total_time:.1f}ms total)")

            slowest_step = max(self.timing_breakdown.items(), key=lambda x: x[1]) if self.timing_breakdown else None
            if slowest_step and slowest_step[1] > 5000:  # > 5 seconds for a single step
                summary_parts.append(f"WARNING: Slowest step: {slowest_step[0]} ({slowest_step[1]:.1f}ms)")

        if self.error_history:
            recent_errors = self.error_history[-3:]
            error_types = [err["error_type"] for err in recent_errors]
            if len(set(error_types)) == 1:  # Same error type repeatedly
                summary_parts.append(f"REPEATED: Repeated error pattern: {error_types[0]}")

        if not summary_parts:
            summary_parts.append("OK: No obvious issues detected in diagnostics")

        return "\n".join(summary_parts)