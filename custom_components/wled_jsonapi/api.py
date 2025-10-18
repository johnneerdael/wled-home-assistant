"""Simplified API client for WLED JSONAPI devices."""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import ClientError, ClientError, ClientSession, ServerTimeoutError

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
)
from .models import WLEDPresetsData

_LOGGER = logging.getLogger(__name__)


class WLEDJSONAPIClient:
    """Simplified API client for WLED JSONAPI devices."""

    def __init__(self, host: str, session: Optional[ClientSession] = None) -> None:
        """Initialize the API client."""
        self.host = host
        self.base_url = f"http://{host}{API_BASE}"
        self._session = session
        self._close_session = False

        if session is None:
            self._session = ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT))
            self._close_session = True

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a simple request to the WLED API with enhanced error handling."""
        # Handle presets endpoint separately since it's not under /json
        if endpoint == API_PRESETS:
            url = f"http://{self.host}{endpoint}"
        else:
            url = f"{self.base_url}{endpoint}"

        _LOGGER.debug("Making %s request to %s (host: %s, endpoint: %s)", method, url, self.host, endpoint)

        try:
            # Determine which HTTP method to use
            if method.upper() == "GET":
                async with self._session.get(url) as response:
                    return await self._handle_response(response, url, endpoint)
            elif method.upper() == "POST":
                _LOGGER.debug("Sending POST data to %s: %s", url, data)
                async with self._session.post(url, json=data) as response:
                    return await self._handle_response(response, url, endpoint)
            else:
                error_msg = f"Unsupported HTTP method: {method}"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)

        except ServerTimeoutError as err:
            error_msg = f"Request to WLED device at {self.host} timed out after {TIMEOUT} seconds"
            _LOGGER.error(error_msg)
            raise WLEDTimeoutError(error_msg, host=self.host, operation=f"{method} {endpoint}", original_error=err) from err

        except aiohttp.ClientConnectorError as err:
            error_msg = f"Could not connect to WLED device at {self.host}. Please check that the device is powered on and connected to your network."
            _LOGGER.error(error_msg)
            raise WLEDNetworkError(error_msg, host=self.host, operation=f"{method} {endpoint}", original_error=err) from err

        except aiohttp.ClientResponseError as err:
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

        except (ClientError, asyncio.TimeoutError) as err:
            error_msg = f"Network error connecting to WLED device at {self.host}: {err}. Please check your network connection and the device's IP address."
            _LOGGER.error(error_msg)
            raise WLEDNetworkError(error_msg, host=self.host, operation=f"{method} {endpoint}", original_error=err) from err

        except json.JSONDecodeError as err:
            error_msg = f"WLED device at {self.host} returned invalid JSON response"
            _LOGGER.error(error_msg)
            raise WLEDInvalidJSONError(error_msg, host=self.host, endpoint=endpoint) from err

        except Exception as err:
            error_msg = f"Unexpected error connecting to WLED device at {self.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDConnectionError(error_msg, host=self.host, operation=f"{method} {endpoint}", original_error=err) from err

    async def _handle_response(self, response: aiohttp.ClientResponse, url: str, endpoint: str) -> Dict[str, Any]:
        """Handle HTTP response with enhanced error handling."""
        response_text = await response.text()

        try:
            response.raise_for_status()
        except aiohttp.ClientResponseError as err:
            # Log the response text for debugging
            if response_text:
                _LOGGER.debug("Error response body: %s", response_text[:500])  # Limit to first 500 chars
            raise

        # Handle empty responses
        if not response_text.strip():
            error_msg = f"WLED device at {self.host} returned empty response for {endpoint}"
            _LOGGER.error(error_msg)
            raise WLEDInvalidResponseError(error_msg, host=self.host, endpoint=endpoint, response_data="<empty>")

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as err:
            error_msg = f"Failed to parse JSON response from WLED device at {self.host}: {err}"
            _LOGGER.error(error_msg)
            _LOGGER.debug("Invalid JSON response: %s", response_text[:500])  # Limit to first 500 chars
            raise WLEDInvalidJSONError(error_msg, host=self.host, endpoint=endpoint, response_data=response_text[:500]) from err

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