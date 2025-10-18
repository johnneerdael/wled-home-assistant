"""Data coordinator for WLED JSONAPI integration."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WLEDJSONAPIClient
from .const import DOMAIN, UPDATE_INTERVAL, PRESETS_UPDATE_INTERVAL, MAX_FAILED_POLLS
from .exceptions import (
    WLEDConnectionError,
    WLEDDeviceUnavailableError,
    WLEDInvalidResponseError,
    WLEDTimeoutError,
    WLEDNetworkError,
    WLEDAuthenticationError,
    WLEDCommandError,
    WLEDPresetError,
    WLEDPresetNotFoundError,
    WLEDPresetLoadError,
    WLEDPlaylistError,
    WLEDPlaylistNotFoundError,
    WLEDPlaylistLoadError,
)
from .models import WLEDPresetsData, WLEDPreset, WLEDPlaylist

_LOGGER = logging.getLogger(__name__)


class WLEDJSONAPIDataCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching data from the WLED JSONAPI device."""

    def __init__(self, hass: HomeAssistant, client: WLEDJSONAPIClient) -> None:
        """Initialize."""
        self.client = client
        self._failed_polls = 0
        self._available = True
        self._last_successful_update: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._last_error_time: Optional[datetime] = None
        self._connection_state = "unknown"  # Can be: connected, disconnected, error, unknown

        # Presets caching
        self._presets_data: Optional[WLEDPresetsData] = None
        self._presets_last_updated: Optional[datetime] = None
        self._presets_failed_updates = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        _LOGGER.info("Initialized WLED coordinator for device at %s", client.host)

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self._available

    @property
    def connection_state(self) -> str:
        """Return the current connection state."""
        return self._connection_state

    @property
    def last_error(self) -> Optional[str]:
        """Return the last error message."""
        return self._last_error

    @property
    def last_error_time(self) -> Optional[datetime]:
        """Return the time of the last error."""
        return self._last_error_time

    @property
    def last_successful_update(self) -> Optional[datetime]:
        """Return the time of the last successful update."""
        return self._last_successful_update

    @property
    def failed_polls(self) -> int:
        """Return the number of consecutive failed polls."""
        return self._failed_polls

    def _set_connection_state(self, state: str, error: Optional[str] = None) -> None:
        """Set the connection state and update related attributes."""
        old_state = self._connection_state
        self._connection_state = state

        if state == "connected":
            self._available = True
            self._last_successful_update = datetime.now()
            self._last_error = None
            self._last_error_time = None
            if old_state != "connected":
                _LOGGER.info("WLED device at %s is now connected", self.client.host)
        elif state in ("disconnected", "error"):
            self._available = False
            if error:
                self._last_error = error
                self._last_error_time = datetime.now()
            if old_state != state:
                _LOGGER.warning(
                    "WLED device at %s connection state changed from %s to %s: %s",
                    self.client.host, old_state, state, error or "No error details"
                )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via library with enhanced error handling and state tracking."""
        try:
            _LOGGER.debug("Fetching data from WLED device at %s", self.client.host)
            data = await self.client.get_full_state()

            # Check if presets need to be updated
            await self._async_update_presets_if_needed()

            # Reset failed polls counter on successful update
            self._failed_polls = 0
            self._set_connection_state("connected")
            _LOGGER.debug("Successfully updated data from WLED device at %s", self.client.host)

            return data

        except WLEDTimeoutError as err:
            self._failed_polls += 1
            error_msg = f"WLED device at {self.client.host} request timed out"
            _LOGGER.warning("%s (attempt %d): %s", error_msg, self._failed_polls, err)
            self._set_connection_state("error", error_msg)

            if self._failed_polls >= MAX_FAILED_POLLS:
                _LOGGER.error(
                    "WLED device at %s marked as unavailable after %d consecutive timeout errors",
                    self.client.host, self._failed_polls
                )

            if self.data is not None:
                _LOGGER.debug("Returning last known data due to timeout error")
                return self.data

            raise UpdateFailed(error_msg) from err

        except WLEDNetworkError as err:
            self._failed_polls += 1
            error_msg = f"Network error connecting to WLED device at {self.client.host}"
            _LOGGER.warning("%s (attempt %d): %s", error_msg, self._failed_polls, err)
            self._set_connection_state("disconnected", error_msg)

            if self._failed_polls >= MAX_FAILED_POLLS:
                _LOGGER.error(
                    "WLED device at %s marked as unavailable after %d consecutive network errors",
                    self.client.host, self._failed_polls
                )

            if self.data is not None:
                _LOGGER.debug("Returning last known data due to network error")
                return self.data

            raise UpdateFailed(error_msg) from err

        except WLEDAuthenticationError as err:
            error_msg = f"WLED device at {self.client.host} requires authentication"
            _LOGGER.error(error_msg)
            self._set_connection_state("error", error_msg)
            raise UpdateFailed(error_msg) from err

        except WLEDInvalidResponseError as err:
            self._failed_polls += 1
            error_msg = f"Invalid response from WLED device at {self.client.host}"
            _LOGGER.warning("%s (attempt %d): %s", error_msg, self._failed_polls, err)
            self._set_connection_state("error", error_msg)

            if self._failed_polls >= MAX_FAILED_POLLS:
                _LOGGER.error(
                    "WLED device at %s marked as unavailable after %d consecutive invalid response errors",
                    self.client.host, self._failed_polls
                )

            if self.data is not None:
                _LOGGER.debug("Returning last known data due to invalid response error")
                return self.data

            raise UpdateFailed(error_msg) from err

        except WLEDConnectionError as err:
            self._failed_polls += 1
            error_msg = f"Connection error with WLED device at {self.client.host}"
            _LOGGER.warning("%s (attempt %d): %s", error_msg, self._failed_polls, err)
            self._set_connection_state("error", error_msg)

            if self._failed_polls >= MAX_FAILED_POLLS:
                _LOGGER.error(
                    "WLED device at %s marked as unavailable after %d consecutive connection errors",
                    self.client.host, self._failed_polls
                )

            if self.data is not None:
                _LOGGER.debug("Returning last known data due to connection error")
                return self.data

            raise UpdateFailed(error_msg) from err

        except Exception as err:
            self._failed_polls += 1
            error_msg = f"Unexpected error updating WLED device at {self.client.host}"
            _LOGGER.exception("%s (attempt %d): %s", error_msg, self._failed_polls, err)
            self._set_connection_state("error", error_msg)

            if self._failed_polls >= MAX_FAILED_POLLS:
                _LOGGER.error(
                    "WLED device at %s marked as unavailable after %d consecutive unexpected errors",
                    self.client.host, self._failed_polls
                )

            if self.data is not None:
                _LOGGER.debug("Returning last known data due to unexpected error")
                return self.data

            raise UpdateFailed(f"{error_msg}: {err}") from err

    async def async_send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to the WLED device with enhanced error handling."""
        if not isinstance(command, dict) or not command:
            error_msg = "Invalid command provided: command must be a non-empty dictionary"
            _LOGGER.error(error_msg)
            raise WLEDCommandError(error_msg, command=command, host=self.client.host)

        try:
            _LOGGER.debug("Sending command to WLED device at %s: %s", self.client.host, command)
            response = await self.client.update_state(command)

            # Trigger an update after successful command
            await self.async_request_refresh()

            _LOGGER.debug("Successfully sent command to WLED device at %s", self.client.host)
            return response

        except WLEDTimeoutError as err:
            error_msg = f"Command to WLED device at {self.client.host} timed out"
            _LOGGER.error(error_msg)
            self._set_connection_state("error", error_msg)
            raise

        except WLEDNetworkError as err:
            error_msg = f"Network error sending command to WLED device at {self.client.host}"
            _LOGGER.error(error_msg)
            self._set_connection_state("disconnected", error_msg)
            raise

        except WLEDAuthenticationError as err:
            error_msg = f"WLED device at {self.client.host} requires authentication for command execution"
            _LOGGER.error(error_msg)
            self._set_connection_state("error", error_msg)
            raise

        except (WLEDConnectionError, WLEDInvalidResponseError, WLEDCommandError) as err:
            error_msg = f"Failed to send command to WLED device at {self.client.host}: {err}"
            _LOGGER.error(error_msg)
            self._set_connection_state("error", error_msg)
            raise

        except Exception as err:
            error_msg = f"Unexpected error sending command to WLED device at {self.client.host}: {err}"
            _LOGGER.exception(error_msg)
            self._set_connection_state("error", error_msg)
            raise WLEDCommandError(error_msg, command=command, host=self.client.host, original_error=err) from err

    async def async_turn_on(
        self,
        brightness: int | None = None,
        transition: int | None = None,
        preset: int | None = None,
    ) -> Dict[str, Any]:
        """Turn on the WLED JSONAPI device."""
        command = {"on": True}
        
        if brightness is not None:
            command["bri"] = brightness
        if transition is not None:
            command["transition"] = transition
        if preset is not None:
            command["ps"] = preset

        return await self.async_send_command(command)

    async def async_turn_off(self, transition: int | None = None) -> Dict[str, Any]:
        """Turn off the WLED JSONAPI device."""
        command = {"on": False}
        
        if transition is not None:
            command["transition"] = transition

        return await self.async_send_command(command)

    async def async_set_brightness(self, brightness: int, transition: int | None = None) -> Dict[str, Any]:
        """Set the brightness of the WLED JSONAPI device."""
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
        """Set an effect on the WLED JSONAPI device."""
        command = {"seg": [{"fx": effect}]}
        
        if speed is not None:
            command["seg"][0]["sx"] = speed
        if intensity is not None:
            command["seg"][0]["ix"] = intensity
        if palette is not None:
            command["seg"][0]["pal"] = palette

        return await self.async_send_command(command)

    async def _async_update_presets_if_needed(self) -> None:
        """Update presets data if it's time to refresh with enhanced error handling."""
        now = datetime.now()

        # Check if we need to update presets (either never updated or more than PRESETS_UPDATE_INTERVAL ago)
        if (self._presets_last_updated is None or
            now - self._presets_last_updated >= PRESETS_UPDATE_INTERVAL):

            try:
                _LOGGER.debug("Updating presets data from WLED device at %s", self.client.host)
                presets_data = await self.client.get_presets()
                self._presets_data = presets_data
                self._presets_last_updated = now
                self._presets_failed_updates = 0

                _LOGGER.debug(
                    "Successfully updated presets data from %s: %d presets, %d playlists",
                    self.client.host, len(presets_data.presets), len(presets_data.playlists)
                )

            except WLEDTimeoutError as err:
                self._presets_failed_updates += 1
                _LOGGER.warning(
                    "Failed to update presets data from %s due to timeout (attempt %d): %s",
                    self.client.host, self._presets_failed_updates, err
                )
                # Don't fail the entire update if presets can't be fetched

            except WLEDNetworkError as err:
                self._presets_failed_updates += 1
                _LOGGER.warning(
                    "Failed to update presets data from %s due to network error (attempt %d): %s",
                    self.client.host, self._presets_failed_updates, err
                )
                # Don't fail the entire update if presets can't be fetched

            except WLEDPresetError as err:
                self._presets_failed_updates += 1
                _LOGGER.warning(
                    "Failed to update presets data from %s due to preset error (attempt %d): %s",
                    self.client.host, self._presets_failed_updates, err
                )
                # Don't fail the entire update if presets can't be fetched

            except (WLEDConnectionError, WLEDInvalidResponseError) as err:
                self._presets_failed_updates += 1
                _LOGGER.warning(
                    "Failed to update presets data from %s due to connection/response error (attempt %d): %s",
                    self.client.host, self._presets_failed_updates, err
                )
                # Don't fail the entire update if presets can't be fetched

            except Exception as err:
                self._presets_failed_updates += 1
                _LOGGER.error(
                    "Unexpected error updating presets data from %s (attempt %d): %s",
                    self.client.host, self._presets_failed_updates, err
                )
                # Don't fail the entire update if presets can't be fetched

    def get_presets_data(self) -> Optional[WLEDPresetsData]:
        """Get cached presets data."""
        return self._presets_data

    def get_preset_by_id(self, preset_id: int) -> Optional[WLEDPreset]:
        """Get a preset by ID from cached data."""
        if self._presets_data:
            return self._presets_data.get_preset_by_id(preset_id)
        return None

    def get_playlist_by_id(self, playlist_id: int) -> Optional[WLEDPlaylist]:
        """Get a playlist by ID from cached data."""
        if self._presets_data:
            return self._presets_data.get_playlist_by_id(playlist_id)
        return None

    def get_all_preset_names(self) -> Dict[int, str]:
        """Get all preset names from cached data."""
        if self._presets_data:
            return self._presets_data.get_all_preset_names()
        return {}

    def get_all_playlist_names(self) -> Dict[int, str]:
        """Get all playlist names from cached data."""
        if self._presets_data:
            return self._presets_data.get_all_playlist_names()
        return {}

    async def async_activate_playlist(self, playlist_id: int) -> Dict[str, Any]:
        """Activate a playlist on the WLED device with enhanced error handling."""
        if not isinstance(playlist_id, int) or playlist_id < 0:
            error_msg = f"Invalid playlist ID provided: {playlist_id}. Must be a non-negative integer."
            _LOGGER.error(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id)

        # Check if the playlist exists in cached data
        playlist = self.get_playlist_by_id(playlist_id)
        if playlist is None:
            _LOGGER.warning(
                "Playlist ID %d not found in cached presets data from WLED device at %s. "
                "Proceeding with activation anyway as the playlist may exist on the device.",
                playlist_id, self.client.host
            )

        try:
            command = {"pl": playlist_id}
            _LOGGER.debug("Activating playlist %d on WLED device at %s", playlist_id, self.client.host)
            response = await self.async_send_command(command)

            # Trigger an update after successful playlist activation
            await self.async_request_refresh()

            _LOGGER.info("Successfully activated playlist %d (%s) on WLED device at %s",
                        playlist_id, playlist.name if playlist else "Unknown", self.client.host)
            return response

        except WLEDTimeoutError as err:
            error_msg = f"Playlist activation timed out for playlist {playlist_id} on WLED device at {self.client.host}"
            _LOGGER.error(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id) from err

        except WLEDNetworkError as err:
            error_msg = f"Network error during playlist activation for playlist {playlist_id} on WLED device at {self.client.host}"
            _LOGGER.error(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id) from err

        except WLEDAuthenticationError as err:
            error_msg = f"Authentication required for playlist activation on WLED device at {self.client.host}"
            _LOGGER.error(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id) from err

        except (WLEDConnectionError, WLEDInvalidResponseError, WLEDCommandError) as err:
            error_msg = f"Failed to activate playlist {playlist_id} on WLED device at {self.client.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id) from err

        except Exception as err:
            error_msg = f"Unexpected error activating playlist {playlist_id} on WLED device at {self.client.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id) from err