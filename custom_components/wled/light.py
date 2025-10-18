"""Light platform for WLED integration."""
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
from .coordinator import WLEDDataCoordinator

_LOGGER = logging.getLogger(__name__)


class WLEDLight(CoordinatorEntity, LightEntity):
    """Representation of a WLED light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: WLEDDataCoordinator, entry: ConfigEntry) -> None:
        """Initialize the WLED light."""
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
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        transition = kwargs.get(ATTR_TRANSITION)
        effect = kwargs.get(ATTR_EFFECT)
        preset = None

        # Handle effect selection
        if effect is not None:
            effects = self.coordinator.data.get("effects", [])
            if effect in effects:
                preset = effects.index(effect)
            else:
                _LOGGER.warning("Effect '%s' not found in available effects", effect)

        await self.coordinator.async_turn_on(
            brightness=brightness,
            transition=transition,
            preset=preset,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        transition = kwargs.get(ATTR_TRANSITION)
        await self.coordinator.async_turn_off(transition=transition)

    async def async_set_brightness(self, brightness: int, **kwargs: Any) -> None:
        """Set the brightness of the light."""
        transition = kwargs.get(ATTR_TRANSITION)
        await self.coordinator.async_set_brightness(brightness, transition=transition)

    async def async_set_effect(self, effect: str, **kwargs: Any) -> None:
        """Set the effect of the light."""
        effects = self.coordinator.data.get("effects", [])
        if effect in effects:
            effect_id = effects.index(effect)
            await self.coordinator.async_set_effect(effect_id)
        else:
            _LOGGER.warning("Effect '%s' not found in available effects", effect)


class WLEDPresetLight(CoordinatorEntity, LightEntity):
    """Representation of a WLED preset selector."""

    _attr_has_entity_name = True
    _attr_name = "Preset"

    def __init__(self, coordinator: WLEDDataCoordinator, entry: ConfigEntry) -> None:
        """Initialize the WLED preset light."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_preset"

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
        """Return the current preset as brightness."""
        state = self.coordinator.data.get("state", {})
        return state.get(KEY_PRESET, 0)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return ColorMode.BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return {ColorMode.BRIGHTNESS}

    @property
    def min_brightness(self) -> int:
        """Return the minimum brightness (preset ID)."""
        return 0

    @property
    def max_brightness(self) -> int:
        """Return the maximum brightness (preset ID)."""
        return 250

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light and set preset."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        transition = kwargs.get(ATTR_TRANSITION)

        if brightness is not None:
            await self.coordinator.async_set_preset(brightness)
        else:
            await self.coordinator.async_turn_on(transition=transition)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        transition = kwargs.get(ATTR_TRANSITION)
        await self.coordinator.async_turn_off(transition=transition)

    async def async_set_brightness(self, brightness: int, **kwargs: Any) -> None:
        """Set the preset."""
        await self.coordinator.async_set_preset(brightness)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up WLED lights from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    # Add main light entity
    async_add_entities([WLEDLight(coordinator, entry)])

    # Add preset selector if presets are available
    if coordinator.data.get("effects"):
        async_add_entities([WLEDPresetLight(coordinator, entry)])