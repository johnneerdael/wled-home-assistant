"""Data coordinator for WLED integration."""
import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WLEDAPIClient
from .const import DOMAIN, UPDATE_INTERVAL
from .exceptions import WLEDConnectionError, WLEDDeviceUnavailableError, WLEDInvalidResponseError

_LOGGER = logging.getLogger(__name__)


class WLEDDataCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching data from the WLED device."""

    def __init__(self, hass: HomeAssistant, client: WLEDAPIClient) -> None:
        """Initialize."""
        self.client = client
        self._failed_polls = 0
        self._available = True

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self._available

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via library."""
        try:
            _LOGGER.debug("Fetching data from WLED device")
            data = await self.client.get_full_state()
            
            # Reset failed polls counter on successful update
            self._failed_polls = 0
            if not self._available:
                _LOGGER.info("WLED device is now available")
                self._available = True
            
            return data

        except (WLEDConnectionError, WLEDInvalidResponseError) as err:
            self._failed_polls += 1
            
            if self._failed_polls >= 3 and self._available:
                _LOGGER.warning("WLED device marked as unavailable after %d failed polls", self._failed_polls)
                self._available = False
            
            _LOGGER.debug("Failed to update WLED data (attempt %d): %s", self._failed_polls, err)
            
            # Return last known data if available, otherwise raise UpdateFailed
            if self.data is not None:
                return self.data
            
            raise UpdateFailed(f"Error communicating with WLED device: {err}") from err

        except Exception as err:
            _LOGGER.error("Unexpected error updating WLED data: %s", err)
            self._failed_polls += 1
            
            if self._failed_polls >= 3 and self._available:
                self._available = False
            
            if self.data is not None:
                return self.data
            
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def async_send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to the WLED device."""
        try:
            _LOGGER.debug("Sending command to WLED device: %s", command)
            response = await self.client.update_state(command)
            
            # Trigger an update after successful command
            await self.async_request_refresh()
            
            return response

        except (WLEDConnectionError, WLEDInvalidResponseError) as err:
            _LOGGER.error("Failed to send command to WLED device: %s", err)
            raise

        except Exception as err:
            _LOGGER.error("Unexpected error sending command to WLED device: %s", err)
            raise

    async def async_turn_on(
        self,
        brightness: int | None = None,
        transition: int | None = None,
        preset: int | None = None,
    ) -> Dict[str, Any]:
        """Turn on the WLED device."""
        command = {"on": True}
        
        if brightness is not None:
            command["bri"] = brightness
        if transition is not None:
            command["transition"] = transition
        if preset is not None:
            command["ps"] = preset

        return await self.async_send_command(command)

    async def async_turn_off(self, transition: int | None = None) -> Dict[str, Any]:
        """Turn off the WLED device."""
        command = {"on": False}
        
        if transition is not None:
            command["transition"] = transition

        return await self.async_send_command(command)

    async def async_set_brightness(self, brightness: int, transition: int | None = None) -> Dict[str, Any]:
        """Set the brightness of the WLED device."""
        command = {"bri": brightness}
        
        if transition is not None:
            command["transition"] = transition

        return await self.async_send_command(command)

    async def async_set_preset(self, preset: int) -> Dict[str, Any]:
        """Set a preset on the WLED device."""
        command = {"ps": preset}
        return await self.async_send_command(command)

    async def async_set_effect(
        self,
        effect: int,
        speed: int | None = None,
        intensity: int | None = None,
        palette: int | None = None,
    ) -> Dict[str, Any]:
        """Set an effect on the WLED device."""
        command = {"seg": [{"fx": effect}]}
        
        if speed is not None:
            command["seg"][0]["sx"] = speed
        if intensity is not None:
            command["seg"][0]["ix"] = intensity
        if palette is not None:
            command["seg"][0]["pal"] = palette

        return await self.async_send_command(command)