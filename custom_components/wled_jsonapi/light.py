"""Light platform for WLED JSONAPI integration."""
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_BRIGHTNESS, KEY_EFFECT, KEY_NAME, KEY_ON, KEY_PALETTE, KEY_PRESET
from .coordinator import WLEDJSONAPIDataCoordinator
from .exceptions import (
    WLEDConnectionError,
    WLEDCommandError,
    WLEDTimeoutError,
    WLEDNetworkError,
    WLEDPresetError,
    WLEDPresetNotFoundError,
    WLEDPresetLoadError,
)

_LOGGER = logging.getLogger(__name__)


class WLEDJSONAPILight(CoordinatorEntity, LightEntity):
    """Representation of a WLED JSONAPI light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: WLEDJSONAPIDataCoordinator, entry: ConfigEntry) -> None:
        """Initialize the WLED JSONAPI light."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_light"

    @property
    def available(self) -> bool:
        """Return True if the light is available."""
        return self.coordinator.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this light."""
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
    def is_on(self) -> bool:
        """Return True if the light is on."""
        state = self.coordinator.data.get("state", {})
        return state.get(KEY_ON, False)

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of the light."""
        state = self.coordinator.data.get("state", {})
        return state.get(KEY_BRIGHTNESS)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return ColorMode.BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return {ColorMode.BRIGHTNESS}

    @property
    def effect(self) -> Optional[str]:
        """Return the current effect."""
        state = self.coordinator.data.get("state", {})
        segments = state.get("seg", [])
        if segments and len(segments) > 0:
            effect_id = segments[0].get(KEY_EFFECT)
            if effect_id is not None:
                effects = self.coordinator.data.get("effects", [])
                if 0 <= effect_id < len(effects):
                    return effects[effect_id]
        return None

    @property
    def effect_list(self) -> Optional[List[str]]:
        """Return the list of supported effects."""
        return self.coordinator.data.get("effects", [])

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return the supported features."""
        return LightEntityFeature.EFFECT

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light with enhanced error handling."""
        if not self.coordinator.available:
            _LOGGER.warning(
                "Cannot turn on WLED light at %s - device is not available. Last error: %s",
                self._entry.data['host'],
                self.coordinator.last_error or "Unknown"
            )
            return

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        transition = kwargs.get(ATTR_TRANSITION)
        effect = kwargs.get(ATTR_EFFECT)
        preset = None

        # Handle effect selection
        if effect is not None:
            effects = self.coordinator.data.get("effects", [])
            if effect in effects:
                preset = effects.index(effect)
                _LOGGER.debug("Effect '%s' found, using preset ID %s", effect, preset)
            else:
                _LOGGER.warning(
                    "Effect '%s' not found in available effects from WLED device at %s. "
                    "Available effects: %s",
                    effect, self._entry.data['host'], effects
                )

        try:
            _LOGGER.debug(
                "Turning on WLED light at %s with brightness=%s, transition=%s, preset=%s",
                self._entry.data['host'], brightness, transition, preset
            )
            await self.coordinator.async_turn_on(
                brightness=brightness,
                transition=transition,
                preset=preset,
            )
            _LOGGER.debug("Successfully turned on WLED light at %s", self._entry.data['host'])

        except WLEDTimeoutError as err:
            _LOGGER.error(
                "Timeout while turning on WLED light at %s. The device may be busy or unresponsive. "
                "Please check the device and try again. Error: %s",
                self._entry.data['host'], err
            )

        except WLEDNetworkError as err:
            _LOGGER.error(
                "Network error while turning on WLED light at %s. Please check that the device is "
                "connected to your network and the IP address is correct. Error: %s",
                self._entry.data['host'], err
            )

        except WLEDCommandError as err:
            _LOGGER.error(
                "Command error while turning on WLED light at %s. The device may not support this "
                "command or there may be an issue with the request. Error: %s",
                self._entry.data['host'], err
            )

        except WLEDConnectionError as err:
            _LOGGER.error(
                "Connection error while turning on WLED light at %s. Please check the device status "
                "and network connectivity. Error: %s",
                self._entry.data['host'], err
            )

        except Exception as err:
            _LOGGER.exception(
                "Unexpected error while turning on WLED light at %s: %s",
                self._entry.data['host'], err
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light with enhanced error handling."""
        if not self.coordinator.available:
            _LOGGER.warning(
                "Cannot turn off WLED light at %s - device is not available. Last error: %s",
                self._entry.data['host'],
                self.coordinator.last_error or "Unknown"
            )
            return

        transition = kwargs.get(ATTR_TRANSITION)

        try:
            _LOGGER.debug(
                "Turning off WLED light at %s with transition=%s",
                self._entry.data['host'], transition
            )
            await self.coordinator.async_turn_off(transition=transition)
            _LOGGER.debug("Successfully turned off WLED light at %s", self._entry.data['host'])

        except WLEDTimeoutError as err:
            _LOGGER.error(
                "Timeout while turning off WLED light at %s. The device may be busy or unresponsive. "
                "Please check the device and try again. Error: %s",
                self._entry.data['host'], err
            )

        except WLEDNetworkError as err:
            _LOGGER.error(
                "Network error while turning off WLED light at %s. Please check that the device is "
                "connected to your network and the IP address is correct. Error: %s",
                self._entry.data['host'], err
            )

        except WLEDCommandError as err:
            _LOGGER.error(
                "Command error while turning off WLED light at %s. The device may not support this "
                "command or there may be an issue with the request. Error: %s",
                self._entry.data['host'], err
            )

        except WLEDConnectionError as err:
            _LOGGER.error(
                "Connection error while turning off WLED light at %s. Please check the device status "
                "and network connectivity. Error: %s",
                self._entry.data['host'], err
            )

        except Exception as err:
            _LOGGER.exception(
                "Unexpected error while turning off WLED light at %s: %s",
                self._entry.data['host'], err
            )

    async def async_set_brightness(self, brightness: int, **kwargs: Any) -> None:
        """Set the brightness of the light with enhanced error handling."""
        if not self.coordinator.available:
            _LOGGER.warning(
                "Cannot set brightness for WLED light at %s - device is not available. Last error: %s",
                self._entry.data['host'],
                self.coordinator.last_error or "Unknown"
            )
            return

        if not isinstance(brightness, int) or not (0 <= brightness <= 255):
            _LOGGER.error(
                "Invalid brightness value %s for WLED light at %s. Must be an integer between 0 and 255.",
                brightness, self._entry.data['host']
            )
            return

        transition = kwargs.get(ATTR_TRANSITION)

        try:
            _LOGGER.debug(
                "Setting brightness of WLED light at %s to %s with transition=%s",
                self._entry.data['host'], brightness, transition
            )
            await self.coordinator.async_set_brightness(brightness, transition=transition)
            _LOGGER.debug("Successfully set brightness of WLED light at %s", self._entry.data['host'])

        except WLEDTimeoutError as err:
            _LOGGER.error(
                "Timeout while setting brightness of WLED light at %s. The device may be busy or unresponsive. "
                "Please check the device and try again. Error: %s",
                self._entry.data['host'], err
            )

        except WLEDNetworkError as err:
            _LOGGER.error(
                "Network error while setting brightness of WLED light at %s. Please check that the device is "
                "connected to your network and the IP address is correct. Error: %s",
                self._entry.data['host'], err
            )

        except WLEDCommandError as err:
            _LOGGER.error(
                "Command error while setting brightness of WLED light at %s. The device may not support this "
                "command or there may be an issue with the request. Error: %s",
                self._entry.data['host'], err
            )

        except WLEDConnectionError as err:
            _LOGGER.error(
                "Connection error while setting brightness of WLED light at %s. Please check the device status "
                "and network connectivity. Error: %s",
                self._entry.data['host'], err
            )

        except Exception as err:
            _LOGGER.exception(
                "Unexpected error while setting brightness of WLED light at %s: %s",
                self._entry.data['host'], err
            )

    async def async_set_effect(self, effect: str, **kwargs: Any) -> None:
        """Set the effect of the light with enhanced error handling."""
        if not self.coordinator.available:
            _LOGGER.warning(
                "Cannot set effect for WLED light at %s - device is not available. Last error: %s",
                self._entry.data['host'],
                self.coordinator.last_error or "Unknown"
            )
            return

        if not isinstance(effect, str) or not effect.strip():
            _LOGGER.error(
                "Invalid effect value '%s' for WLED light at %s. Must be a non-empty string.",
                effect, self._entry.data['host']
            )
            return

        effects = self.coordinator.data.get("effects", [])
        if effect in effects:
            effect_id = effects.index(effect)
            try:
                _LOGGER.debug(
                    "Setting effect of WLED light at %s to '%s' (ID: %s)",
                    self._entry.data['host'], effect, effect_id
                )
                await self.coordinator.async_set_effect(effect_id)
                _LOGGER.debug("Successfully set effect of WLED light at %s", self._entry.data['host'])
            except WLEDTimeoutError as err:
                _LOGGER.error(
                    "Timeout while setting effect of WLED light at %s. The device may be busy or unresponsive. "
                    "Please check the device and try again. Error: %s",
                    self._entry.data['host'], err
                )
            except WLEDNetworkError as err:
                _LOGGER.error(
                    "Network error while setting effect of WLED light at %s. Please check that the device is "
                    "connected to your network and the IP address is correct. Error: %s",
                    self._entry.data['host'], err
                )
            except WLEDCommandError as err:
                _LOGGER.error(
                    "Command error while setting effect of WLED light at %s. The device may not support this "
                    "command or there may be an issue with the request. Error: %s",
                    self._entry.data['host'], err
                )
            except WLEDConnectionError as err:
                _LOGGER.error(
                    "Connection error while setting effect of WLED light at %s. Please check the device status "
                    "and network connectivity. Error: %s",
                    self._entry.data['host'], err
                )
            except Exception as err:
                _LOGGER.exception(
                    "Unexpected error while setting effect of WLED light at %s: %s",
                    self._entry.data['host'], err
                )
        else:
            _LOGGER.warning(
                "Effect '%s' not found in available effects from WLED device at %s. "
                "Available effects: %s",
                effect, self._entry.data['host'], effects
            )




async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WLED JSONAPI lights from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    # Add main light entity
    async_add_entities([WLEDJSONAPILight(coordinator, entry)])

    # Note: Preset selection is now handled by the select platform instead of a light entity
    _LOGGER.debug("Added main light entity. Preset and playlist selection handled by select platform.")