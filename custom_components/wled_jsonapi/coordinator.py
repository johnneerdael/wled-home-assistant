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

    def _handle_error(self, error: Exception) -> None:
        """
        Handle error with simple approach appropriate for WLED devices.

        Args:
            error: The exception to handle
        """
        # Simple error handling for WLED HTTP client
        if isinstance(error, (WLEDTimeoutError, WLEDNetworkError)):
            self._available = False
            self._failed_polls += 1
            self._connection_state = "error"
            _LOGGER.warning("Network error updating WLED device at %s (attempt %d): %s",
                          self.client.host, self._failed_polls, error)
        elif isinstance(error, WLEDAuthenticationError):
            self._available = False
            self._connection_state = "error"
            _LOGGER.error("Authentication error with WLED device at %s: %s",
                        self.client.host, error)
        elif isinstance(error, (WLEDInvalidResponseError, WLEDConnectionError)):
            self._available = False
            self._failed_polls += 1
            self._connection_state = "error"
            _LOGGER.warning("Connection error updating WLED device at %s (attempt %d): %s",
                          self.client.host, self._failed_polls, error)
        else:
            # Default handling for unexpected errors
            self._available = False
            self._failed_polls += 1
            self._connection_state = "error"
            _LOGGER.error("Unexpected error updating WLED device at %s: %s",
                        self.client.host, error)

        # Store error information
        self._last_error = str(error)
        self._last_error_time = datetime.now()

        # Log if max failed polls reached
        if self._failed_polls >= MAX_FAILED_POLLS:
            _LOGGER.error(
                "WLED device at %s marked as unavailable after %d consecutive errors",
                self.client.host, self._failed_polls
            )

  
    
    
    
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
        """Update data via library with simplified error handling."""
        try:
            _LOGGER.debug("Fetching full state data from WLED device at %s", self.client.host)

            # Use full state to get effects, palettes, info, and state data in single API call
            full_state = await self.client.get_full_state()

            # Use complete state dict with effects, palettes, info, and state
            data = full_state

            # Check if presets need to be updated
            await self._async_update_presets_if_needed()

            # Reset failed polls counter on successful update
            self._failed_polls = 0
            self._set_connection_state("connected")
            _LOGGER.debug("Successfully updated full state data from WLED device at %s: %s",
                         self.client.host, list(data.keys()))

            return data

        except (WLEDTimeoutError, WLEDNetworkError, WLEDAuthenticationError,
                WLEDInvalidResponseError, WLEDConnectionError) as err:
            # Handle error with simplified approach
            self._handle_error(err)

            # Return cached data if available for network/connection errors
            if isinstance(err, (WLEDTimeoutError, WLEDNetworkError, WLEDInvalidResponseError, WLEDConnectionError)):
                if self.data is not None:
                    _LOGGER.debug("Returning last known data due to %s error", type(err).__name__)
                    return self.data

            # Generate appropriate error message for UpdateFailed
            error_type = "network" if isinstance(err, (WLEDTimeoutError, WLEDNetworkError)) else "connection"
            if isinstance(err, WLEDAuthenticationError):
                error_type = "authentication"
            elif isinstance(err, (WLEDInvalidResponseError, WLEDConnectionError)):
                error_type = "connection"

            error_msg = f"{error_type.capitalize()} error updating WLED device at {self.client.host}"
            raise UpdateFailed(error_msg) from err

        except Exception as err:
            # Handle unexpected errors
            self._handle_error(err)

            if self.data is not None:
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
        """Send a command to the WLED device with comprehensive logging."""
        if not isinstance(command, dict) or not command:
            error_msg = "Invalid command provided: command must be a non-empty dictionary"
            _LOGGER.error("WLED Command Validation Failed: %s | Device: %s", error_msg, self.client.host)
            raise WLEDCommandError(error_msg, command=command, host=self.client.host)

        # Log command details at INFO level for visibility
        _LOGGER.info(
            "WLED Command: Sending to %s | Command: %s | Device Available: %s",
            self.client.host, command, self.available
        )

        # Log additional debug details
        _LOGGER.debug(
            "WLED Command Details: Device=%s, Command=%s, Failed Polls=%d, Connection State=%s",
            self.client.host, command, self._failed_polls, self._connection_state
        )

        try:
            response = await self.client.update_state(command)

            # Log successful command execution
            _LOGGER.info(
                "WLED Command Success: %s | Command: %s | Response Received",
                self.client.host, command
            )

            # Log response details for debugging
            _LOGGER.debug(
                "WLED Command Response: Device=%s, Command=%s, Response Keys=%s",
                self.client.host, command, list(response.keys()) if isinstance(response, dict) else "N/A"
            )

            # Trigger an update after successful command
            _LOGGER.debug("WLED Command: Triggering data refresh after successful command to %s", self.client.host)
            await self.async_request_refresh()

            _LOGGER.info("WLED Command Completed: %s | Command: %s", self.client.host, command)
            return response

        except (WLEDTimeoutError, WLEDNetworkError, WLEDAuthenticationError,
                WLEDConnectionError, WLEDInvalidResponseError, WLEDCommandError) as err:
            # Handle error with comprehensive logging
            _LOGGER.error(
                "WLED Command Failed: %s | Command: %s | Error Type: %s | Error: %s",
                self.client.host, command, type(err).__name__, str(err)
            )
            self._handle_error(err)
            raise

        except Exception as err:
            # Handle unexpected errors with detailed logging
            _LOGGER.error(
                "WLED Command Unexpected Error: %s | Command: %s | Error Type: %s | Error: %s",
                self.client.host, command, type(err).__name__, str(err)
            )
            self._handle_error(err)
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
        """Turn on the WLED JSONAPI device with comprehensive logging."""
        command = {"on": True}

        if brightness is not None:
            command["bri"] = brightness
        if transition is not None:
            command["transition"] = transition
        if preset is not None:
            command["ps"] = preset

        # Log turn_on command details
        _LOGGER.info(
            "WLED Turn On: %s | Brightness: %s | Transition: %s | Preset: %s",
            self.client.host, brightness, transition, preset
        )

        return await self.async_send_command(command)

    async def async_turn_off(self, transition: int | None = None) -> Dict[str, Any]:
        """Turn off the WLED JSONAPI device with comprehensive logging."""
        command = {"on": False}

        if transition is not None:
            command["transition"] = transition

        # Log turn_off command details
        _LOGGER.info(
            "WLED Turn Off: %s | Transition: %s",
            self.client.host, transition
        )

        return await self.async_send_command(command)

    async def async_set_brightness(self, brightness: int, transition: int | None = None) -> Dict[str, Any]:
        """Set the brightness of the WLED JSONAPI device with comprehensive logging."""
        command = {"bri": brightness}

        if transition is not None:
            command["transition"] = transition

        # Log brightness command details
        _LOGGER.info(
            "WLED Set Brightness: %s | Brightness: %s | Transition: %s",
            self.client.host, brightness, transition
        )

        return await self.async_send_command(command)

    async def async_set_preset(self, preset: int) -> Dict[str, Any]:
        """Set a preset on the WLED device with comprehensive logging."""
        command = {"ps": preset}

        # Log preset command details
        _LOGGER.info(
            "WLED Set Preset: %s | Preset: %s",
            self.client.host, preset
        )

        return await self.async_send_command(command)

    async def async_set_effect(
        self,
        effect: int,
        speed: int | None = None,
        intensity: int | None = None,
        palette: int | None = None,
    ) -> Dict[str, Any]:
        """Set an effect on the WLED JSONAPI device with comprehensive logging."""
        command = {"seg": [{"fx": effect}]}

        if speed is not None:
            command["seg"][0]["sx"] = speed
        if intensity is not None:
            command["seg"][0]["ix"] = intensity
        if palette is not None:
            command["seg"][0]["pal"] = palette

        # Log effect command details
        _LOGGER.info(
            "WLED Set Effect: %s | Effect: %s | Speed: %s | Intensity: %s | Palette: %s",
            self.client.host, effect, speed, intensity, palette
        )

        return await self.async_send_command(command)

    async def _async_update_presets_if_needed(self) -> None:
        """Update presets data if it's time to refresh with simplified error handling."""
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
                # Simple preset error handling
                self._presets_failed_updates += 1
                _LOGGER.warning(
                    "Failed to update presets from %s due to %s error (attempt %d): %s",
                    self.client.host, type(err).__name__.lower().replace('wled', ''),
                    self._presets_failed_updates, err
                )

            except Exception as err:
                # Handle unexpected errors
                self._presets_failed_updates += 1
                _LOGGER.warning(
                    "Failed to update presets from %s due to unexpected error (attempt %d): %s",
                    self.client.host, self._presets_failed_updates, err
                )

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
        """Activate a playlist on the WLED device with simplified error handling."""
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
            # Simple error handling
            error_msg = f"Failed to activate playlist {playlist_id} on WLED device at {self.client.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id) from err

        except Exception as err:
            # Handle unexpected errors
            error_msg = f"Unexpected error activating playlist {playlist_id} on WLED device at {self.client.host}: {err}"
            _LOGGER.error(error_msg)
            raise WLEDPlaylistLoadError(error_msg, playlist_id=playlist_id) from err

    async def async_set_palette_for_all_segments(self, palette_id: int) -> Dict[str, Any]:
        """Set the palette on all segments of the WLED device with comprehensive logging."""
        if not isinstance(palette_id, int) or palette_id < 0:
            error_msg = f"Invalid palette ID provided: {palette_id}. Must be a non-negative integer."
            _LOGGER.error(error_msg)
            raise WLEDCommandError(error_msg, command={"pal": palette_id}, host=self.client.host)

        # Get current segments from state data
        state = self.data.get("state", {})
        segments = state.get("seg", [])

        if not segments:
            error_msg = "No segments found in WLED device state data"
            _LOGGER.error(error_msg)
            raise WLEDCommandError(error_msg, command={"pal": palette_id}, host=self.client.host)

        # Build segment commands
        segment_commands = []
        for seg in segments:
            seg_id = seg.get("id")
            if seg_id is not None:
                segment_commands.append({"id": seg_id, "pal": palette_id})
            else:
                _LOGGER.warning("Segment without ID found in WLED device data, skipping")

        if not segment_commands:
            error_msg = "No valid segments found to apply palette"
            _LOGGER.error(error_msg)
            raise WLEDCommandError(error_msg, command={"pal": palette_id}, host=self.client.host)

        # Create command
        command = {"seg": segment_commands}

        # Log palette command details
        _LOGGER.info(
            "WLED Set Palette: %s | Palette: %s | Segments: %s",
            self.client.host, palette_id, [cmd["id"] for cmd in segment_commands]
        )

        # Get current palette for logging
        current_palette = None
        if segments:
            main_seg = segments[0]  # Use first segment as reference
            current_palette = main_seg.get("pal")

        _LOGGER.debug(
            "WLED Palette Change: %s | Current: %s -> New: %s | Segments: %d",
            self.client.host, current_palette, palette_id, len(segment_commands)
        )

        try:
            response = await self.async_send_command(command)

            # Log successful palette change
            _LOGGER.info(
                "WLED Palette Success: %s | Palette: %s -> %s | Applied to %d segments",
                self.client.host, current_palette, palette_id, len(segment_commands)
            )

            return response

        except (WLEDTimeoutError, WLEDNetworkError, WLEDAuthenticationError,
                WLEDConnectionError, WLEDInvalidResponseError, WLEDCommandError) as err:
            # Handle error with comprehensive logging
            _LOGGER.error(
                "WLED Palette Failed: %s | Palette: %s | Error Type: %s | Error: %s",
                self.client.host, palette_id, type(err).__name__, str(err)
            )
            raise

        except Exception as err:
            # Handle unexpected errors with detailed logging
            _LOGGER.error(
                "WLED Palette Unexpected Error: %s | Palette: %s | Error Type: %s | Error: %s",
                self.client.host, palette_id, type(err).__name__, str(err)
            )
            raise WLEDCommandError(
                f"Unexpected error setting palette {palette_id} on WLED device at {self.client.host}: {err}",
                command=command, host=self.client.host, original_error=err
            ) from err