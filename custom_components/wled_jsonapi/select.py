"""Select platform for WLED JSONAPI integration."""
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_NAME, KEY_PRESET
from .coordinator import WLEDJSONAPIDataCoordinator
from .exceptions import (
    WLEDConnectionError,
    WLEDCommandError,
    WLEDTimeoutError,
    WLEDNetworkError,
    WLEDPresetError,
    WLEDPresetNotFoundError,
    WLEDPresetLoadError,
    WLEDPlaylistError,
    WLEDPlaylistNotFoundError,
    WLEDPlaylistLoadError,
)

_LOGGER = logging.getLogger(__name__)

PRESET_SELECT_DESCRIPTION = SelectEntityDescription(
    key="preset",
    translation_key="preset",
    icon="mdi:palette",
)

PLAYLIST_SELECT_DESCRIPTION = SelectEntityDescription(
    key="playlist",
    translation_key="playlist",
    icon="mdi:playlist-play",
)


class WLEDJSONAPIPresetSelect(CoordinatorEntity, SelectEntity):
    """Representation of a WLED JSONAPI preset selector."""

    _attr_has_entity_name = True
    entity_description = PRESET_SELECT_DESCRIPTION

    def __init__(self, coordinator: WLEDJSONAPIDataCoordinator, entry: ConfigEntry) -> None:
        """Initialize the WLED JSONAPI preset selector."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_preset_select"
        self._attr_current_option = None

    @property
    def available(self) -> bool:
        """Return True if the select is available."""
        return self.coordinator.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this select."""
        info = self.coordinator.data.get("info", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.unique_id)},
            name=info.get(KEY_NAME, f"WLED ({self._entry.data['host']})"),
            manufacturer="WLED",
            model=info.get("arch", "Unknown"),
            sw_version=info.get("ver", "Unknown"),
            configuration_url=f"http://{self._entry.data['host']}",
        )

    @property
    def options(self) -> List[str]:
        """Return the available preset options."""
        presets_data = self.coordinator.get_presets_data()
        if presets_data:
            preset_names = presets_data.get_all_preset_names()
            # Return preset names sorted by ID
            sorted_presets = sorted(preset_names.items(), key=lambda x: x[0])
            return [name for _, name in sorted_presets]
        return []

    @property
    def current_option(self) -> Optional[str]:
        """Return the current preset option."""
        state = self.coordinator.data.get("state", {})
        current_preset_id = state.get(KEY_PRESET)

        if current_preset_id is not None:
            presets_data = self.coordinator.get_presets_data()
            if presets_data:
                preset = presets_data.get_preset_by_id(current_preset_id)
                if preset:
                    return preset.name

        return None

    async def async_select_option(self, option: str) -> None:
        """Select a preset option with enhanced error handling."""
        if not self.coordinator.available:
            _LOGGER.warning(
                "Cannot select preset for WLED device at %s - device is not available. Last error: %s",
                self._entry.data['host'],
                self.coordinator.last_error or "Unknown"
            )
            return

        presets_data = self.coordinator.get_presets_data()
        if not presets_data:
            _LOGGER.error("No presets data available for WLED device at %s", self._entry.data['host'])
            return

        # Find the preset ID by name
        preset_names = presets_data.get_all_preset_names()
        preset_id = None
        for pid, name in preset_names.items():
            if name == option:
                preset_id = pid
                break

        if preset_id is None:
            _LOGGER.error(
                "Preset '%s' not found for WLED device at %s. Available presets: %s",
                option, self._entry.data['host'], list(preset_names.values())
            )
            return

        try:
            _LOGGER.debug("Selecting preset '%s' (ID: %s) for WLED device at %s", option, preset_id, self._entry.data['host'])
            await self.coordinator.async_set_preset(preset_id)
            _LOGGER.debug("Successfully selected preset '%s' for WLED device at %s", option, self._entry.data['host'])

        except WLEDTimeoutError as err:
            _LOGGER.error(
                "Timeout while selecting preset '%s' for WLED device at %s. The device may be busy or unresponsive. "
                "Please check the device and try again. Error: %s",
                option, self._entry.data['host'], err
            )

        except WLEDNetworkError as err:
            _LOGGER.error(
                "Network error while selecting preset '%s' for WLED device at %s. Please check that the device is "
                "connected to your network and the IP address is correct. Error: %s",
                option, self._entry.data['host'], err
            )

        except WLEDCommandError as err:
            _LOGGER.error(
                "Command error while selecting preset '%s' for WLED device at %s. The device may not support this "
                "command or there may be an issue with the request. Error: %s",
                option, self._entry.data['host'], err
            )

        except (WLEDPresetError, WLEDPresetLoadError) as err:
            _LOGGER.error(
                "Preset error while selecting preset '%s' for WLED device at %s: %s",
                option, self._entry.data['host'], err
            )

        except WLEDConnectionError as err:
            _LOGGER.error(
                "Connection error while selecting preset '%s' for WLED device at %s. Please check the device status "
                "and network connectivity. Error: %s",
                option, self._entry.data['host'], err
            )

        except Exception as err:
            _LOGGER.exception(
                "Unexpected error while selecting preset '%s' for WLED device at %s: %s",
                option, self._entry.data['host'], err
            )


