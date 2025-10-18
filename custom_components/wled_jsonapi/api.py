"""Simplified API client for WLED JSONAPI devices."""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import ClientError, ClientSession

from .const import API_BASE, API_INFO, API_PRESETS, API_STATE, TIMEOUT
from .exceptions import (
    WLEDConnectionError,
    WLEDInvalidResponseError,
    WLEDTimeoutError,
    WLEDInvalidJSONError,
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
        """Make a simple request to the WLED API."""
        url = self._build_url(endpoint)

        _LOGGER.debug("Making %s request to %s", method, url)

        session = await self._ensure_session()

        try:
            if method.upper() == "GET":
                async with session.get(url) as response:
                    return await self._handle_response(response, url, endpoint)
            elif method.upper() == "POST":
                async with session.post(url, json=data) as response:
                    return await self._handle_response(response, url, endpoint)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except asyncio.TimeoutError as err:
            raise WLEDTimeoutError(
                f"Request to WLED device at {self.host} timed out after {TIMEOUT} seconds",
                host=self.host,
                original_error=err
            ) from err
        except aiohttp.ClientConnectorError as err:
            raise WLEDConnectionError(
                f"Connection error to WLED device at {self.host}: {err}",
                host=self.host,
                original_error=err
            ) from err
        except ClientError as err:
            raise WLEDConnectionError(
                f"Network error connecting to WLED device at {self.host}: {err}",
                host=self.host,
                original_error=err
            ) from err

    async def _handle_response(self, response: aiohttp.ClientResponse, url: str, endpoint: str) -> Dict[str, Any]:
        """Handle HTTP response."""
        if response.status >= 400:
            raise WLEDInvalidResponseError(
                f"WLED device at {self.host} returned HTTP {response.status} for {endpoint}",
                host=self.host,
                endpoint=endpoint,
            )

        try:
            response_text = await response.text()

            if not response_text or not response_text.strip():
                raise WLEDInvalidResponseError(
                    f"WLED device at {self.host} returned empty response for {endpoint}",
                    host=self.host,
                    endpoint=endpoint,
                )

            parsed_response = json.loads(response_text)

            if not isinstance(parsed_response, dict):
                raise WLEDInvalidResponseError(
                    f"WLED device at {self.host} returned invalid response format for {endpoint}",
                    host=self.host,
                    endpoint=endpoint,
                )

            _LOGGER.debug("Successfully parsed response from %s", url)
            return parsed_response

        except json.JSONDecodeError as err:
            raise WLEDInvalidJSONError(
                f"Failed to parse JSON response from WLED device at {self.host}: {err}",
                host=self.host,
                endpoint=endpoint,
                response_data=response_text[:500] if response_text else ""
            ) from err

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
            _LOGGER.debug("Successfully updated state on %s: %s", self.host, state)
            return response
        except Exception as err:
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

    async def activate_playlist(self, playlist: int) -> Dict[str, Any]:
        """Activate a playlist on the WLED device."""
        if not isinstance(playlist, int) or playlist < 0:
            error_msg = f"Invalid playlist ID provided: {playlist}. Must be a non-negative integer."
            _LOGGER.error(error_msg)
            raise ValueError(error_msg)

        try:
            state = {"pl": playlist}
            _LOGGER.debug("Activating playlist %d on WLED device at %s", playlist, self.host)
            response = await self.update_state(state)
            _LOGGER.debug("Successfully activated playlist %d on %s", playlist, self.host)
            return response
        except Exception as err:
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