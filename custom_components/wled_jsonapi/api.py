"""Simplified API client for WLED JSONAPI devices."""
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import ClientError, ClientSession, ServerTimeoutError

from .const import API_BASE, API_INFO, API_PRESETS, API_STATE, TIMEOUT
from .exceptions import (
    WLEDCommandError,
    WLEDConnectionError,
    WLEDInvalidResponseError,
    WLEDTimeoutError,
    WLEDNetworkError,
    WLEDInvalidJSONError,
    WLEDInvalidStateError,
    WLEDPresetError,
    WLEDPresetNotFoundError,
    WLEDPresetLoadError,
    WLEDPlaylistError,
    WLEDPlaylistNotFoundError,
    WLEDPlaylistLoadError,
    WLEDAuthenticationError,
    WLEDDNSResolutionError,
    WLEDConnectionTimeoutError,
    WLEDConnectionRefusedError,
    WLEDConnectionResetError,
    WLEDSSLError,
    WLEDHTTPError,
    WLEDSessionError,
    WLEDConnectionStalledError,
    WLEDConnectionDiagnostics,
)
from .models import WLEDPresetsData

_LOGGER = logging.getLogger(__name__)


class WLEDConnectionDiagnosticsManager:
    """Manages connection diagnostics and timing for WLED devices."""

    def __init__(self, host: str, debug_mode: bool = False):
        """Initialize the diagnostics manager."""
        self.host = host
        self.debug_mode = debug_mode
        self.current_diagnostics = WLEDConnectionDiagnostics()
        self.historical_diagnostics = []
        self._start_time = None
        self._timing_stack = []

    @asynccontextmanager
    async def timed_request(self, operation_name: str):
        """Context manager for timing HTTP requests with detailed breakdown."""
        self._start_time = time.time()
        self._timing_stack = []

        try:
            if self.debug_mode:
                _LOGGER.debug("🔍 Starting diagnostic timing for %s to %s", operation_name, self.host)

            # Start request timing
            start_time = time.time()
            self._timing_stack.append(("request_start", start_time))

            yield self

        finally:
            # Calculate total request time
            total_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            self.current_diagnostics.add_timing_step(f"{operation_name}_total", total_time)

            if self.debug_mode:
                _LOGGER.debug("⏱️ %s to %s completed in %.2fms", operation_name, self.host, total_time)
                self._log_detailed_timing()

    def add_timing_step(self, step_name: str) -> None:
        """Add a timing step with duration from previous step."""
        if self._timing_stack:
            previous_step, previous_time = self._timing_stack[-1]
            current_time = time.time()
            duration_ms = (current_time - previous_time) * 1000

            self.current_diagnostics.add_timing_step(step_name, duration_ms)
            self._timing_stack.append((step_name, current_time))

            if self.debug_mode:
                _LOGGER.debug("⏱️ %s: %.2fms", step_name, duration_ms)

    def _log_detailed_timing(self) -> None:
        """Log detailed timing breakdown for debugging."""
        if self.debug_mode and self.current_diagnostics.timing_breakdown:
            _LOGGER.debug("📊 Detailed timing breakdown for %s:", self.host)
            for step, duration in self.current_diagnostics.timing_breakdown.items():
                _LOGGER.debug("   - %s: %.2fms", step, duration)

    def log_connection_state(self, state: str, details: Dict[str, Any] = None) -> None:
        """Log connection state changes."""
        state_info = {"state": state, "timestamp": time.time()}
        if details:
            state_info.update(details)

        self.current_diagnostics.set_connection_state(state_info)

        if self.debug_mode:
            _LOGGER.debug("🔗 Connection state for %s: %s", self.host, state)
            if details:
                _LOGGER.debug("   Details: %s", details)

    def log_session_info(self, session_info: Dict[str, Any]) -> None:
        """Log aiohttp session information."""
        self.current_diagnostics.set_session_info(session_info)

        if self.debug_mode:
            _LOGGER.debug("🌐 Session info for %s: %s", self.host, session_info)

    def log_network_info(self, network_info: Dict[str, Any]) -> None:
        """Log network information."""
        self.current_diagnostics.set_network_info(network_info)

        if self.debug_mode:
            _LOGGER.debug("🌍 Network info for %s: %s", self.host, network_info)

    def record_error(self, error_type: str, details: Dict[str, Any]) -> None:
        """Record an error in the diagnostics history."""
        error_record = {
            "error_type": error_type,
            "timestamp": time.time(),
            "host": self.host,
            "details": details
        }

        self.current_diagnostics.add_error_to_history(error_type, error_record)

        # Log the error with diagnostic context
        _LOGGER.error("❌ %s error for %s: %s", error_type, self.host, details.get("message", "Unknown error"))

        if self.debug_mode:
            _LOGGER.debug("🔍 Error diagnostics for %s: %s", self.host, error_record)

    def finalize_diagnostics(self) -> WLEDConnectionDiagnostics:
        """Finalize current diagnostics and move to history."""
        # Calculate performance metrics
        metrics = self.current_diagnostics.calculate_performance_metrics()

        # Log troubleshooting summary if needed
        if self.debug_mode:
            summary = self.current_diagnostics.get_troubleshooting_summary()
            _LOGGER.debug("📋 Troubleshooting summary for %s:\n%s", self.host, summary)

        # Move to history and create new instance
        self.historical_diagnostics.append(self.current_diagnostics)
        self.current_diagnostics = WLEDConnectionDiagnostics()

        # Keep only last 10 diagnostics to prevent memory growth
        if len(self.historical_diagnostics) > 10:
            self.historical_diagnostics.pop(0)

        return self.historical_diagnostics[-1]

    def get_latest_diagnostics(self) -> Optional[WLEDConnectionDiagnostics]:
        """Get the most recent completed diagnostics."""
        return self.historical_diagnostics[-1] if self.historical_diagnostics else None