class WLEDJSONAPIPlaylistSelect(CoordinatorEntity, SelectEntity):
    """Representation of a WLED JSONAPI playlist selector."""

    _attr_has_entity_name = True
    entity_description = PLAYLIST_SELECT_DESCRIPTION

    def __init__(self, coordinator: WLEDJSONAPIDataCoordinator, entry: ConfigEntry) -> None:
        """Initialize the WLED JSONAPI playlist selector."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_playlist_select"
        self._attr_current_option = None

    @property
    def available(self) -> bool:
        """Return True if the select is available."""
        return self.coordinator.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this select."""
        info = self.coordinator.data.get("info", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.unique_id)},
            name=info.get(KEY_NAME, f"WLED ({self._entry.data['host']})"),
            manufacturer="WLED",
            model=info.get("arch", "Unknown"),
            sw_version=info.get("ver", "Unknown"),
            configuration_url=f"http://{self._entry.data['host']}",
        )

    @property
    def options(self) -> List[str]:
        """Return the available playlist options."""
        presets_data = self.coordinator.get_presets_data()
        if presets_data:
            playlist_names = presets_data.get_all_playlist_names()
            # Return playlist names sorted by ID
            sorted_playlists = sorted(playlist_names.items(), key=lambda x: x[0])
            return [name for _, name in sorted_playlists]
        return []

    @property
    def current_option(self) -> Optional[str]:
        """Return the current playlist option."""
        state = self.coordinator.data.get("state", {})
        current_playlist_id = state.get("pl")

        if current_playlist_id is not None and current_playlist_id >= 0:
            presets_data = self.coordinator.get_presets_data()
            if presets_data:
                playlist = presets_data.get_playlist_by_id(current_playlist_id)
                if playlist:
                    return playlist.name

        return None

    async def async_select_option(self, option: str) -> None:
        """Select a playlist option with enhanced error handling."""
        if not self.coordinator.available:
            _LOGGER.warning(
                "Cannot select playlist for WLED device at %s - device is not available. Last error: %s",
                self._entry.data['host'],
                self.coordinator.last_error or "Unknown"
            )
            return

        presets_data = self.coordinator.get_presets_data()
        if not presets_data:
            _LOGGER.error("No playlists data available for WLED device at %s", self._entry.data['host'])
            return

        # Find the playlist ID by name
        playlist_names = presets_data.get_all_playlist_names()
        playlist_id = None
        for pid, name in playlist_names.items():
            if name == option:
                playlist_id = pid
                break

        if playlist_id is None:
            _LOGGER.error(
                "Playlist '%s' not found for WLED device at %s. Available playlists: %s",
                option, self._entry.data['host'], list(playlist_names.values())
            )
            return

        try:
            _LOGGER.debug("Selecting playlist '%s' (ID: %s) for WLED device at %s", option, playlist_id, self._entry.data['host'])
            await self.coordinator.async_activate_playlist(playlist_id)
            _LOGGER.debug("Successfully selected playlist '%s' for WLED device at %s", option, self._entry.data['host'])

        except WLEDTimeoutError as err:
            _LOGGER.error(
                "Timeout while selecting playlist '%s' for WLED device at %s. The device may be busy or unresponsive. "
                "Please check the device and try again. Error: %s",
                option, self._entry.data['host'], err
            )

        except WLEDNetworkError as err:
            _LOGGER.error(
                "Network error while selecting playlist '%s' for WLED device at %s. Please check that the device is "
                "connected to your network and the IP address is correct. Error: %s",
                option, self._entry.data['host'], err
            )

        except WLEDCommandError as err:
            _LOGGER.error(
                "Command error while selecting playlist '%s' for WLED device at %s. The device may not support this "
                "command or there may be an issue with the request. Error: %s",
                option, self._entry.data['host'], err
            )

        except (WLEDPlaylistError, WLEDPlaylistLoadError) as err:
            _LOGGER.error(
                "Playlist error while selecting playlist '%s' for WLED device at %s: %s",
                option, self._entry.data['host'], err
            )

        except WLEDConnectionError as err:
            _LOGGER.error(
                "Connection error while selecting playlist '%s' for WLED device at %s. Please check the device status "
                "and network connectivity. Error: %s",
                option, self._entry.data['host'], err
            )

        except Exception as err:
            _LOGGER.exception(
                "Unexpected error while selecting playlist '%s' for WLED device at %s: %s",
                option, self._entry.data['host'], err
            )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WLED JSONAPI selects from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = []

    # Add preset selector if presets are available
    presets_data = coordinator.get_presets_data()
    if presets_data and presets_data.presets:
        entities.append(WLEDJSONAPIPresetSelect(coordinator, entry))
        _LOGGER.debug("Added preset selector entity")
    else:
        _LOGGER.debug("No presets available, skipping preset selector")

    # Add playlist selector if playlists are available
    if presets_data and presets_data.playlists:
        entities.append(WLEDJSONAPIPlaylistSelect(coordinator, entry))
        _LOGGER.debug("Added playlist selector entity")
    else:
        _LOGGER.debug("No playlists available, skipping playlist selector")

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.debug("No select entities added - no presets or playlists available")