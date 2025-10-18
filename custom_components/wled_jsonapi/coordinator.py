"""Data coordinator for WLED JSONAPI integration."""
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Type

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WLEDJSONAPIClient
from .const import DOMAIN, UPDATE_INTERVAL, PRESETS_UPDATE_INTERVAL, MAX_FAILED_POLLS
from .exceptions import (
    WLEDConnectionError,
    WLEDInvalidResponseError,
    WLEDTimeoutError,
    WLEDNetworkError,
    WLEDAuthenticationError,
    WLEDCommandError,
    WLEDPresetError,
    WLEDPresetLoadError,
    WLEDPlaylistError,
    WLEDPlaylistLoadError,
)
from .models import (
    WLEDPresetsData,
    WLEDPreset,
    WLEDPlaylist,
    WLEDEssentialState,
    WLEDEssentialPresetsData,
)

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

    def _get_error_config(self, exception_type: Type[Exception]) -> Dict[str, Any]:
        """
        Get error configuration for exception type.

        Returns a dictionary with standardized error handling configuration:
        - connection_state: The state to set ("error", "disconnected", "connected")
        - error_type: Type description for logging ("timeout", "network", etc.)
        - increment_failed_polls: Whether to increment the failed polls counter
        - can_return_cached: Whether cached data can be returned for this error

        Args:
            exception_type: The exception class to get configuration for

        Returns:
            Dictionary containing error handling configuration
        """
        error_configs = {
            WLEDTimeoutError: {
                "connection_state": "error",
                "error_type": "timeout",
                "increment_failed_polls": True,
                "can_return_cached": True,
            },
            WLEDNetworkError: {
                "connection_state": "disconnected",
                "error_type": "network",
                "increment_failed_polls": True,
                "can_return_cached": True,
            },
            WLEDAuthenticationError: {
                "connection_state": "error",
                "error_type": "authentication",
                "increment_failed_polls": False,
                "can_return_cached": False,
            },
            WLEDInvalidResponseError: {
                "connection_state": "error",
                "error_type": "invalid_response",
                "increment_failed_polls": True,
                "can_return_cached": True,
            },
            WLEDConnectionError: {
                "connection_state": "error",
                "error_type": "connection",
                "increment_failed_polls": True,
                "can_return_cached": True,
            },
        }
        return error_configs.get(exception_type, {
            "connection_state": "error",
            "error_type": "unexpected",
            "increment_failed_polls": True,
            "can_return_cached": True,
        })

    def _handle_update_error(
        self,
        exception: Exception,
        operation: str
    ) -> None:
        """
        Handle error during data update with standardized logic.

        This method centralizes the common error handling pattern used in update operations:
        1. Increment failed polls counter (if configured)
        2. Generate standardized error message
        3. Log the error with appropriate level
        4. Set connection state
        5. Log error if max failed polls threshold is reached

        Args:
            exception: The exception that occurred
            operation: Description of the operation being performed (e.g., "updating", "fetching")
        """
        exception_type = type(exception)
        config = self._get_error_config(exception_type)

        # Increment failed polls counter if configured
        if config["increment_failed_polls"]:
            self._failed_polls += 1

        # Generate error message
        error_msg = f"{config['error_type'].title()} error {operation} WLED device at {self.client.host}"

        # Log the error
        if config["increment_failed_polls"]:
            _LOGGER.warning("%s (attempt %d): %s", error_msg, self._failed_polls, exception)
        else:
            _LOGGER.error("%s: %s", error_msg, exception)

        # Set connection state
        self._set_connection_state(config["connection_state"], error_msg)

        # Log if max failed polls reached
        if (config["increment_failed_polls"] and
            self._failed_polls >= MAX_FAILED_POLLS):
            _LOGGER.error(
                "WLED device at %s marked as unavailable after %d consecutive %s errors",
                self.client.host, self._failed_polls, config["error_type"]
            )

    def _handle_command_error(
        self,
        exception: Exception,
        operation: str,
        command: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle error during command execution with standardized logic.

        This method centralizes error handling for command operations:
        1. Generate standardized error message
        2. Determine appropriate connection state
        3. Log the error
        4. Set connection state

        Args:
            exception: The exception that occurred
            operation: Description of the command operation (e.g., "sending command")
            command: Optional command data that was being sent (for context)
        """
        exception_type = type(exception)

        # Generate error message
        error_msg = f"{operation} on WLED device at {self.client.host}"

        # Determine connection state
        if exception_type == WLEDNetworkError:
            connection_state = "disconnected"
        else:
            connection_state = "error"

        # Log and set state
        _LOGGER.error(f"{error_msg}: {exception}")
        self._set_connection_state(connection_state, error_msg)

    def _handle_preset_error(
        self,
        exception: Exception,
        operation: str
    ) -> None:
        """
        Handle error during preset update with standardized logic.

        This method centralizes error handling for preset operations:
        1. Increment preset failed updates counter
        2. Log warning with attempt count and exception details

        Note: Preset update errors don't fail the entire main data update,
        so errors are logged as warnings rather than errors.

        Args:
            exception: The exception that occurred during preset operation
            operation: Description of the preset operation (e.g., "update presets data")
        """
        self._presets_failed_updates += 1
        _LOGGER.warning(
            "Failed to %s from %s due to %s error (attempt %d): %s",
            operation, self.client.host, type(exception).__name__.lower().replace('wled', ''),
            self._presets_failed_updates, exception
        )

    def _should_return_cached_data(self, exception: Exception) -> bool:
        """
        Determine if cached data should be returned for this exception.

        Uses the error configuration to decide whether cached data can be returned
        for the given exception type. This allows the system to gracefully degrade
        by returning stale data when the device is temporarily unavailable.

        Args:
            exception: The exception that occurred

        Returns:
            True if cached data should be returned, False otherwise
        """
        exception_type = type(exception)
        config = self._get_error_config(exception_type)
        return config["can_return_cached"] and self.data is not None

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
            _LOGGER.debug("Fetching essential data from WLED device at %s", self.client.host)

            # Use streamlined essential data extraction for better performance
            essential_state = await self.client.get_essential_state()

            # Convert essential state to dictionary for Home Assistant
            data = essential_state.to_state_dict()

            # Include raw essential data for advanced features
            if essential_state.raw_state:
                data["_raw_state"] = essential_state.raw_state

            # Check if presets need to be updated
            await self._async_update_presets_if_needed()

            # Reset failed polls counter on successful update
            self._failed_polls = 0
            self._set_connection_state("connected")
            _LOGGER.debug("Successfully updated essential data from WLED device at %s: %s",
                         self.client.host, list(data.keys()))

            return data

        except (WLEDTimeoutError, WLEDNetworkError, WLEDAuthenticationError,
                WLEDInvalidResponseError, WLEDConnectionError) as err:
            # Handle all known WLED exceptions with standardized logic
            self._handle_update_error(err, "updating")

            # Return cached data if available and configured
            if self._should_return_cached_data(err):
                _LOGGER.debug("Returning last known data due to %s error", type(err).__name__)
                return self.data

            # Generate appropriate error message for UpdateFailed
            config = self._get_error_config(type(err))
            error_msg = f"{config['error_type'].title()} error updating WLED device at {self.client.host}"
            raise UpdateFailed(error_msg) from err

        except Exception as err:
            # Handle unexpected errors
            self._handle_update_error(err, "updating")

            if self._should_return_cached_data(err):
                _LOGGER.debug("Returning last known data due to unexpected error")
                return self.data

            error_msg = f"Unexpected error updating WLED device at {self.client.host}: {err}"
            raise UpdateFailed(error_msg) from err

    async def async_get_essential_state(self) -> WLEDEssentialState:
        """
        Get essential state data from the WLED device.

        This method provides direct access to the streamlined essential state
        without going through the coordinator's data caching mechanism.

        Returns:
            WLEDEssentialState object containing only essential parameters

        Raises:
            UpdateFailed: If the device is unavailable or returns invalid data
        """
        try:
            return await self.client.get_essential_state()
        except Exception as err:
            error_msg = f"Failed to get essential state from WLED device at {self.client.host}: {err}"
            raise UpdateFailed(error_msg) from err

    async def async_get_essential_presets(self) -> WLEDEssentialPresetsData:
        """
        Get essential presets data from the WLED device.

        This method provides direct access to the streamlined essential presets
        without going through the coordinator's caching mechanism.

        Returns:
            WLEDEssentialPresetsData object containing only essential preset information

        Raises:
            UpdateFailed: If the device is unavailable or returns invalid data
        """
        try:
            return await self.client.get_essential_presets()
        except Exception as err:
            error_msg = f"Failed to get essential presets from WLED device at {self.client.host}: {err}"
            raise UpdateFailed(error_msg) from err

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

        except (WLEDTimeoutError, WLEDNetworkError, WLEDAuthenticationError,
                WLEDConnectionError, WLEDInvalidResponseError, WLEDCommandError) as err:
            # Handle all known WLED exceptions with standardized logic
            self._handle_command_error(err, "sending command", command)
            raise

        except Exception as err:
            # Handle unexpected errors
            self._handle_command_error(err, "sending command", command)
            raise WLEDCommandError(
                f"Unexpected error sending command to WLED device at {self.client.host}: {err}",
                command=command, host=self.client.host, original_error=err
            ) from err

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
                _LOGGER.debug("Updating essential presets data from WLED device at %s", self.client.host)

                # Use streamlined essential presets extraction for better performance
                essential_presets_data = await self.client.get_essential_presets()

                # Convert essential presets to the full format for backward compatibility
                self._presets_data = WLEDPresetsData.from_dict({
                    str(preset.id): {"n": preset.name} for preset in essential_presets_data.presets.values()
                })

                # Add playlists
                for playlist in essential_presets_data.playlists.values():
                    self._presets_data.playlists[playlist.id] = WLEDPlaylist.from_playlist_response(
                        str(playlist.id), {"n": playlist.name}
                    )

                self._presets_last_updated = now
                self._presets_failed_updates = 0

                _LOGGER.debug(
                    "Successfully updated essential presets data from %s: %d presets, %d playlists",
                    self.client.host, len(essential_presets_data.presets), len(essential_presets_data.playlists)
                )

            except (WLEDTimeoutError, WLEDNetworkError, WLEDPresetError,
                    WLEDConnectionError, WLEDInvalidResponseError) as err:
                # Handle all known preset-related errors with standardized logic
                self._handle_preset_error(err, "update essential presets data")

            except Exception as err:
                # Handle unexpected errors
                self._handle_preset_error(err, "update essential presets data")

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

        except (WLEDTimeoutError, WLEDNetworkError, WLEDAuthenticationError,
                WLEDConnectionError, WLEDInvalidResponseError, WLEDCommandError) as err:
            # Handle all known WLED exceptions with standardized logic
            error_msg = f"Failed to activate playlist {playlist_id} on WLED device at {self.client.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id) from err

        except Exception as err:
            # Handle unexpected errors
            error_msg = f"Unexpected error activating playlist {playlist_id} on WLED device at {self.client.host}: {err}"
            _LOGGER.exception(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id) from err