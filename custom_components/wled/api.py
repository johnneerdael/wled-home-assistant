"""API client for WLED devices."""
import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    API_BASE,
    API_INFO,
    API_STATE,
    CONNECTION_TIMEOUT,
    INITIAL_RETRY_DELAY,
    MAX_RETRIES,
    MAX_RETRY_DELAY,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF_MULTIPLIER,
)
from .exceptions import (
    WLEDCommandError,
    WLEDConnectionError,
    WLEDDeviceUnavailableError,
    WLEDInvalidResponseError,
)

_LOGGER = logging.getLogger(__name__)


class WLEDAPIClient:
    """API client for WLED devices."""

    def __init__(self, host: str, session: Optional[ClientSession] = None) -> None:
        """Initialize the API client."""
        self.host = host
        self.base_url = f"http://{host}{API_BASE}"
        self._session = session
        self._close_session = False

        if session is None:
            self._session = ClientSession()
            self._close_session = True

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        retries: int = MAX_RETRIES,
    ) -> Dict[str, Any]:
        """Make a request to the WLED API with retry logic."""
        url = f"{self.base_url}{endpoint}"
        retry_delay = INITIAL_RETRY_DELAY

        for attempt in range(retries + 1):
            try:
                _LOGGER.debug(
                    "Making %s request to %s (attempt %d/%d)",
                    method,
                    url,
                    attempt + 1,
                    retries + 1,
                )

                async with asyncio.timeout(REQUEST_TIMEOUT):
                    if method.upper() == "GET":
                        async with self._session.get(
                            url, timeout=CONNECTION_TIMEOUT
                        ) as response:
                            response.raise_for_status()
                            return await response.json()
                    elif method.upper() == "POST":
                        async with self._session.post(
                            url, json=data, timeout=CONNECTION_TIMEOUT
                        ) as response:
                            response.raise_for_status()
                            return await response.json()

            except asyncio.TimeoutError as err:
                _LOGGER.warning(
                    "Timeout connecting to WLED device at %s (attempt %d/%d)",
                    self.host,
                    attempt + 1,
                    retries + 1,
                )
                if attempt == retries:
                    raise WLEDConnectionError(f"Timeout connecting to {self.host}") from err

            except ClientError as err:
                _LOGGER.warning(
                    "Error connecting to WLED device at %s: %s (attempt %d/%d)",
                    self.host,
                    err,
                    attempt + 1,
                    retries + 1,
                )
                if attempt == retries:
                    raise WLEDConnectionError(f"Connection error to {self.host}: {err}") from err

            except Exception as err:
                _LOGGER.error(
                    "Unexpected error connecting to WLED device at %s: %s (attempt %d/%d)",
                    self.host,
                    err,
                    attempt + 1,
                    retries + 1,
                )
                if attempt == retries:
                    raise WLEDConnectionError(f"Unexpected error to {self.host}: {err}") from err

            # Wait before retry with exponential backoff
            if attempt < retries:
                await asyncio.sleep(retry_delay)
                retry_delay = min(
                    retry_delay * RETRY_BACKOFF_MULTIPLIER, MAX_RETRY_DELAY
                )

        raise WLEDConnectionError(f"Failed to connect to {self.host} after {retries} retries")

    async def get_state(self) -> Dict[str, Any]:
        """Get the current state of the WLED device."""
        try:
            response = await self._request("GET", API_STATE)
            if not isinstance(response, dict):
                raise WLEDInvalidResponseError("Invalid response format")
            return response
        except Exception as err:
            _LOGGER.error("Failed to get state from %s: %s", self.host, err)
            raise

    async def get_info(self) -> Dict[str, Any]:
        """Get information about the WLED device."""
        try:
            response = await self._request("GET", API_INFO)
            if not isinstance(response, dict):
                raise WLEDInvalidResponseError("Invalid response format")
            return response
        except Exception as err:
            _LOGGER.error("Failed to get info from %s: %s", self.host, err)
            raise

    async def get_full_state(self) -> Dict[str, Any]:
        """Get the full state including info, effects, and palettes."""
        try:
            response = await self._request("GET", "")
            if not isinstance(response, dict):
                raise WLEDInvalidResponseError("Invalid response format")
            return response
        except Exception as err:
            _LOGGER.error("Failed to get full state from %s: %s", self.host, err)
            raise

    async def update_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Update the state of the WLED device."""
        try:
            response = await self._request("POST", API_STATE, data=state)
            if not isinstance(response, dict):
                raise WLEDInvalidResponseError("Invalid response format")
            return response
        except Exception as err:
            _LOGGER.error("Failed to update state on %s: %s", self.host, err)
            raise WLEDCommandError(f"Failed to update state: {err}") from err

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

    async def test_connection(self) -> bool:
        """Test connection to the WLED device."""
        try:
            await self.get_info()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._close_session and self._session:
            await self._session.close()

    async def __aenter__(self) -> "WLEDAPIClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()