class WLEDJSONAPIClient:
    """Simplified API client for WLED JSONAPI devices."""

    def __init__(self, host: str, session: Optional[ClientSession] = None, debug_mode: bool = False, use_simple_client: bool = False) -> None:
        """Initialize the API client."""
        self.host = host
        self.base_url = f"http://{host}{API_BASE}"
        self._session = session
        self._close_session = False
        self.debug_mode = debug_mode
        self.use_simple_client = use_simple_client
        self.diagnostics_manager = WLEDConnectionDiagnosticsManager(host, debug_mode)

        if session is None:
            self._session = None
            self._close_session = True

            if use_simple_client:
                # Simplified configuration for maximum compatibility
                self._session_config = {
                    "connector": {
                        # Disable connection pooling and advanced features
                        "enable_cleanup_closed": False,
                        "force_close": True,  # Force close connections
                        "limit": 1,  # Single connection
                        "limit_per_host": 1,
                        "ttl_dns_cache": 0,  # Disable DNS cache
                        "use_dns_cache": False,
                        "keepalive_timeout": 0,  # Disable keepalive
                        "disable_cleanup_closed": True,  # No cleanup
                    },
                    "timeout": {
                        "total": 30,  # Simple total timeout
                        "connect": 10,  # Connection timeout
                        "sock_read": None,  # Use total timeout for reads
                    },
                    "headers": {
                        # Minimal headers only
                        "User-Agent": "Home-Assistant-WLED-JSONAPI/1.0",
                    },
                    "auto_decompress": False,  # Disable auto decompression
                }
                self._max_retries = 3  # Simple retry logic
                self._retry_delay = 1.0  # 1 second delay
            else:
                # Enhanced configuration (existing behavior)
                self._session_config = {
                    "connector": {
                        "enable_cleanup_closed": False,
                        "force_close": False,
                        "limit": 1,
                        "limit_per_host": 1,
                        "ttl_dns_cache": 300,
                        "use_dns_cache": True,
                        "keepalive_timeout": 30,
                    },
                    "timeout": {
                        "total": 30,
                        "connect": 10,
                        "sock_read": 15,
                    },
                    "headers": {
                        "User-Agent": "Home-Assistant-WLED-JSONAPI/1.0",
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Encoding": "gzip, deflate",
                        "Connection": "keep-alive",
                    },
                    "auto_decompress": True,
                }
                self._max_retries = 5  # Enhanced retry logic
                self._retry_delay = None  # Exponential backoff
        else:
            self._session = session
            self._close_session = False
            self._session_config = {}
            # Use simple retry logic when external session provided with simple mode
            self._max_retries = 3 if use_simple_client else 5
            self._retry_delay = 1.0 if use_simple_client else None

        # Log session information for diagnostics
        if self._session:
            session_info = {
                "closed": self._session.closed,
                "connector": {
                    "limit": getattr(self._session.connector, 'limit', 'unknown') if self._session.connector else "none",
                    "limit_per_host": getattr(self._session.connector, 'limit_per_host', 'unknown') if self._session.connector else "none",
                    "keepalive_timeout": getattr(self._session.connector, 'keepalive_timeout', 'unknown') if self._session.connector else "none",
                },
                "timeout": {
                    "total": getattr(self._session.timeout, 'total', 'unknown') if self._session.timeout else "none",
                    "connect": getattr(self._session.timeout, 'connect', 'unknown') if self._session.timeout else "none",
                    "sock_read": getattr(self._session.timeout, 'sock_read', 'unknown') if self._session.timeout else "none",
                }
            }
        else:
            session_info = {
                "session_type": "lazy_initialized",
                "config": self._session_config
            }

        self.diagnostics_manager.log_session_info(session_info)

    async def _ensure_session(self) -> ClientSession:
        """Ensure that an aiohttp session exists, creating one if necessary."""
        if self._session is None or self._session.closed:
            if self._session_config:
                # Create connector
                connector = aiohttp.TCPConnector(**self._session_config["connector"])

                # Create timeout
                timeout = aiohttp.ClientTimeout(**self._session_config["timeout"])

                # Create session
                self._session = ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers=self._session_config["headers"],
                    auto_decompress=self._session_config["auto_decompress"],
                )

                # Log session creation
                session_info = {
                    "closed": self._session.closed,
                    "connector": {
                        "limit": getattr(self._session.connector, 'limit', 'unknown') if self._session.connector else "none",
                        "limit_per_host": getattr(self._session.connector, 'limit_per_host', 'unknown') if self._session.connector else "none",
                        "keepalive_timeout": getattr(self._session.connector, 'keepalive_timeout', 'unknown') if self._session.connector else "none",
                    },
                    "timeout": {
                        "total": getattr(self._session.timeout, 'total', 'unknown') if self._session.timeout else "none",
                        "connect": getattr(self._session.timeout, 'connect', 'unknown') if self._session.timeout else "none",
                        "sock_read": getattr(self._session.timeout, 'sock_read', 'unknown') if self._session.timeout else "none",
                    }
                }
                self.diagnostics_manager.log_session_info(session_info)

        return self._session

    def _build_url(self, endpoint: str) -> str:
        """
        Build the full URL for the given endpoint.

        Handles the special case of the presets endpoint which is not under /json.

        Args:
            endpoint: The API endpoint to build URL for

        Returns:
            Complete URL for the endpoint
        """
        # Handle presets endpoint separately since it's not under /json
        if endpoint == API_PRESETS:
            return f"http://{self.host}{endpoint}"
        else:
            # For other endpoints, remove the /json prefix from endpoint since base_url already includes it
            if endpoint.startswith("/json/"):
                endpoint = endpoint[5:]  # Remove "/json" prefix
            return f"{self.base_url}{endpoint}"

    async def _execute_http_request(self, method: str, url: str, data: Optional[Dict[str, Any]] = None) -> aiohttp.ClientResponse:
        """
        Execute the HTTP request and return the response with comprehensive diagnostics.

        Handles GET and POST requests with detailed logging, timing, and error handling.

        Args:
            method: HTTP method (GET or POST)
            url: Full URL to request
            data: Optional JSON data for POST requests

        Returns:
            aiohttp ClientResponse object

        Raises:
            ValueError: If unsupported HTTP method is provided
            Various WLED connection exceptions based on specific failure modes
        """
        operation_name = f"{method.upper()}_{url.split('/')[-1] or 'root'}"

        async with self.diagnostics_manager.timed_request(operation_name):
            try:
                # Ensure session is available
                session = await self._ensure_session()

                # Validate session state before making request
                if session.closed:
                    error_msg = f"Cannot execute {method} request: session is closed"
                    self.diagnostics_manager.record_error("WLEDSessionError", {
                        "message": error_msg,
                        "session_state": "closed",
                        "url": url
                    })
                    raise WLEDSessionError(error_msg, host=self.host, operation=operation_name)

                self.diagnostics_manager.log_connection_state("session_validated", {
                    "session_closed": session.closed,
                    "method": method,
                    "url": url
                })

                self.diagnostics_manager.add_timing_step("session_validation")

                # Log network information
                network_info = {
                    "target_host": self.host,
                    "url": url,
                    "method": method,
                    "user_agent": session.headers.get("User-Agent", "unknown") if hasattr(session, 'headers') else "default"
                }
                self.diagnostics_manager.log_network_info(network_info)

                # Execute the appropriate request method
                if method.upper() == "GET":
                    return await self._execute_get_request(session, url, operation_name)
                elif method.upper() == "POST":
                    return await self._execute_post_request(session, url, data, operation_name)
                else:
                    error_msg = f"Unsupported HTTP method: {method}"
                    self.diagnostics_manager.record_error("WLEDCommandError", {
                        "message": error_msg,
                        "method": method,
                        "url": url
                    })
                    raise ValueError(error_msg)

            except (WLEDConnectionError, WLEDNetworkError, WLEDTimeoutError):
                # Re-raise WLED exceptions
                raise
            except aiohttp.ClientConnectorError as err:
                # Handle connection-related errors with specific types
                await self._handle_connector_error(err, method, url)
            except aiohttp.ServerTimeoutError as err:
                timeout_error = WLEDConnectionTimeoutError(
                    f"Request to WLED device at {self.host} timed out during {method} request to {url}",
                    host=self.host,
                    operation=operation_name,
                    original_error=err,
                    timeout_stage="server"
                )
                self.diagnostics_manager.record_error("WLEDConnectionTimeoutError", {
                    "message": str(timeout_error),
                    "timeout_stage": "server",
                    "url": url,
                    "method": method
                })
                raise timeout_error
            except aiohttp.ClientResponseError as err:
                http_error = WLEDHTTPError(
                    f"HTTP error {err.status} during {method} request to {url}: {err.message}",
                    host=self.host,
                    operation=operation_name,
                    original_error=err,
                    http_code=err.status,
                    response_headers=dict(err.headers) if err.headers else None
                )
                self.diagnostics_manager.record_error("WLEDHTTPError", {
                    "message": str(http_error),
                    "http_status": err.status,
                    "url": url,
                    "method": method
                })
                raise http_error
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                network_error = WLEDNetworkError(
                    f"Network error during {method} request to {url}: {err}",
                    host=self.host,
                    operation=operation_name,
                    original_error=err
                )
                self.diagnostics_manager.record_error("WLEDNetworkError", {
                    "message": str(network_error),
                    "error_type": type(err).__name__,
                    "url": url,
                    "method": method
                })
                raise network_error
            except Exception as err:
                connection_error = WLEDConnectionError(
                    f"Unexpected error during {method} request to {url}: {err}",
                    host=self.host,
                    operation=operation_name,
                    original_error=err
                )
                self.diagnostics_manager.record_error("WLEDConnectionError", {
                    "message": str(connection_error),
                    "error_type": type(err).__name__,
                    "url": url,
                    "method": method
                })
                raise connection_error
            finally:
                # Finalize diagnostics for this request
                self.diagnostics_manager.finalize_diagnostics()

    async def _execute_get_request(self, session: ClientSession, url: str, operation_name: str) -> aiohttp.ClientResponse:
        """Execute a GET request with detailed diagnostics."""
        self.diagnostics_manager.log_connection_state("executing_get", {"url": url})

        headers = {"Cache-Control": "no-cache"}  # Prevent caching issues

        try:
            self.diagnostics_manager.add_timing_step("get_request_start")

            async with session.get(url, headers=headers) as response:
                self.diagnostics_manager.add_timing_step("get_response_received")

                # Log response details
                response_info = {
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type", "unknown"),
                    "content_length": response.headers.get("Content-Length", "unknown"),
                    "connection_state": "received"
                }
                self.diagnostics_manager.log_connection_state("get_response_complete", response_info)

                _LOGGER.debug("GET request completed with status %s for %s", response.status, url)
                return response

        except aiohttp.ClientConnectionError as err:
            await self._handle_connector_error(err, "GET", url)
        except Exception as err:
            # This will be caught by the outer exception handler
            raise

    async def _execute_post_request(self, session: ClientSession, url: str, data: Optional[Dict[str, Any]], operation_name: str) -> aiohttp.ClientResponse:
        """Execute a POST request with detailed diagnostics."""
        self.diagnostics_manager.log_connection_state("executing_post", {
            "url": url,
            "data_size": len(str(data)) if data else 0
        })

        headers = {"Content-Type": "application/json"}

        try:
            self.diagnostics_manager.add_timing_step("post_request_start")

            async with session.post(url, json=data, headers=headers) as response:
                self.diagnostics_manager.add_timing_step("post_response_received")

                # Log response details
                response_info = {
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type", "unknown"),
                    "content_length": response.headers.get("Content-Length", "unknown"),
                    "connection_state": "received"
                }
                self.diagnostics_manager.log_connection_state("post_response_complete", response_info)

                _LOGGER.debug("POST request completed with status %s for %s", response.status, url)
                return response

        except aiohttp.ClientConnectionError as err:
            await self._handle_connector_error(err, "POST", url)
        except Exception as err:
            # This will be caught by the outer exception handler
            raise

    async def _handle_connector_error(self, err: aiohttp.ClientConnectorError, method: str, url: str) -> None:
        """Handle connector errors with specific exception types and diagnostics."""
        error_str = str(err).lower()
        operation_name = f"{method.upper()}_{url.split('/')[-1] or 'root'}"

        if "dns" in error_str or "name resolution" in error_str:
            dns_error = WLEDDNSResolutionError(
                f"DNS resolution failed for WLED device at {self.host}: {err}",
                host=self.host,
                operation=operation_name,
                original_error=err
            )
            self.diagnostics_manager.record_error("WLEDDNSResolutionError", {
                "message": str(dns_error),
                "error_details": str(err),
                "url": url,
                "method": method
            })
            raise dns_error

        elif "connection refused" in error_str:
            refused_error = WLEDConnectionRefusedError(
                f"WLED device at {self.host} refused the connection: {err}",
                host=self.host,
                operation=operation_name,
                original_error=err,
                port=80
            )
            self.diagnostics_manager.record_error("WLEDConnectionRefusedError", {
                "message": str(refused_error),
                "error_details": str(err),
                "url": url,
                "method": method
            })
            raise refused_error

        elif "connection reset" in error_str or "connection closed" in error_str:
            reset_error = WLEDConnectionResetError(
                f"WLED device at {self.host} reset the connection: {err}",
                host=self.host,
                operation=operation_name,
                original_error=err,
                reset_stage="request"
            )
            self.diagnostics_manager.record_error("WLEDConnectionResetError", {
                "message": str(reset_error),
                "error_details": str(err),
                "url": url,
                "method": method
            })
            raise reset_error

        elif "timeout" in error_str:
            timeout_error = WLEDConnectionTimeoutError(
                f"Connection timeout during {method} request to {url}: {err}",
                host=self.host,
                operation=operation_name,
                original_error=err,
                timeout_stage="connect"
            )
            self.diagnostics_manager.record_error("WLEDConnectionTimeoutError", {
                "message": str(timeout_error),
                "timeout_stage": "connect",
                "url": url,
                "method": method
            })
            raise timeout_error

        elif "ssl" in error_str or "tls" in error_str:
            ssl_error = WLEDSSLError(
                f"SSL/TLS error during {method} request to {url}: {err}",
                host=self.host,
                operation=operation_name,
                original_error=err
            )
            self.diagnostics_manager.record_error("WLEDSSLError", {
                "message": str(ssl_error),
                "error_details": str(err),
                "url": url,
                "method": method
            })
            raise ssl_error

        else:
            # Generic connection error
            network_error = WLEDNetworkError(
                f"Connection error during {method} request to {url}: {err}",
                host=self.host,
                operation=operation_name,
                original_error=err
            )
            self.diagnostics_manager.record_error("WLEDNetworkError", {
                "message": str(network_error),
                "error_details": str(err),
                "url": url,
                "method": method
            })
            raise network_error

    def set_debug_mode(self, debug_mode: bool) -> None:
        """Enable or disable debug mode for verbose connection tracing."""
        self.debug_mode = debug_mode
        self.diagnostics_manager.debug_mode = debug_mode
        _LOGGER.info("Debug mode %s for WLED device at %s", "enabled" if debug_mode else "disabled", self.host)

    def get_connection_diagnostics(self) -> Optional[WLEDConnectionDiagnostics]:
        """Get the most recent connection diagnostics."""
        return self.diagnostics_manager.get_latest_diagnostics()

    def get_diagnostics_summary(self) -> Dict[str, Any]:
        """Get a summary of recent connection diagnostics."""
        latest = self.diagnostics_manager.get_latest_diagnostics()
        if not latest:
            return {"status": "no_diagnostics", "message": "No connection diagnostics available"}

        return {
            "status": "available",
            "host": self.host,
            "performance_metrics": latest.calculate_performance_metrics(),
            "troubleshooting_summary": latest.get_troubleshooting_summary(),
            "recent_errors": latest.error_history[-3:] if latest.error_history else [],
            "debug_mode": self.debug_mode
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the WLED API with comprehensive diagnostics and error handling."""
        url = self._build_url(endpoint)
        operation_name = f"{method}_{endpoint or 'root'}"

        _LOGGER.debug("Making %s request to %s (host: %s, endpoint: %s, simple_client: %s)",
                     method, url, self.host, endpoint, self.use_simple_client)
        self.diagnostics_manager.log_connection_state("request_start", {
            "method": method,
            "endpoint": endpoint,
            "url": url,
            "has_data": data is not None,
            "simple_client": self.use_simple_client
        })

        # Use simple retry logic for simple client mode
        if self.use_simple_client:
            return await self._request_with_simple_retry(method, url, endpoint, data, operation_name)
        else:
            return await self._request_with_enhanced_retry(method, url, endpoint, data, operation_name)

    async def _request_with_simple_retry(
        self, method: str, url: str, endpoint: str, data: Optional[Dict[str, Any]], operation_name: str
    ) -> Dict[str, Any]:
        """Execute request with simple retry logic for maximum compatibility."""
        last_exception = None

        for attempt in range(self._max_retries + 1):  # +1 for initial attempt
            try:
                if attempt > 0:
                    _LOGGER.debug("Simple retry attempt %d/%d for %s", attempt, self._max_retries, operation_name)
                    await asyncio.sleep(self._retry_delay)  # Fixed 1-second delay

                self.diagnostics_manager.add_timing_step(f"attempt_{attempt}_start")
                response = await self._execute_http_request(method, url, data)
                self.diagnostics_manager.add_timing_step("http_request_complete")

                result = await self._handle_response(response, url, endpoint)
                self.diagnostics_manager.add_timing_step("response_processed")

                if attempt > 0:
                    _LOGGER.info("Request succeeded on attempt %d for %s", attempt + 1, operation_name)

                self.diagnostics_manager.log_connection_state("request_success", {
                    "method": method,
                    "endpoint": endpoint,
                    "response_size": len(str(result)) if result else 0,
                    "attempts": attempt + 1
                })

                return result

            except (WLEDConnectionError, WLEDNetworkError, WLEDTimeoutError, WLEDDNSResolutionError,
                    WLEDConnectionRefusedError, WLEDConnectionResetError, WLEDSSLError, WLEDHTTPError,
                    WLEDSessionError, WLEDConnectionStalledError) as err:
                last_exception = err
                if attempt < self._max_retries:
                    _LOGGER.debug("Request failed (attempt %d), retrying: %s", attempt + 1, err)
                    continue
                else:
                    _LOGGER.error("Simple retry failed after %d attempts for %s", self._max_retries + 1, operation_name)
                    break

            except Exception as err:
                # For unexpected errors, don't retry
                connection_error = WLEDConnectionError(
                    f"Unexpected error connecting to WLED device at {self.host}: {err}",
                    host=self.host,
                    operation=operation_name,
                    original_error=err
                )
                self.diagnostics_manager.record_error("WLEDConnectionError", {
                    "message": str(connection_error),
                    "error_type": type(err).__name__,
                    "endpoint": endpoint,
                    "method": method
                })
                raise connection_error

        # All retry attempts failed, raise the last exception
        raise last_exception

    async def _request_with_enhanced_retry(
        self, method: str, url: str, endpoint: str, data: Optional[Dict[str, Any]], operation_name: str
    ) -> Dict[str, Any]:
        """Execute request with enhanced retry logic (original behavior)."""
        try:
            self.diagnostics_manager.add_timing_step("request_setup")
            response = await self._execute_http_request(method, url, data)
            self.diagnostics_manager.add_timing_step("http_request_complete")

            result = await self._handle_response(response, url, endpoint)
            self.diagnostics_manager.add_timing_step("response_processed")

            self.diagnostics_manager.log_connection_state("request_success", {
                "method": method,
                "endpoint": endpoint,
                "response_size": len(str(result)) if result else 0
            })

            return result

        except (WLEDConnectionError, WLEDNetworkError, WLEDTimeoutError, WLEDDNSResolutionError,
                WLEDConnectionRefusedError, WLEDConnectionResetError, WLEDSSLError, WLEDHTTPError,
                WLEDSessionError, WLEDConnectionStalledError):
            # Re-raise all our enhanced exceptions
            raise

        except ServerTimeoutError as err:
            timeout_error = WLEDConnectionTimeoutError(
                f"Request to WLED device at {self.host} timed out after {TIMEOUT} seconds",
                host=self.host,
                operation=operation_name,
                original_error=err,
                timeout_stage="server"
            )
            self.diagnostics_manager.record_error("WLEDConnectionTimeoutError", {
                "message": str(timeout_error),
                "timeout_stage": "server",
                "endpoint": endpoint,
                "method": method
            })
            raise timeout_error

        except aiohttp.ClientConnectorError as err:
            # This should be handled by _handle_connector_error, but add a fallback
            network_error = WLEDNetworkError(
                f"Connection error to WLED device at {self.host}: {err}",
                host=self.host,
                operation=operation_name,
                original_error=err
            )
            self.diagnostics_manager.record_error("WLEDNetworkError", {
                "message": str(network_error),
                "error_details": str(err),
                "endpoint": endpoint,
                "method": method
            })
            raise network_error

        except aiohttp.ClientResponseError as err:
            self._handle_response_error(err, method, endpoint)
            # This method will always raise an exception

        except (ClientError, asyncio.TimeoutError) as err:
            network_error = WLEDNetworkError(
                f"Network error connecting to WLED device at {self.host}: {err}. Please check your network connection and the device's IP address.",
                host=self.host,
                operation=operation_name,
                original_error=err
            )
            self.diagnostics_manager.record_error("WLEDNetworkError", {
                "message": str(network_error),
                "error_type": type(err).__name__,
                "endpoint": endpoint,
                "method": method
            })
            raise network_error

        except json.JSONDecodeError as err:
            json_error = WLEDInvalidJSONError(
                f"WLED device at {self.host} returned invalid JSON response: {err}",
                host=self.host,
                endpoint=endpoint,
                response_data="<unavailable>"
            )
            self.diagnostics_manager.record_error("WLEDInvalidJSONError", {
                "message": str(json_error),
                "json_error": str(err),
                "endpoint": endpoint,
                "method": method
            })
            raise json_error

        except Exception as err:
            connection_error = WLEDConnectionError(
                f"Unexpected error connecting to WLED device at {self.host}: {err}",
                host=self.host,
                operation=operation_name,
                original_error=err
            )
            self.diagnostics_manager.record_error("WLEDConnectionError", {
                "message": str(connection_error),
                "error_type": type(err).__name__,
                "endpoint": endpoint,
                "method": method
            })
            raise connection_error

    def _handle_response_error(self, err: aiohttp.ClientResponseError, method: str, endpoint: str) -> None:
        """
        Handle HTTP response errors with appropriate exception types.

        Maps HTTP status codes to specific WLED exception types for better error handling:
        - 401: Authentication required
        - 404: Endpoint not found
        - 5xx: Server errors
        - Other: Connection errors

        Args:
            err: The aiohttp ClientResponseError that occurred
            method: HTTP method being used
            endpoint: API endpoint being requested

        Raises:
            WLEDAuthenticationError: For 401 status codes
            WLEDInvalidResponseError: For 404 status codes
            WLEDConnectionError: For other HTTP errors
        """
        if err.status == 401:
            error_msg = f"WLED device at {self.host} requires authentication"
            _LOGGER.error(error_msg)
            raise WLEDAuthenticationError(error_msg, host=self.host) from err
        elif err.status == 404:
            error_msg = f"WLED device at {self.host} returned 404 Not Found for endpoint {endpoint}. The device may not support this feature."
            _LOGGER.error(error_msg)
            raise WLEDInvalidResponseError(error_msg, host=self.host, endpoint=endpoint) from err
        elif 500 <= err.status < 600:
            error_msg = f"WLED device at {self.host} encountered a server error (HTTP {err.status}). The device may be overloaded or have an internal error."
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, operation=f"{method} {endpoint}", original_error=err) from err
        else:
            error_msg = f"WLED device at {self.host} returned HTTP {err.status}: {err.message}"
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, operation=f"{method} {endpoint}", original_error=err) from err

    async def _handle_response(self, response: aiohttp.ClientResponse, url: str, endpoint: str) -> Dict[str, Any]:
        """Handle HTTP response with comprehensive diagnostics and enhanced error handling."""
        self.diagnostics_manager.add_timing_step("response_handling_start")

        response_info = {
            "status": response.status,
            "content_type": response.headers.get('Content-Type', 'unknown'),
            "content_length": response.headers.get('Content-Length', 'unknown'),
            "headers": dict(response.headers)
        }

        self.diagnostics_manager.log_connection_state("response_received", response_info)

        _LOGGER.debug("Received response from %s: status=%s, content_type=%s", url, response.status, response.headers.get('Content-Type', 'unknown'))

        try:
            self.diagnostics_manager.add_timing_step("response_read_start")
            response_text = await response.text()
            self.diagnostics_manager.add_timing_step("response_read_complete")

            # Log response info for debugging
            if response_text:
                _LOGGER.debug("Response body length: %d characters", len(response_text))
                if len(response_text) < 200:  # Log short responses completely
                    _LOGGER.debug("Response body: %s", response_text)
                else:
                    _LOGGER.debug("Response body (first 200 chars): %s", response_text[:200])

                self.diagnostics_manager.log_connection_state("response_body_processed", {
                    "response_length": len(response_text),
                    "content_preview": response_text[:100] if response_text else ""
                })

            try:
                response.raise_for_status()
                self.diagnostics_manager.add_timing_step("response_status_validated")
            except aiohttp.ClientResponseError as err:
                # Log the response text for debugging
                if response_text:
                    _LOGGER.debug("Error response body: %s", response_text[:500])  # Limit to first 500 chars
                else:
                    _LOGGER.debug("Error response: no body content")

                http_error = WLEDHTTPError(
                    f"WLED device at {self.host} returned HTTP {err.status}: {err.message}",
                    host=self.host,
                    operation=f"response_handling_{endpoint}",
                    original_error=err,
                    http_code=err.status,
                    response_headers=dict(response.headers)
                )
                self.diagnostics_manager.record_error("WLEDHTTPError", {
                    "message": str(http_error),
                    "http_status": err.status,
                    "error_message": err.message,
                    "endpoint": endpoint,
                    "response_preview": response_text[:200] if response_text else ""
                })
                raise http_error

            # Handle empty responses
            if not response_text.strip():
                invalid_response_error = WLEDInvalidResponseError(
                    f"WLED device at {self.host} returned empty response for {endpoint}",
                    host=self.host,
                    endpoint=endpoint,
                    response_data="<empty>"
                )
                self.diagnostics_manager.record_error("WLEDInvalidResponseError", {
                    "message": str(invalid_response_error),
                    "error_type": "empty_response",
                    "endpoint": endpoint
                })
                raise invalid_response_error

            try:
                self.diagnostics_manager.add_timing_step("json_parsing_start")
                parsed_response = json.loads(response_text)
                self.diagnostics_manager.add_timing_step("json_parsing_complete")

                self.diagnostics_manager.log_connection_state("response_parsing_success", {
                    "json_keys": list(parsed_response.keys()) if isinstance(parsed_response, dict) else "not_dict",
                    "response_type": type(parsed_response).__name__
                })

                return parsed_response

            except json.JSONDecodeError as err:
                json_error = WLEDInvalidJSONError(
                    f"Failed to parse JSON response from WLED device at {self.host}: {err}",
                    host=self.host,
                    endpoint=endpoint,
                    response_data=response_text[:500] if response_text else ""
                )
                self.diagnostics_manager.record_error("WLEDInvalidJSONError", {
                    "message": str(json_error),
                    "json_error": str(err),
                    "endpoint": endpoint,
                    "response_preview": response_text[:200] if response_text else ""
                })
                raise json_error

        except Exception as err:
            # Re-raise our WLED exceptions
            if isinstance(err, (WLEDHTTPError, WLEDInvalidResponseError, WLEDInvalidJSONError)):
                raise

            # Handle other unexpected errors
            unexpected_error = WLEDConnectionError(
                f"Unexpected error handling response from WLED device at {self.host}: {err}",
                host=self.host,
                operation=f"response_handling_{endpoint}",
                original_error=err
            )
            self.diagnostics_manager.record_error("WLEDConnectionError", {
                "message": str(unexpected_error),
                "error_type": type(err).__name__,
                "endpoint": endpoint
            })
            raise unexpected_error

    async def get_state(self) -> Dict[str, Any]:
        """Get the current state of the WLED device."""
        try:
            response = await self._request("GET", API_STATE)
            if not isinstance(response, dict):
                error_msg = f"WLED device at {self.host} returned invalid state response format"
                _LOGGER.error(error_msg)
                raise WLEDInvalidStateError(error_msg, host=self.host, endpoint=API_STATE, response_data=str(response))

            _LOGGER.debug("Successfully retrieved state from %s", self.host)
            return response

        except (WLEDConnectionError, WLEDInvalidResponseError):
            # Re-raise existing exceptions
            raise
        except Exception as err:
            error_msg = f"Unexpected error getting state from WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, operation="GET state", original_error=err) from err

    async def get_info(self) -> Dict[str, Any]:
        """Get information about the WLED device."""
        try:
            response = await self._request("GET", API_INFO)
            if not isinstance(response, dict):
                error_msg = f"WLED device at {self.host} returned invalid info response format"
                _LOGGER.error(error_msg)
                raise WLEDInvalidStateError(error_msg, host=self.host, endpoint=API_INFO, response_data=str(response))

            # Validate that required fields are present
            if "name" not in response:
                _LOGGER.warning("WLED device at %s info response missing 'name' field", self.host)

            _LOGGER.debug("Successfully retrieved info from %s", self.host)
            return response

        except (WLEDConnectionError, WLEDInvalidResponseError):
            # Re-raise existing exceptions
            raise
        except Exception as err:
            error_msg = f"Unexpected error getting info from WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, operation="GET info", original_error=err) from err

    async def get_full_state(self) -> Dict[str, Any]:
        """Get the full state including info, effects, and palettes."""
        try:
            response = await self._request("GET", "")
            if not isinstance(response, dict):
                error_msg = f"WLED device at {self.host} returned invalid full state response format"
                _LOGGER.error(error_msg)
                raise WLEDInvalidStateError(error_msg, host=self.host, endpoint="/", response_data=str(response))

            # Validate expected structure
            required_sections = ["info", "state"]
            for section in required_sections:
                if section not in response:
                    _LOGGER.warning("WLED device at %s full state response missing required section: %s", self.host, section)

            _LOGGER.debug("Successfully retrieved full state from %s", self.host)
            return response

        except (WLEDConnectionError, WLEDInvalidResponseError):
            # Re-raise existing exceptions
            raise
        except Exception as err:
            error_msg = f"Unexpected error getting full state from WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, operation="GET full state", original_error=err) from err

    async def update_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Update the state of the WLED device."""
        if not isinstance(state, dict) or not state:
            error_msg = f"Invalid state data provided to WLED device at {self.host}: {state}"
            _LOGGER.error(error_msg)
            raise WLEDInvalidCommandError(error_msg, command=state, host=self.host)

        try:
            response = await self._request("POST", API_STATE, data=state)
            if not isinstance(response, dict):
                error_msg = f"WLED device at {self.host} returned invalid response for state update"
                _LOGGER.error(error_msg)
                raise WLEDInvalidStateError(error_msg, host=self.host, endpoint=API_STATE, response_data=str(response))

            _LOGGER.debug("Successfully updated state on %s: %s", self.host, state)
            return response

        except (WLEDConnectionError, WLEDInvalidResponseError, WLEDCommandError):
            # Re-raise existing exceptions
            raise
        except Exception as err:
            error_msg = f"Unexpected error updating state on WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDCommandError(error_msg, command=state, host=self.host, original_error=err) from err

    async def turn_on(
        self,
        brightness: Optional[int] = None,
        transition: Optional[int] = None,
        preset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Turn on the WLED device."""
        state = {"on": True}

        if brightness is not None:
            state["bri"] = brightness
        if transition is not None:
            state["transition"] = transition
        if preset is not None:
            state["ps"] = preset

        return await self.update_state(state)

    async def turn_off(self, transition: Optional[int] = None) -> Dict[str, Any]:
        """Turn off the WLED device."""
        state = {"on": False}

        if transition is not None:
            state["transition"] = transition

        return await self.update_state(state)

    async def set_brightness(self, brightness: int, transition: Optional[int] = None) -> Dict[str, Any]:
        """Set the brightness of the WLED device."""
        state = {"bri": brightness}

        if transition is not None:
            state["transition"] = transition

        return await self.update_state(state)

    async def set_preset(self, preset: int) -> Dict[str, Any]:
        """Set a preset on the WLED device."""
        state = {"ps": preset}
        return await self.update_state(state)

    async def set_effect(
        self,
        effect: int,
        speed: Optional[int] = None,
        intensity: Optional[int] = None,
        palette: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Set an effect on the WLED device."""
        state = {"seg": [{"fx": effect}]}

        if speed is not None:
            state["seg"][0]["sx"] = speed
        if intensity is not None:
            state["seg"][0]["ix"] = intensity
        if palette is not None:
            state["seg"][0]["pal"] = palette

        return await self.update_state(state)

    async def get_presets(self) -> WLEDPresetsData:
        """Get presets and playlists from the WLED device with enhanced error handling."""
        try:
            response = await self._request("GET", API_PRESETS)
            if not isinstance(response, dict):
                error_msg = f"WLED device at {self.host} returned invalid presets response format"
                _LOGGER.error(error_msg)
                raise WLEDInvalidStateError(error_msg, host=self.host, endpoint=API_PRESETS, response_data=str(response))

            # Parse the response into our data model
            presets_data = WLEDPresetsData.from_dict(response)

            if not presets_data.presets and not presets_data.playlists:
                _LOGGER.warning("No presets or playlists found on WLED device at %s", self.host)
            else:
                _LOGGER.debug(
                    "Successfully retrieved %d presets and %d playlists from %s",
                    len(presets_data.presets),
                    len(presets_data.playlists),
                    self.host
                )

            return presets_data

        except (WLEDConnectionError, WLEDInvalidResponseError):
            # Re-raise existing exceptions with more context
            _LOGGER.error("Failed to retrieve presets from WLED device at %s due to connection/response error", self.host)
            raise
        except ValueError as err:
            error_msg = f"Failed to parse presets data from WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDPresetError(error_msg) from err
        except Exception as err:
            error_msg = f"Unexpected error getting presets from WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDPresetError(error_msg) from err

    async def activate_playlist(self, playlist: int) -> Dict[str, Any]:
        """Activate a playlist on the WLED device with enhanced error handling."""
        if not isinstance(playlist, int) or playlist < 0:
            error_msg = f"Invalid playlist ID provided: {playlist}. Must be a non-negative integer."
            _LOGGER.error(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist)

        try:
            state = {"pl": playlist}
            _LOGGER.debug("Activating playlist %d on WLED device at %s", playlist, self.host)
            response = await self.update_state(state)
            _LOGGER.debug("Successfully activated playlist %d on %s", playlist, self.host)
            return response

        except (WLEDConnectionError, WLEDCommandError):
            # Re-raise existing exceptions with playlist context
            raise
        except Exception as err:
            error_msg = f"Unexpected error activating playlist {playlist} on WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist) from err

    async def test_connection(self) -> bool:
        """Test connection to the WLED device with enhanced error handling."""
        try:
            _LOGGER.debug("Testing connection to WLED device at %s", self.host)
            await self.get_info()
            _LOGGER.debug("Connection test successful for WLED device at %s", self.host)
            return True
        except WLEDTimeoutError as err:
            _LOGGER.warning("Connection test to WLED device at %s timed out: %s", self.host, err)
            return False
        except WLEDNetworkError as err:
            _LOGGER.warning("Connection test to WLED device at %s failed due to network error: %s", self.host, err)
            return False
        except WLEDAuthenticationError as err:
            _LOGGER.warning("Connection test to WLED device at %s failed due to authentication error: %s", self.host, err)
            return False
        except WLEDConnectionError as err:
            _LOGGER.warning("Connection test to WLED device at %s failed: %s", self.host, err)
            return False
        except Exception as err:
            _LOGGER.error("Unexpected error during connection test to WLED device at %s: %s", self.host, err)
            return False

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._close_session and self._session:
            await self._session.close()

    async def __aenter__(self) -> "WLEDJSONAPIClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()