"""Simplified API client for WLED JSONAPI devices."""
import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import ClientError, ClientSession

from .const import API_BASE, API_INFO, API_PRESETS, API_STATE, TIMEOUT
from .exceptions import (
    WLEDConnectionError,
    WLEDInvalidResponseError,
    WLEDTimeoutError,
    WLEDInvalidJSONError,
    WLEDCommandError,
)
from .models import (
    WLEDPresetsData,
    WLEDEssentialState,
    WLEDEssentialPresetsData,
)

_LOGGER = logging.getLogger(__name__)


class WLEDJSONAPIClient:
    """Simplified API client for WLED JSONAPI devices."""

    def __init__(self, host: str, session: Optional[ClientSession] = None) -> None:
        """Initialize the API client."""
        self.host = host
        self.base_url = f"http://{host}{API_BASE}"
        self._session = session
        self._close_session = session is None

    async def _ensure_session(self) -> ClientSession:
        """Ensure that an aiohttp session exists, creating one if necessary."""
        if self._session is None or self._session.closed:
            self._session = ClientSession(
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                headers={"User-Agent": "Home-Assistant-WLED-JSONAPI/1.0"}
            )
        return self._session

    def _build_url(self, endpoint: str) -> str:
        """Build the full URL for the given endpoint."""
        if endpoint == API_PRESETS:
            return f"http://{self.host}{endpoint}"
        else:
            if endpoint.startswith("/json/"):
                endpoint = endpoint[5:]  # Remove "/json" prefix
            return f"{self.base_url}{endpoint}"

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the WLED API with comprehensive logging."""
        url = self._build_url(endpoint)
        request_start_time = time.time()

        # Log request details at INFO level for visibility
        _LOGGER.info(
            "WLED API Request: %s %s | Host: %s | Payload: %s",
            method, url, self.host, data
        )

        # Log additional debug details
        _LOGGER.debug(
            "WLED Request Details: Method=%s, URL=%s, Endpoint=%s, Payload=%s, Timeout=%s",
            method, url, endpoint, data, TIMEOUT
        )

        session = await self._ensure_session()

        # Log session details for debugging
        _LOGGER.debug(
            "WLED Session Details: Headers=%s, Timeout=%s, Session Closed=%s",
            session.headers, session.timeout, session.closed
        )

        try:
            if method.upper() == "GET":
                _LOGGER.debug("Executing GET request to %s", url)
                async with session.get(url) as response:
                    return await self._handle_response(response, url, endpoint, None, request_start_time)
            elif method.upper() == "POST":
                _LOGGER.debug("Executing POST request to %s with data: %s", url, data)
                async with session.post(url, json=data) as response:
                    return await self._handle_response(response, url, endpoint, data, request_start_time)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except asyncio.TimeoutError as err:
            request_duration = time.time() - request_start_time
            _LOGGER.error(
                "WLED Request Failed: %s %s | Duration: %.2fs | Error: Timeout after %s seconds | Payload: %s",
                method, url, request_duration, TIMEOUT, data
            )
            raise WLEDTimeoutError(
                f"Request to WLED device at {self.host} timed out after {TIMEOUT} seconds",
                host=self.host,
                original_error=err
            ) from err
        except aiohttp.ClientConnectorError as err:
            request_duration = time.time() - request_start_time
            _LOGGER.error(
                "WLED Request Failed: %s %s | Duration: %.2fs | Error: Connection failed - %s | Payload: %s",
                method, url, request_duration, err, data
            )
            raise WLEDConnectionError(
                f"Connection error to WLED device at {self.host}: {err}",
                host=self.host,
                original_error=err
            ) from err
        except ClientError as err:
            request_duration = time.time() - request_start_time
            _LOGGER.error(
                "WLED Request Failed: %s %s | Duration: %.2fs | Error: Network error - %s | Payload: %s",
                method, url, request_duration, err, data
            )
            raise WLEDConnectionError(
                f"Network error connecting to WLED device at {self.host}: {err}",
                host=self.host,
                original_error=err
            ) from err
        except Exception as err:
            request_duration = time.time() - request_start_time
            _LOGGER.error(
                "WLED Request Failed: %s %s | Duration: %.2fs | Error: Unexpected error - %s | Payload: %s",
                method, url, request_duration, err, data
            )
            raise

    async def _handle_response(
        self,
        response: aiohttp.ClientResponse,
        url: str,
        endpoint: str,
        command_data: Optional[Dict[str, Any]] = None,
        request_start_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """Handle HTTP response with comprehensive validation and logging."""
        request_duration = time.time() - request_start_time if request_start_time else None

        # Log response details at INFO level for visibility
        _LOGGER.info(
            "WLED API Response: %s | Status: %s | Duration: %.2fs",
            url, response.status, request_duration or 0
        )

        # Log additional debug details
        _LOGGER.debug(
            "WLED Response Details: URL=%s, Status=%s, Headers=%s, Duration=%.2fs",
            url, response.status, dict(response.headers), request_duration or 0
        )

        if response.status >= 400:
            error_response_text = ""
            try:
                error_response_text = await response.text()
                _LOGGER.error(
                    "WLED HTTP Error: %s | Status: %s | Duration: %.2fs | Error Response: %s | Command: %s",
                    url, response.status, request_duration or 0, error_response_text[:500], command_data
                )
            except Exception:
                _LOGGER.error(
                    "WLED HTTP Error: %s | Status: %s | Duration: %.2fs | Command: %s",
                    url, response.status, request_duration or 0, command_data
                )

            raise WLEDInvalidResponseError(
                f"WLED device at {self.host} returned HTTP {response.status} for {endpoint}",
                host=self.host,
                endpoint=endpoint,
            )

        try:
            response_text = await response.text()

            # Log response body for debugging
            _LOGGER.debug(
                "WLED Response Body: %s | Status: %s | Length: %d characters",
                url, response.status, len(response_text)
            )

            if not response_text or not response_text.strip():
                _LOGGER.error(
                    "WLED Empty Response: %s | Status: %s | Duration: %.2fs | Command: %s",
                    url, response.status, request_duration or 0, command_data
                )
                raise WLEDInvalidResponseError(
                    f"WLED device at {self.host} returned empty response for {endpoint}",
                    host=self.host,
                    endpoint=endpoint,
                )

            parsed_response = json.loads(response_text)

            if not isinstance(parsed_response, dict):
                _LOGGER.error(
                    "WLED Invalid Response Format: %s | Expected dict, got %s | Response: %s | Command: %s",
                    url, type(parsed_response).__name__, response_text[:200], command_data
                )
                raise WLEDInvalidResponseError(
                    f"WLED device at {self.host} returned invalid response format for {endpoint}",
                    host=self.host,
                    endpoint=endpoint,
                )

            # Log successful response parsing
            _LOGGER.debug(
                "WLED Response Parsed: %s | Status: %s | Duration: %.2fs | Keys: %s | Command: %s",
                url, response.status, request_duration or 0, list(parsed_response.keys()), command_data
            )

            # Validate response content and check for WLED-specific errors
            self._validate_response_content(parsed_response, endpoint, command_data)

            # For state commands, verify the command was actually applied
            if endpoint == API_STATE and command_data:
                self._validate_state_response(parsed_response, command_data)

            # Log successful response handling
            _LOGGER.info(
                "WLED Request Success: %s | Status: %s | Duration: %.2fs | Command Applied: %s",
                url, response.status, request_duration or 0, command_data is not None
            )

            return parsed_response

        except json.JSONDecodeError as err:
            _LOGGER.error(
                "WLED JSON Decode Error: %s | Duration: %.2fs | Error: %s | Response: %s | Command: %s",
                url, request_duration or 0, err, response_text[:500] if response_text else "", command_data
            )
            raise WLEDInvalidJSONError(
                f"Failed to parse JSON response from WLED device at {self.host}: {err}",
                host=self.host,
                endpoint=endpoint,
                response_data=response_text[:500] if response_text else ""
            ) from err

    def _validate_response_content(
        self,
        response_data: Dict[str, Any],
        endpoint: str,
        command_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Validate response content for WLED-specific errors and structure."""

        # Check for WLED error responses (HTTP 200 but contains error)
        if "error" in response_data:
            error_info = response_data["error"]
            if isinstance(error_info, dict):
                error_msg = error_info.get("message", "Unknown WLED error")
                error_code = error_info.get("code", "unknown")
            else:
                error_msg = str(error_info)
                error_code = "unknown"

            _LOGGER.error(
                "WLED device at %s returned error response: %s (code: %s)",
                self.host, error_msg, error_code
            )

            raise WLEDCommandError(
                f"WLED device error: {error_msg}",
                command=command_data,
                host=self.host
            )

        # Check for success field that some WLED endpoints return
        if "success" in response_data and not response_data["success"]:
            reason = response_data.get("error", "Unknown reason")
            _LOGGER.error(
                "WLED device at %s reported command failure: %s",
                self.host, reason
            )
            raise WLEDCommandError(
                f"WLED command failed: {reason}",
                command=command_data,
                host=self.host
            )

        # Endpoint-specific validation
        if endpoint == API_STATE:
            self._validate_state_response_structure(response_data)
        elif endpoint == API_INFO:
            self._validate_info_response_structure(response_data)
        elif endpoint == API_PRESETS:
            self._validate_presets_response_structure(response_data)

    def _validate_state_response_structure(self, response_data: Dict[str, Any]) -> None:
        """Validate that state response has expected structure."""
        # State responses should at least have on/off status
        if "on" not in response_data:
            _LOGGER.warning(
                "WLED device at %s state response missing 'on' field",
                self.host
            )

        # Check for segment data if present in command
        if "seg" in response_data:
            segments = response_data["seg"]
            if not isinstance(segments, list):
                _LOGGER.warning(
                    "WLED device at %s returned invalid segment data format",
                    self.host
                )

    def _validate_info_response_structure(self, response_data: Dict[str, Any]) -> None:
        """Validate that info response has expected structure."""
        required_fields = ["name", "ver"]
        missing_fields = [field for field in required_fields if field not in response_data]

        if missing_fields:
            _LOGGER.warning(
                "WLED device at %s info response missing required fields: %s",
                self.host, ", ".join(missing_fields)
            )

    def _validate_presets_response_structure(self, response_data: Dict[str, Any]) -> None:
        """Validate that presets response has expected structure."""
        if not isinstance(response_data, dict):
            _LOGGER.warning(
                "WLED device at %s presets response is not a dictionary",
                self.host
            )
            return

        # Check for expected preset structure
        if "p" not in response_data and "presets" not in response_data:
            _LOGGER.warning(
                "WLED device at %s presets response missing preset data",
                self.host
            )

    def _validate_state_response(self, response_data: Dict[str, Any], command_data: Dict[str, Any]) -> None:
        """Verify that state command was applied successfully."""

        # Extract the actual state changes from the response
        response_state = response_data.get("state", response_data)

        # Track if we found any mismatches
        mismatches = []

        # Validate each command field
        for field, expected_value in command_data.items():
            if field == "seg":
                # Handle segment validation separately
                self._validate_segment_command(response_state, expected_value)
                continue

            # Check if the field exists in response and matches expected value
            if field in response_state:
                actual_value = response_state[field]
                if actual_value != expected_value:
                    mismatches.append((field, expected_value, actual_value))
                    _LOGGER.warning(
                        "WLED device at %s state mismatch for %s: expected %s, got %s",
                        self.host, field, expected_value, actual_value
                    )
            else:
                _LOGGER.warning(
                    "WLED device at %s response missing field %s after command",
                    self.host, field
                )

        # If we have critical mismatches, raise an error
        critical_fields = ["on", "bri"]
        critical_mismatches = [
            (field, expected, actual) for field, expected, actual in mismatches
            if field in critical_fields
        ]

        if critical_mismatches:
            error_details = ", ".join([
                f"{field}: expected {expected}, got {actual}"
                for field, expected, actual in critical_mismatches
            ])
            raise WLEDCommandError(
                f"WLED device did not apply critical state changes: {error_details}",
                command=command_data,
                host=self.host
            )

        # Log successful validation for non-critical mismatches
        if mismatches and not critical_mismatches:
            _LOGGER.info(
                "WLED device at %s command applied with minor state differences: %s",
                self.host, ", ".join([f"{field}" for field, _, _ in mismatches])
            )
        elif not mismatches:
            _LOGGER.debug(
                "WLED device at %s successfully applied all state changes: %s",
                self.host, command_data
            )

    def _validate_segment_command(self, response_state: Dict[str, Any], segment_command: Dict[str, Any]) -> None:
        """Validate segment-specific commands."""
        response_segments = response_state.get("seg", [])

        if not isinstance(response_segments, list) or not response_segments:
            _LOGGER.warning(
                "WLED device at %s response missing or invalid segment data",
                self.host
            )
            return

        # For simplicity, validate against the first segment
        # (most commands target segment 0)
        response_segment = response_segments[0]

        mismatches = []
        for field, expected_value in segment_command.items():
            if field in response_segment and response_segment[field] != expected_value:
                mismatches.append((field, expected_value, response_segment[field]))
                _LOGGER.warning(
                    "WLED device at %s segment state mismatch for %s: expected %s, got %s",
                    self.host, field, expected_value, response_segment[field]
                )

        if mismatches:
            _LOGGER.info(
                "WLED device at %s segment command applied with differences: %s",
                self.host, ", ".join([f"{field}" for field, _, _ in mismatches])
            )

    async def get_state(self) -> Dict[str, Any]:
        """Get the current state of the WLED device."""
        try:
            response = await self._request("GET", API_STATE)
            _LOGGER.debug("Successfully retrieved state from %s", self.host)
            return response
        except Exception as err:
            error_msg = f"Error getting state from WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, original_error=err) from err

    async def get_info(self) -> Dict[str, Any]:
        """Get information about the WLED device."""
        try:
            response = await self._request("GET", API_INFO)

            if "name" not in response:
                _LOGGER.warning("WLED device at %s info response missing 'name' field", self.host)

            _LOGGER.debug("Successfully retrieved info from %s", self.host)
            return response
        except Exception as err:
            error_msg = f"Error getting info from WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, original_error=err) from err

    async def get_full_state(self) -> Dict[str, Any]:
        """Get the full state including info, effects, and palettes."""
        try:
            response = await self._request("GET", "")

            required_sections = ["info", "state"]
            for section in required_sections:
                if section not in response:
                    _LOGGER.warning("WLED device at %s full state response missing required section: %s", self.host, section)

            _LOGGER.debug("Successfully retrieved full state from %s", self.host)
            return response
        except Exception as err:
            error_msg = f"Error getting full state from WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, original_error=err) from err

    async def update_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Update the state of the WLED device."""
        if not isinstance(state, dict) or not state:
            error_msg = f"Invalid state data provided to WLED device at {self.host}: {state}"
            _LOGGER.error(error_msg)
            raise ValueError(error_msg)

        try:
            response = await self._request("POST", API_STATE, data=state)
            _LOGGER.info("Successfully updated state on %s: %s", self.host, state)
            return response
        except WLEDCommandError as err:
            # Command validation failed - device didn't apply the changes
            error_msg = f"State command validation failed on WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise
        except Exception as err:
            # Network or other errors
            error_msg = f"Error updating state on WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, original_error=err) from err

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
        """Get presets and playlists from the WLED device."""
        try:
            response = await self._request("GET", API_PRESETS)
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
        except Exception as err:
            error_msg = f"Error getting presets from WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, original_error=err) from err

    async def get_essential_presets(self) -> WLEDEssentialPresetsData:
        """Get essential presets and playlists data from the WLED device."""
        try:
            response = await self._request("GET", API_PRESETS)
            essential_presets_data = WLEDEssentialPresetsData.from_presets_response(response)

            if not essential_presets_data.presets and not essential_presets_data.playlists:
                _LOGGER.warning("No essential presets or playlists found on WLED device at %s", self.host)
            else:
                _LOGGER.debug(
                    "Successfully retrieved %d essential presets and %d essential playlists from %s",
                    len(essential_presets_data.presets),
                    len(essential_presets_data.playlists),
                    self.host
                )

            return essential_presets_data
        except Exception as err:
            error_msg = f"Error getting essential presets from WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, original_error=err) from err

    async def activate_playlist(self, playlist: int) -> Dict[str, Any]:
        """Activate a playlist on the WLED device."""
        if not isinstance(playlist, int) or playlist < 0:
            error_msg = f"Invalid playlist ID provided: {playlist}. Must be a non-negative integer."
            _LOGGER.error(error_msg)
            raise ValueError(error_msg)

        try:
            state = {"pl": playlist}
            _LOGGER.info("Activating playlist %d on WLED device at %s", playlist, self.host)
            response = await self.update_state(state)
            _LOGGER.info("Successfully activated playlist %d on %s", playlist, self.host)
            return response
        except WLEDCommandError as err:
            # Command validation failed - device didn't apply the changes
            error_msg = f"Playlist activation validation failed on WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise
        except Exception as err:
            # Network or other errors
            error_msg = f"Error activating playlist {playlist} on WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, original_error=err) from err

    async def test_connection(self) -> bool:
        """Test connection to the WLED device."""
        try:
            _LOGGER.debug("Testing connection to WLED device at %s", self.host)
            await self.get_info()
            _LOGGER.debug("Connection test successful for WLED device at %s", self.host)
            return True
        except Exception as err:
            _LOGGER.warning("Connection test to WLED device at %s failed: %s", self.host, err)
            return False

    async def get_essential_state(self) -> WLEDEssentialState:
        """Get only essential state parameters from the WLED device."""
        try:
            _LOGGER.debug("Getting essential state from WLED device at %s", self.host)
            response = await self._request("GET", API_STATE)

            # Extract only essential parameters
            essential_response = {}
            if 'on' in response:
                essential_response['on'] = response['on']
            if 'bri' in response:
                essential_response['bri'] = response['bri']
            if 'ps' in response:
                essential_response['ps'] = response['ps']
            if 'pl' in response:
                essential_response['pl'] = response['pl']

            essential_state = WLEDEssentialState.from_state_response(essential_response)

            _LOGGER.debug("Successfully extracted essential state from %s: on=%s, brightness=%s, preset=%s, playlist=%s",
                         self.host, essential_state.on, essential_state.brightness,
                         essential_state.preset_id, essential_state.playlist_id)

            return essential_state
        except Exception as err:
            error_msg = f"Error getting essential state from WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, original_error=err) from err

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._close_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "WLEDJSONAPIClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()