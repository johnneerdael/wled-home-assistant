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
    WLEDInvalidCommandError,
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
    WLEDConnectionLifecycleError,
    WLEDConnectionDiagnostics,
)
from .models import (
    WLEDPresetsData,
    WLEDEssentialState,
    WLEDEssentialPresetsData,
    WLEDEssentialPreset,
    WLEDEssentialPlaylist,
)

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
                # Simplified configuration for maximum compatibility with response buffering
                self._session_config = {
                    "connector": {
                        # Optimized for reliable response handling
                        "enable_cleanup_closed": True,  # Enable cleanup for stability
                        "force_close": False,  # Don't force close - let response reading complete
                        "limit": 1,  # Single connection
                        "limit_per_host": 1,
                        "ttl_dns_cache": 300,  # Enable DNS cache for reliability
                        "use_dns_cache": True,
                        "keepalive_timeout": 30,  # Enable keepalive for connection reuse
                        "disable_cleanup_closed": False,  # Enable cleanup
                        "family": 0,  # Allow both IPv4 and IPv6
                        "ssl": False,  # Disable SSL (WLED uses HTTP)
                    },
                    "timeout": {
                        "total": 15,  # Reduced timeout for faster failure detection
                        "connect": 5,  # Faster connection timeout
                        "sock_read": 10,  # Separate read timeout
                    },
                    "headers": {
                        # Minimal headers only
                        "User-Agent": "Home-Assistant-WLED-JSONAPI/1.0",
                        "Accept": "application/json, text/plain, */*",
                        "Connection": "close",  # Request connection close after response
                    },
                    "auto_decompress": False,  # Disable auto decompression
                    "read_timeout": 10,  # Explicit read timeout
                    "conn_timeout": 5,  # Explicit connection timeout
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
                # Create connector with enhanced configuration for simple client
                connector_config = self._session_config["connector"].copy()

                # Add additional connector options for reliability
                if self.use_simple_client:
                    connector_config.update({
                        "limit_per_host": 1,
                        "use_dns_cache": True,
                        "keepalive_timeout": 30,
                    })

                connector = aiohttp.TCPConnector(**connector_config)

                # Create timeout with enhanced error handling
                timeout_config = self._session_config["timeout"].copy()
                if self.use_simple_client:
                    # Use explicit timeout values for better error handling
                    timeout = aiohttp.ClientTimeout(
                        total=timeout_config.get("total", 15),
                        connect=timeout_config.get("connect", 5),
                        sock_read=timeout_config.get("sock_read", 10)
                    )
                else:
                    timeout = aiohttp.ClientTimeout(**timeout_config)

                # Create session with additional headers for simple client
                session_kwargs = {
                    "connector": connector,
                    "timeout": timeout,
                }

                if "headers" in self._session_config:
                    session_kwargs["headers"] = self._session_config["headers"]

                if "auto_decompress" in self._session_config:
                    session_kwargs["auto_decompress"] = self._session_config["auto_decompress"]

                self._session = ClientSession(**session_kwargs)

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
        Execute the HTTP request and return the response with comprehensive diagnostics and connection lifecycle management.

        Handles GET and POST requests with detailed logging, timing, and error handling.
        Implements enhanced connection lifecycle management to prevent premature connection closure.

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
        connection_lifecycle = WLEDConnectionLifecycleManager(self.host, self.diagnostics_manager)

        async with self.diagnostics_manager.timed_request(operation_name):
            try:
                # Connection Phase 1: Pre-request session validation
                session = await self._ensure_session()

                # Enhanced session state validation
                await connection_lifecycle.validate_session_health(session, method, url)

                # Connection Phase 2: Connection establishment monitoring
                self.diagnostics_manager.log_connection_state("connection_establishment_start", {
                    "method": method,
                    "url": url,
                    "operation": operation_name
                })

                # Execute the appropriate request method with connection lifecycle monitoring
                if method.upper() == "GET":
                    response = await connection_lifecycle.execute_request_with_lifecycle_management(
                        session, "GET", url, operation_name
                    )
                elif method.upper() == "POST":
                    response = await connection_lifecycle.execute_request_with_lifecycle_management(
                        session, "POST", url, operation_name, data
                    )
                else:
                    error_msg = f"Unsupported HTTP method: {method}"
                    self.diagnostics_manager.record_error("WLEDCommandError", {
                        "message": error_msg,
                        "method": method,
                        "url": url
                    })
                    raise ValueError(error_msg)

                # Connection Phase 3: Post-request connection validation
                await connection_lifecycle.validate_connection_health(response, "request_completed")

                # Log successful request with connection state
                self.diagnostics_manager.log_connection_state("request_execution_complete", {
                    "method": method,
                    "url": url,
                    "response_status": response.status,
                    "connection_state": getattr(response.connection, 'state', 'unknown') if hasattr(response, 'connection') else 'no_connection_info'
                })

                return response

            except (WLEDConnectionError, WLEDNetworkError, WLEDTimeoutError, WLEDConnectionLifecycleError):
                # Re-raise WLED exceptions including new lifecycle errors
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
                # Connection Phase 4: Connection lifecycle cleanup and diagnostics
                lifecycle_summary = connection_lifecycle.get_connection_lifecycle_summary()
                self.diagnostics_manager.log_connection_state("request_lifecycle_complete", lifecycle_summary)

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
        """Handle HTTP response with enhanced connection lifecycle management to prevent premature closure."""
        self.diagnostics_manager.add_timing_step("response_handling_start")

        # Connection Phase 1: Initial connection state validation
        await self._validate_connection_state("response_handling_start", response)

        response_info = {
            "status": response.status,
            "content_type": response.headers.get('Content-Type', 'unknown'),
            "content_length": response.headers.get('Content-Length', 'unknown'),
            "headers": dict(response.headers),
            "connection_state": getattr(response.connection, 'state', 'unknown') if hasattr(response, 'connection') else 'no_connection_info'
        }

        self.diagnostics_manager.log_connection_state("response_received", response_info)

        _LOGGER.debug("Received response from %s: status=%s, content_type=%s, connection_state=%s",
                     url, response.status, response.headers.get('Content-Type', 'unknown'),
                     response_info.get('connection_state'))

        # Enhanced connection lifecycle management with comprehensive state tracking
        response_text = None
        response_buffer = None
        connection_lifecycle = WLEDConnectionLifecycleManager(self.host, self.diagnostics_manager)

        try:
            # Connection Phase 2: Validate connection health before response processing
            await connection_lifecycle.validate_connection_health(response, "before_response_processing")

            # Stage 1: Validate HTTP status with connection state monitoring
            self.diagnostics_manager.add_timing_step("status_validation_start")

            # Enhanced status validation with connection state check
            await connection_lifecycle.monitor_connection_during_operation(response, "status_validation", async_func=lambda: self._validate_response_status(response, endpoint))

            self.diagnostics_manager.add_timing_step("status_validation_complete")

            # Connection Phase 3: Pre-read connection validation and state monitoring
            await connection_lifecycle.validate_connection_health(response, "before_response_reading")

            # Stage 2: Enhanced response reading with connection lifecycle management
            self.diagnostics_manager.add_timing_step("response_buffering_start")

            try:
                # Use connection-managed response reading with timeout and retry logic
                response_text, response_buffer = await connection_lifecycle.read_response_with_lifecycle_management(
                    response, endpoint, self.debug_mode
                )

                self.diagnostics_manager.add_timing_step("response_bytes_read")
                self.diagnostics_manager.add_timing_step("response_decoded")

                # Connection Phase 4: Post-read connection validation
                await connection_lifecycle.validate_connection_health(response, "after_response_reading")

            except WLEDConnectionLifecycleError as lifecycle_err:
                # Handle connection lifecycle-specific errors
                self.diagnostics_manager.record_error("WLEDConnectionLifecycleError", {
                    "message": str(lifecycle_err),
                    "lifecycle_stage": lifecycle_err.lifecycle_stage,
                    "connection_state": lifecycle_err.connection_state,
                    "endpoint": endpoint,
                    "original_error": str(lifecycle_err.original_error) if lifecycle_err.original_error else "none"
                })
                raise lifecycle_err

            # Connection Phase 5: Validate response content with connection state check
            await connection_lifecycle.validate_connection_health(response, "before_content_validation")

            if not response_text or not response_text.strip():
                invalid_response_error = WLEDInvalidResponseError(
                    f"WLED device at {self.host} returned empty response for {endpoint}",
                    host=self.host,
                    endpoint=endpoint,
                    response_data="<empty>"
                )
                self.diagnostics_manager.record_error("WLEDInvalidResponseError", {
                    "message": str(invalid_response_error),
                    "error_type": "empty_response",
                    "endpoint": endpoint,
                    "connection_state": getattr(response.connection, 'state', 'unknown') if hasattr(response, 'connection') else 'no_connection_info'
                })
                raise invalid_response_error

            # Connection Phase 6: Pre-parsing connection validation
            await connection_lifecycle.validate_connection_health(response, "before_json_parsing")

            # Stage 3: Enhanced JSON parsing with connection lifecycle monitoring
            self.diagnostics_manager.add_timing_step("json_parsing_start")

            try:
                # Monitor connection during JSON parsing to prevent closure during processing
                parsed_response = await connection_lifecycle.monitor_connection_during_operation(
                    response,
                    "json_parsing",
                    async_func=lambda: self._parse_json_response(response_text, endpoint, response_buffer)
                )

                self.diagnostics_manager.add_timing_step("json_parsing_complete")

                # Log successful parsing for debugging
                if self.debug_mode or len(response_text) < 200:
                    _LOGGER.debug("Response body: %s", response_text)
                else:
                    _LOGGER.debug("Response body length: %d characters", len(response_text))

                self.diagnostics_manager.log_connection_state("response_parsing_success", {
                    "json_keys": list(parsed_response.keys()) if isinstance(parsed_response, dict) else "not_dict",
                    "response_type": type(parsed_response).__name__,
                    "response_length": len(response_text),
                    "connection_state": getattr(response.connection, 'state', 'unknown') if hasattr(response, 'connection') else 'no_connection_info'
                })

                # Connection Phase 7: Final connection validation before data extraction
                await connection_lifecycle.validate_connection_health(response, "before_data_extraction")

                # Extract essential parameters using the streamlined extraction method
                if isinstance(parsed_response, dict):
                    essential_data = self._extract_essential_state_fields(parsed_response)

                    # If we have essential data, return it for reliability and performance
                    if essential_data:
                        _LOGGER.debug("Extracted essential parameters from %s: %s", self.host, list(essential_data.keys()))

                        # Connection Phase 8: Final success validation
                        await connection_lifecycle.validate_connection_health(response, "processing_complete")

                        return essential_data
                    else:
                        # Return full response if no essential parameters found (fallback)
                        _LOGGER.debug("No essential parameters found in response from %s, returning full response", self.host)

                        # Connection Phase 8: Final success validation
                        await connection_lifecycle.validate_connection_health(response, "processing_complete")

                        return parsed_response
                else:
                    # Connection Phase 8: Final success validation
                    await connection_lifecycle.validate_connection_health(response, "processing_complete")
                    return parsed_response

            except json.JSONDecodeError as err:
                # Try to extract partial information from malformed JSON
                json_error = WLEDInvalidJSONError(
                    f"Failed to parse JSON response from WLED device at {self.host}: {err}",
                    host=self.host,
                    endpoint=endpoint,
                    response_data=response_buffer[:500] if response_buffer else ""
                )
                self.diagnostics_manager.record_error("WLEDInvalidJSONError", {
                    "message": str(json_error),
                    "json_error": str(err),
                    "endpoint": endpoint,
                    "response_preview": response_buffer[:200] if response_buffer else "",
                    "connection_state": getattr(response.connection, 'state', 'unknown') if hasattr(response, 'connection') else 'no_connection_info'
                })
                raise json_error

        except (WLEDHTTPError, WLEDInvalidResponseError, WLEDConnectionResetError, WLEDInvalidJSONError, WLEDConnectionLifecycleError):
            # Re-raise our specific WLED exceptions
            raise

        except Exception as err:
            # Handle other unexpected errors with connection lifecycle context
            unexpected_error = WLEDConnectionError(
                f"Unexpected error handling response from WLED device at {self.host}: {err}",
                host=self.host,
                operation=f"response_handling_{endpoint}",
                original_error=err
            )
            self.diagnostics_manager.record_error("WLEDConnectionError", {
                "message": str(unexpected_error),
                "error_type": type(err).__name__,
                "endpoint": endpoint,
                "response_preview": response_buffer[:200] if response_buffer else "",
                "connection_state": getattr(response.connection, 'state', 'unknown') if hasattr(response, 'connection') else 'no_connection_info'
            })
            raise unexpected_error
        finally:
            # Connection Phase 9: Connection cleanup logging (but don't actually close - let context manager handle it)
            self.diagnostics_manager.add_timing_step("response_handling_complete")
            self.diagnostics_manager.log_connection_state("response_handling_finished", {
                "endpoint": endpoint,
                "response_length": len(response_text) if response_text else 0,
                "processing_successful": response_text is not None
            })

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

    def _extract_essential_state_fields(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only essential state fields from WLED response data.

        This method implements targeted JSON parsing to extract only the required parameters:
        - on/off state (state.on)
        - brightness (state.bri)
        - preset ID and preset name
        - playlist ID and playlist name

        Args:
            response_data: Raw JSON response data from WLED device

        Returns:
            Dictionary containing only essential fields
        """
        if not isinstance(response_data, dict):
            return {}

        essential_data = {}

        # Extract essential state fields with direct path access
        # Use direct field access for maximum performance
        if 'on' in response_data:
            essential_data['on'] = response_data['on']

        if 'bri' in response_data:
            essential_data['bri'] = response_data['bri']

        if 'ps' in response_data:
            essential_data['ps'] = response_data['ps']

        if 'pl' in response_data:
            essential_data['pl'] = response_data['pl']

        # Only include segment info if absolutely necessary for basic functionality
        # Skip complex segment processing to improve performance
        if 'seg' in response_data and isinstance(response_data['seg'], list) and len(response_data['seg']) > 0:
            # Only extract the first segment's essential info
            first_segment = response_data['seg'][0]
            if isinstance(first_segment, dict):
                segment_essential = {}
                if 'on' in first_segment:
                    segment_essential['on'] = first_segment['on']
                if 'bri' in first_segment:
                    segment_essential['bri'] = first_segment['bri']
                if 'fx' in first_segment:
                    segment_essential['fx'] = first_segment['fx']
                if segment_essential:
                    essential_data['seg'] = [segment_essential]

        return essential_data

    def _extract_essential_preset_fields(self, preset_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only essential preset information from preset response data.

        Args:
            preset_data: Raw preset JSON response data

        Returns:
            Dictionary containing only essential preset information
        """
        if not isinstance(preset_data, dict):
            return {}

        essential_preset = {}

        # Only extract the name field for presets - skip complex state data
        if 'n' in preset_data:
            essential_preset['n'] = preset_data['n']

        # Include basic on/brightness state if present
        if 'on' in preset_data:
            essential_preset['on'] = preset_data['on']

        if 'bri' in preset_data:
            essential_preset['bri'] = preset_data['bri']

        return essential_preset

    def _extract_essential_playlist_fields(self, playlist_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only essential playlist information from playlist response data.

        Args:
            playlist_data: Raw playlist JSON response data

        Returns:
            Dictionary containing only essential playlist information
        """
        if not isinstance(playlist_data, dict):
            return {}

        essential_playlist = {}

        # Only extract the name field for playlists
        if 'n' in playlist_data:
            essential_playlist['n'] = playlist_data['n']

        # Include basic playlist configuration
        if 'playlist' in playlist_data and isinstance(playlist_data['playlist'], dict):
            playlist_config = {}
            if 'ps' in playlist_data['playlist']:
                playlist_config['ps'] = playlist_data['playlist']['ps']
            if 'dur' in playlist_data['playlist']:
                playlist_config['dur'] = playlist_data['playlist']['dur']
            if playlist_config:
                essential_playlist['playlist'] = playlist_config

        return essential_playlist

    async def get_essential_state(self) -> WLEDEssentialState:
        """
        Get only essential state parameters from the WLED device.

        This method implements streamlined data extraction that focuses only on:
        - on/off state (state.on)
        - brightness (state.bri)
        - preset ID and preset name
        - playlist ID and playlist name

        Returns:
            WLEDEssentialState object containing only essential parameters

        Raises:
            WLEDConnectionError: If connection to device fails
            WLEDInvalidResponseError: If device returns invalid response
        """
        try:
            _LOGGER.debug("Getting essential state from WLED device at %s", self.host)

            # Use the state endpoint for minimal data
            response = await self._request("GET", API_STATE)

            if not isinstance(response, dict):
                error_msg = f"WLED device at {self.host} returned invalid state response format"
                _LOGGER.error(error_msg)
                raise WLEDInvalidStateError(error_msg, host=self.host, endpoint=API_STATE, response_data=str(response))

            # Extract only essential parameters using targeted parsing
            essential_response = self._extract_essential_state_fields(response)

            # Create essential state object
            essential_state = WLEDEssentialState.from_state_response(essential_response)

            _LOGGER.debug("Successfully extracted essential state from %s: on=%s, brightness=%s, preset=%s, playlist=%s",
                         self.host, essential_state.on, essential_state.brightness,
                         essential_state.preset_id, essential_state.playlist_id)

            return essential_state

        except (WLEDConnectionError, WLEDInvalidResponseError, WLEDInvalidStateError):
            # Re-raise existing exceptions
            raise
        except Exception as err:
            error_msg = f"Unexpected error getting essential state from WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, operation="GET essential state", original_error=err) from err

    async def get_essential_presets(self) -> WLEDEssentialPresetsData:
        """
        Get only essential presets and playlists information from the WLED device.

        This method implements streamlined data extraction that focuses only on:
        - Preset names and IDs
        - Playlist names and IDs
        - Basic playlist configuration (preset IDs, durations)

        Skips complex preset state data, effects, and advanced configuration.

        Returns:
            WLEDEssentialPresetsData object containing only essential preset information

        Raises:
            WLEDConnectionError: If connection to device fails
            WLEDInvalidResponseError: If device returns invalid response
        """
        try:
            _LOGGER.debug("Getting essential presets from WLED device at %s", self.host)

            response = await self._request("GET", API_PRESETS)

            if not isinstance(response, dict):
                error_msg = f"WLED device at {self.host} returned invalid presets response format"
                _LOGGER.error(error_msg)
                raise WLEDInvalidStateError(error_msg, host=self.host, endpoint=API_PRESETS, response_data=str(response))

            # Process only essential preset information with targeted extraction
            essential_presets = {}
            essential_playlists = {}

            for key, value in response.items():
                # Skip non-numeric keys
                if not key.isdigit():
                    continue

                try:
                    # Check if this is a playlist (has "playlist" field)
                    if isinstance(value, dict) and "playlist" in value:
                        essential_playlist_data = self._extract_essential_playlist_fields(value)
                        if essential_playlist_data:
                            playlist = WLEDEssentialPlaylist.from_playlist_response(key, essential_playlist_data)
                            essential_playlists[playlist.id] = playlist
                    elif isinstance(value, dict):
                        # This is a regular preset
                        essential_preset_data = self._extract_essential_preset_fields(value)
                        if essential_preset_data:
                            preset = WLEDEssentialPreset.from_preset_response(key, essential_preset_data)
                            essential_presets[preset.id] = preset
                    else:
                        # Skip non-dict entries for reliability
                        continue

                except (ValueError, KeyError, TypeError) as err:
                    # Skip invalid entries for reliability and continue processing
                    _LOGGER.debug("Skipping invalid preset/playlist entry %s: %s", key, err)
                    continue

            essential_presets_data = WLEDEssentialPresetsData(
                presets=essential_presets,
                playlists=essential_playlists
            )

            if not essential_presets_data.presets and not essential_presets_data.playlists:
                _LOGGER.warning("No essential presets or playlists found on WLED device at %s", self.host)
            else:
                _LOGGER.debug(
                    "Successfully extracted %d essential presets and %d essential playlists from %s",
                    len(essential_presets_data.presets),
                    len(essential_presets_data.playlists),
                    self.host
                )

            return essential_presets_data

        except (WLEDConnectionError, WLEDInvalidResponseError, WLEDInvalidStateError):
            # Re-raise existing exceptions with more context
            _LOGGER.error("Failed to retrieve essential presets from WLED device at %s due to connection/response error", self.host)
            raise
        except Exception as err:
            error_msg = f"Unexpected error getting essential presets from WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDPresetError(error_msg) from err

    async def get_minimal_device_info(self) -> Dict[str, Any]:
        """
        Get minimal device information required for basic operation.

        Extracts only the essential device information:
        - Device name
        - MAC address for unique ID generation
        - Basic version info

        Returns:
            Dictionary containing minimal device information

        Raises:
            WLEDConnectionError: If connection to device fails
            WLEDInvalidResponseError: If device returns invalid response
        """
        try:
            _LOGGER.debug("Getting minimal device info from WLED device at %s", self.host)

            response = await self._request("GET", API_INFO)

            if not isinstance(response, dict):
                error_msg = f"WLED device at {self.host} returned invalid info response format"
                _LOGGER.error(error_msg)
                raise WLEDInvalidStateError(error_msg, host=self.host, endpoint=API_INFO, response_data=str(response))

            # Extract only essential info fields
            minimal_info = {}

            if 'name' in response:
                minimal_info['name'] = response['name']
            if 'mac' in response:
                minimal_info['mac'] = response['mac']
            if 'ver' in response:
                minimal_info['ver'] = response['ver']
            if 'leds' in response:
                minimal_info['leds'] = response['leds']
            if 'ip' in response:
                minimal_info['ip'] = response['ip']

            _LOGGER.debug("Successfully extracted minimal info from %s: %s", self.host, list(minimal_info.keys()))
            return minimal_info

        except (WLEDConnectionError, WLEDInvalidResponseError, WLEDInvalidStateError):
            # Re-raise existing exceptions
            raise
        except Exception as err:
            error_msg = f"Unexpected error getting minimal device info from WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, operation="GET minimal info", original_error=err) from err

    async def _validate_connection_state(self, stage: str, response: aiohttp.ClientResponse) -> None:
        """Validate connection state at various stages of request processing."""
        if not response:
            raise WLEDConnectionLifecycleError(
                f"Response object is None during {stage}",
                host=self.host,
                lifecycle_stage=stage,
                connection_state="no_response_object"
            )

        # Check connection state if available
        connection_state = "unknown"
        if hasattr(response, 'connection') and response.connection:
            connection_state = getattr(response.connection, 'state', 'unknown')

        # Check response status
        if hasattr(response, 'status') and response.status:
            if response.status >= 500:
                raise WLEDConnectionLifecycleError(
                    f"Server error during {stage}: HTTP {response.status}",
                    host=self.host,
                    lifecycle_stage=stage,
                    connection_state=connection_state,
                    http_status=response.status
                )

        self.diagnostics_manager.log_connection_state(f"connection_validated_{stage}", {
            "connection_state": connection_state,
            "response_status": getattr(response, 'status', 'unknown'),
            "stage": stage
        })

    def _validate_response_status(self, response: aiohttp.ClientResponse, endpoint: str) -> None:
        """Validate response status with enhanced error handling."""
        try:
            response.raise_for_status()
        except aiohttp.ClientResponseError as err:
            http_error = WLEDHTTPError(
                f"WLED device at {self.host} returned HTTP {err.status}: {err.message}",
                host=self.host,
                operation=f"status_validation_{endpoint}",
                original_error=err,
                http_code=err.status,
                response_headers=dict(response.headers)
            )
            raise http_error

    def _parse_json_response(self, response_text: str, endpoint: str, response_buffer: str) -> Dict[str, Any]:
        """Parse JSON response with enhanced error handling."""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as err:
            json_error = WLEDInvalidJSONError(
                f"Failed to parse JSON response from WLED device at {self.host}: {err}",
                host=self.host,
                endpoint=endpoint,
                response_data=response_buffer[:500] if response_buffer else ""
            )
            raise json_error

    async def close(self) -> None:
        """Close the HTTP session with enhanced connection lifecycle management."""
        if self._close_session and self._session:
            # Log connection cleanup
            self.diagnostics_manager.log_connection_state("session_cleanup_start", {
                "session_closed": self._session.closed,
                "cleanup_reason": "explicit_close"
            })

            try:
                await self._session.close()
                self.diagnostics_manager.log_connection_state("session_cleanup_complete", {
                    "cleanup_successful": True
                })
            except Exception as err:
                self.diagnostics_manager.record_error("WLEDSessionError", {
                    "message": f"Error during session cleanup: {err}",
                    "cleanup_reason": "explicit_close",
                    "original_error": str(err)
                })

    async def __aenter__(self) -> "WLEDJSONAPIClient":
        """Async context manager entry with connection lifecycle management."""
        self.diagnostics_manager.log_connection_state("context_manager_enter", {
            "host": self.host
        })
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with enhanced connection lifecycle management."""
        self.diagnostics_manager.log_connection_state("context_manager_exit", {
            "host": self.host,
            "exception_occurred": exc_type is not None,
            "exception_type": str(exc_type) if exc_type else None
        })

        # Enhanced cleanup with connection lifecycle validation
        if self._close_session and self._session:
            try:
                # Only close if not already closed
                if not self._session.closed:
                    await self._session.close()
                    self.diagnostics_manager.log_connection_state("context_manager_cleanup", {
                        "cleanup_successful": True,
                        "cleanup_reason": "context_manager_exit"
                    })
                else:
                    self.diagnostics_manager.log_connection_state("context_manager_cleanup", {
                        "cleanup_successful": True,
                        "cleanup_reason": "already_closed"
                    })
            except Exception as err:
                self.diagnostics_manager.record_error("WLEDSessionError", {
                    "message": f"Error during context manager cleanup: {err}",
                    "cleanup_reason": "context_manager_exit",
                    "original_error": str(err)
                })


class WLEDConnectionLifecycleManager:
    """Manages connection lifecycle for WLED devices to prevent premature connection closure."""

    def __init__(self, host: str, diagnostics_manager: WLEDConnectionDiagnosticsManager):
        self.host = host
        self.diagnostics_manager = diagnostics_manager
        self._connection_state_history = []
        self._lifecycle_start_time = time.time()

    async def validate_connection_health(self, response: aiohttp.ClientResponse, stage: str) -> None:
        """Validate connection health at different stages of the request lifecycle."""
        if not response:
            raise WLEDConnectionLifecycleError(
                f"Response object is None during {stage}",
                host=self.host,
                lifecycle_stage=stage,
                connection_state="no_response_object"
            )

        # Record connection state for tracking
        connection_info = {
            "stage": stage,
            "timestamp": time.time(),
            "response_status": getattr(response, 'status', 'unknown'),
            "content_length": response.headers.get('Content-Length', 'unknown') if hasattr(response, 'headers') else 'unknown',
            "content_type": response.headers.get('Content-Type', 'unknown') if hasattr(response, 'headers') else 'unknown'
        }

        # Check connection state if available
        if hasattr(response, 'connection') and response.connection:
            connection_info["connection_state"] = getattr(response.connection, 'state', 'unknown')
            connection_info["connection_closed"] = getattr(response.connection, 'closed', 'unknown')
        else:
            connection_info["connection_state"] = "no_connection_info"
            connection_info["connection_closed"] = "unknown"

        self._connection_state_history.append(connection_info)

        # Log for debugging
        self.diagnostics_manager.log_connection_state(f"health_check_{stage}", connection_info)

        # Perform health validations
        if hasattr(response, 'connection') and response.connection:
            connection_state = getattr(response.connection, 'state', 'unknown')
            connection_closed = getattr(response.connection, 'closed', True)

            if connection_closed and stage not in ["processing_complete", "response_handling_finished"]:
                raise WLEDConnectionLifecycleError(
                    f"Connection unexpectedly closed during {stage}",
                    host=self.host,
                    lifecycle_stage=stage,
                    connection_state=connection_state,
                    connection_closed=True
                )

        # Check response validity
        if hasattr(response, 'status') and response.status:
            if response.status >= 500:
                raise WLEDConnectionLifecycleError(
                    f"Server error detected during {stage}: HTTP {response.status}",
                    host=self.host,
                    lifecycle_stage=stage,
                    connection_state=connection_info.get("connection_state", "unknown"),
                    http_status=response.status
                )

    async def monitor_connection_during_operation(self, response: aiohttp.ClientResponse, operation_name: str, async_func) -> Any:
        """Monitor connection state during async operations to prevent premature closure."""
        operation_start = time.time()

        try:
            # Pre-operation connection validation
            await self.validate_connection_health(response, f"before_{operation_name}")

            # Execute the operation
            result = await async_func()

            # Post-operation connection validation
            await self.validate_connection_health(response, f"after_{operation_name}")

            # Log successful operation
            operation_duration = (time.time() - operation_start) * 1000
            self.diagnostics_manager.add_timing_step(f"{operation_name}_with_monitoring")

            if self.diagnostics_manager.debug_mode:
                _LOGGER.debug("🔗 Connection monitored operation '%s' completed in %.2fms for %s",
                             operation_name, operation_duration, self.host)

            return result

        except (WLEDConnectionLifecycleError, WLEDConnectionError, WLEDNetworkError):
            # Re-raise connection-related errors
            raise
        except Exception as err:
            # Wrap unexpected errors with connection lifecycle context
            lifecycle_error = WLEDConnectionLifecycleError(
                f"Operation '{operation_name}' failed: {err}",
                host=self.host,
                lifecycle_stage=f"during_{operation_name}",
                connection_state="operation_failed",
                original_error=err
            )
            self.diagnostics_manager.record_error("WLEDConnectionLifecycleError", {
                "message": str(lifecycle_error),
                "operation_name": operation_name,
                "operation_duration_ms": (time.time() - operation_start) * 1000,
                "original_error": str(err)
            })
            raise lifecycle_error

    async def read_response_with_lifecycle_management(self, response: aiohttp.ClientResponse, endpoint: str, debug_mode: bool) -> tuple[str, str]:
        """Read response data with comprehensive connection lifecycle management."""
        response_text = None
        response_buffer = None
        read_attempts = 0
        max_read_attempts = 3

        while read_attempts < max_read_attempts:
            read_attempts += 1
            read_start = time.time()

            try:
                # Validate connection health before reading
                await self.validate_connection_health(response, f"read_attempt_{read_attempts}")

                # Read response data with timeout management
                try:
                    # Use asyncio.wait_for to add timeout to the read operation
                    raw_data = await asyncio.wait_for(
                        self._safe_read_response(response),
                        timeout=10.0  # 10 second read timeout
                    )

                    read_duration = (time.time() - read_start) * 1000
                    self.diagnostics_manager.add_timing_step(f"response_read_attempt_{read_attempts}")

                    # Validate connection health after reading
                    await self.validate_connection_health(response, f"after_read_attempt_{read_attempts}")

                    # Decode the data with proper error handling
                    if raw_data:
                        try:
                            response_text = raw_data.decode('utf-8')
                        except UnicodeDecodeError:
                            # Try with error handling for problematic encoding
                            response_text = raw_data.decode('utf-8', errors='replace')
                            _LOGGER.warning("Response encoding issues detected for %s, used error replacement", self.host)

                        response_buffer = response_text  # Keep buffer for error reporting

                        if debug_mode:
                            _LOGGER.debug("🔗 Successfully read %d bytes from %s in %.2fms (attempt %d)",
                                        len(raw_data), self.host, read_duration, read_attempts)

                        return response_text, response_buffer
                    else:
                        response_text = ""
                        response_buffer = ""
                        return response_text, response_buffer

                except asyncio.TimeoutError as timeout_err:
                    if read_attempts < max_read_attempts:
                        _LOGGER.warning("Read attempt %d timed out for %s, retrying...", read_attempts, self.host)
                        await asyncio.sleep(0.5 * read_attempts)  # Exponential backoff
                        continue
                    else:
                        raise WLEDConnectionLifecycleError(
                            f"Response read timed out after {max_read_attempts} attempts for {endpoint}",
                            host=self.host,
                            lifecycle_stage="response_read_timeout",
                            connection_state="timeout",
                            original_error=timeout_err
                        )

            except WLEDConnectionLifecycleError:
                # Re-raise lifecycle errors immediately
                raise
            except Exception as read_err:
                if read_attempts < max_read_attempts:
                    _LOGGER.warning("Read attempt %d failed for %s, retrying: %s", read_attempts, self.host, read_err)
                    await asyncio.sleep(0.5 * read_attempts)  # Exponential backoff
                    continue
                else:
                    # Handle connection closure during read
                    connection_error = WLEDConnectionLifecycleError(
                        f"Connection closed while reading response from WLED device at {self.host}: {read_err}",
                        host=self.host,
                        lifecycle_stage="response_read_failure",
                        connection_state="read_failed",
                        original_error=read_err
                    )
                    self.diagnostics_manager.record_error("WLEDConnectionLifecycleError", {
                        "message": str(connection_error),
                        "error_type": "connection_closed_during_read",
                        "endpoint": endpoint,
                        "attempts": read_attempts,
                        "original_error": str(read_err)
                    })
                    raise connection_error

        # This should never be reached, but just in case
        raise WLEDConnectionLifecycleError(
            f"Failed to read response after {max_read_attempts} attempts for {endpoint}",
            host=self.host,
            lifecycle_stage="response_read_exhausted",
            connection_state="exhausted"
        )

    async def _safe_read_response(self, response: aiohttp.ClientResponse) -> bytes:
        """Safely read response data with connection state monitoring."""
        try:
            # Use read() instead of text() to get raw bytes first
            return await response.read()
        except (aiohttp.ClientConnectionError, ConnectionResetError, ConnectionError) as conn_err:
            # Handle connection-specific errors
            raise WLEDConnectionLifecycleError(
                f"Connection error during response read: {conn_err}",
                host=self.host,
                lifecycle_stage="response_read_connection_error",
                connection_state="connection_error",
                original_error=conn_err
            )
        except Exception as err:
            # Handle other read errors
            raise WLEDConnectionLifecycleError(
                f"Unexpected error during response read: {err}",
                host=self.host,
                lifecycle_stage="response_read_unexpected_error",
                connection_state="read_error",
                original_error=err
            )

    async def validate_session_health(self, session: ClientSession, method: str, url: str) -> None:
        """Validate session health before making requests."""
        if not session:
            raise WLEDConnectionLifecycleError(
                "Session object is None",
                host=self.host,
                lifecycle_stage="session_validation",
                connection_state="no_session_object"
            )

        if session.closed:
            raise WLEDConnectionLifecycleError(
                f"Cannot execute {method} request: session is closed",
                host=self.host,
                lifecycle_stage="session_validation",
                connection_state="session_closed"
            )

        # Log session health for debugging
        session_info = {
            "session_closed": session.closed,
            "method": method,
            "url": url,
            "session_type": type(session).__name__
        }

        if hasattr(session, 'connector') and session.connector:
            session_info.update({
                "connector_limit": getattr(session.connector, 'limit', 'unknown'),
                "connector_limit_per_host": getattr(session.connector, 'limit_per_host', 'unknown'),
                "connector_closed": getattr(session.connector, '_closed', 'unknown')
            })

        self.diagnostics_manager.log_connection_state("session_health_validated", session_info)

    async def execute_request_with_lifecycle_management(self, session: ClientSession, method: str, url: str, operation_name: str, data: Optional[Dict[str, Any]] = None) -> aiohttp.ClientResponse:
        """Execute HTTP request with comprehensive connection lifecycle management."""
        request_start = time.time()

        try:
            # Pre-request connection validation
            self.diagnostics_manager.log_connection_state("request_execution_start", {
                "method": method,
                "url": url,
                "operation": operation_name,
                "has_data": data is not None
            })

            # Execute the request with connection monitoring
            if method.upper() == "GET":
                async with session.get(url, headers={"Cache-Control": "no-cache"}) as response:
                    request_duration = (time.time() - request_start) * 1000
                    self.diagnostics_manager.add_timing_step("get_request_complete")

                    # Validate connection state immediately after request
                    await self.validate_connection_health(response, "get_request_received")

                    return response

            elif method.upper() == "POST":
                async with session.post(url, json=data, headers={"Content-Type": "application/json"}) as response:
                    request_duration = (time.time() - request_start) * 1000
                    self.diagnostics_manager.add_timing_step("post_request_complete")

                    # Validate connection state immediately after request
                    await self.validate_connection_health(response, "post_request_received")

                    return response

        except (aiohttp.ClientConnectionError, ConnectionResetError, ConnectionError) as conn_err:
            # Handle connection-specific errors during request execution
            raise WLEDConnectionLifecycleError(
                f"Connection error during {method} request execution: {conn_err}",
                host=self.host,
                lifecycle_stage="request_execution",
                connection_state="connection_error",
                original_error=conn_err
            )
        except Exception as err:
            # Handle other request execution errors
            raise WLEDConnectionLifecycleError(
                f"Unexpected error during {method} request execution: {err}",
                host=self.host,
                lifecycle_stage="request_execution",
                connection_state="request_error",
                original_error=err
            )

    def get_connection_lifecycle_summary(self) -> Dict[str, Any]:
        """Get a summary of the connection lifecycle for debugging."""
        total_duration = (time.time() - self._lifecycle_start_time) * 1000

        summary = {
            "host": self.host,
            "total_lifecycle_duration_ms": total_duration,
            "connection_state_checks": len(self._connection_state_history),
            "state_history": self._connection_state_history,
            "lifecycle_stages": [state["stage"] for state in self._connection_state_history]
        }

        # Analyze connection state patterns
        if self._connection_state_history:
            final_state = self._connection_state_history[-1]
            summary["final_connection_state"] = final_state.get("connection_state", "unknown")
            summary["final_response_status"] = final_state.get("response_status", "unknown")

        return summary