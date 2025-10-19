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

from .const import (
    DOMAIN,
    KEY_BRIGHTNESS,
    KEY_EFFECT,
    KEY_NAME,
    KEY_ON,
    KEY_PALETTE,
    KEY_PRESET,
    KEY_MAC,
    KEY_ARCH,
    DEFAULT_DEVICE_NAME,
    MAC_PREFIX,
    ARCH_PREFIX
)
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

    def _get_device_name(self, info: Dict[str, Any]) -> str:
        """Get device name with improved fallback strategy.

        Priority order:
        1. Device name from WLED config
        2. MAC address based name (e.g., "WLED-A1B2C3")
        3. Architecture-based name (e.g., "WLED ESP32")
        4. Generic name ("WLED Device")

        Args:
            info: Device info dictionary from WLED API

        Returns:
            Device name string, never None
        """
        # Priority 1: Try device name from WLED info first
        device_name = info.get(KEY_NAME)
        if device_name and isinstance(device_name, str):
            device_name = device_name.strip()
            if device_name:
                _LOGGER.debug("Using WLED device name: %s", device_name)
                return device_name

        # Priority 2: Try MAC address based name
        mac = info.get(KEY_MAC)
        if mac and isinstance(mac, str):
            mac_clean = mac.replace(":", "").replace("-", "").upper()
            if len(mac_clean) >= 6:
                mac_suffix = mac_clean[-6:]
                mac_name = f"{MAC_PREFIX}{mac_suffix}"
                _LOGGER.debug("Using MAC-based name: %s (from MAC: %s)", mac_name, mac)
                return mac_name

        # Priority 3: Try architecture-based name
        arch = info.get(KEY_ARCH)
        if arch and isinstance(arch, str):
            arch_clean = arch.strip()
            if arch_clean and arch_clean.lower() != "unknown":
                arch_name = f"{ARCH_PREFIX}{arch_clean}"
                _LOGGER.debug("Using architecture-based name: %s", arch_name)
                return arch_name

        # Priority 4: Final fallback - generic name
        _LOGGER.debug("Using default device name: %s", DEFAULT_DEVICE_NAME)
        return DEFAULT_DEVICE_NAME

    @property
    def available(self) -> bool:
        """Return True if the light is available."""
        return self.coordinator.available

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this light."""
        info = self.coordinator.data.get("info", {})
        device_name = self._get_device_name(info)

        _LOGGER.debug(
            "WLED device info: name='%s', host='%s', identifiers=%s",
            device_name, self._entry.data['host'], {(DOMAIN, self._entry.unique_id)}
        )

        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.unique_id)},
            name=device_name,
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
        """Turn on the light with comprehensive logging and error handling."""
        host = self._entry.data['host']

        # Log turn_on attempt at INFO level
        _LOGGER.info(
            "WLED Light Turn On: %s | Available: %s | Current State: %s",
            host, self.coordinator.available, self.is_on
        )

        if not self.coordinator.available:
            _LOGGER.warning(
                "WLED Light Turn On Failed: %s | Device unavailable | Last Error: %s",
                host, self.coordinator.last_error or "Unknown"
            )
            return

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        transition = kwargs.get(ATTR_TRANSITION)
        effect = kwargs.get(ATTR_EFFECT)
        preset = None

        # Log input parameters
        _LOGGER.debug(
            "WLED Light Turn On Params: %s | Brightness: %s, Transition: %s, Effect: %s",
            host, brightness, transition, effect
        )

        # Handle effect selection with detailed logging
        if effect is not None:
            effects = self.coordinator.data.get("effects", [])
            _LOGGER.debug(
                "WLED Light Effect Lookup: %s | Requested: '%s' | Available: %s",
                host, effect, effects
            )

            if effect in effects:
                preset = effects.index(effect)
                _LOGGER.info(
                    "WLED Light Effect Found: %s | Effect: '%s' -> Preset ID: %s",
                    host, effect, preset
                )
            else:
                _LOGGER.warning(
                    "WLED Light Effect Not Found: %s | Effect: '%s' | Available: %s",
                    host, effect, effects
                )

        # Log the final command that will be sent
        _LOGGER.info(
            "WLED Light Turn On Command: %s | Brightness: %s | Transition: %s | Preset: %s",
            host, brightness, transition, preset
        )

        try:
            await self.coordinator.async_turn_on(
                brightness=brightness,
                transition=transition,
                preset=preset,
            )
            _LOGGER.info("WLED Light Turn On Success: %s", host)

        except WLEDTimeoutError as err:
            _LOGGER.error(
                "WLED Light Turn On Timeout: %s | Device may be busy or unresponsive | Error: %s",
                host, err
            )

        except WLEDNetworkError as err:
            _LOGGER.error(
                "WLED Light Turn On Network Error: %s | Check network connectivity and IP address | Error: %s",
                host, err
            )

        except WLEDCommandError as err:
            _LOGGER.error(
                "WLED Light Turn On Command Error: %s | Device may not support this command | Error: %s",
                host, err
            )

        except WLEDConnectionError as err:
            _LOGGER.error(
                "WLED Light Turn On Connection Error: %s | Check device status and network | Error: %s",
                host, err
            )

        except Exception as err:
            _LOGGER.exception(
                "WLED Light Turn On Unexpected Error: %s | Error: %s",
                host, err
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light with comprehensive logging and error handling."""
        host = self._entry.data['host']

        # Log turn_off attempt at INFO level
        _LOGGER.info(
            "WLED Light Turn Off: %s | Available: %s | Current State: %s",
            host, self.coordinator.available, self.is_on
        )

        if not self.coordinator.available:
            _LOGGER.warning(
                "WLED Light Turn Off Failed: %s | Device unavailable | Last Error: %s",
                host, self.coordinator.last_error or "Unknown"
            )
            return

        transition = kwargs.get(ATTR_TRANSITION)

        # Log input parameters
        _LOGGER.debug(
            "WLED Light Turn Off Params: %s | Transition: %s",
            host, transition
        )

        # Log the final command that will be sent
        _LOGGER.info(
            "WLED Light Turn Off Command: %s | Transition: %s",
            host, transition
        )

        try:
            await self.coordinator.async_turn_off(transition=transition)
            _LOGGER.info("WLED Light Turn Off Success: %s", host)

        except WLEDTimeoutError as err:
            _LOGGER.error(
                "WLED Light Turn Off Timeout: %s | Device may be busy or unresponsive | Error: %s",
                host, err
            )

        except WLEDNetworkError as err:
            _LOGGER.error(
                "WLED Light Turn Off Network Error: %s | Check network connectivity and IP address | Error: %s",
                host, err
            )

        except WLEDCommandError as err:
            _LOGGER.error(
                "WLED Light Turn Off Command Error: %s | Device may not support this command | Error: %s",
                host, err
            )

        except WLEDConnectionError as err:
            _LOGGER.error(
                "WLED Light Turn Off Connection Error: %s | Check device status and network | Error: %s",
                host, err
            )

        except Exception as err:
            _LOGGER.exception(
                "WLED Light Turn Off Unexpected Error: %s | Error: %s",
                host, err
            )

    async def async_set_brightness(self, brightness: int, **kwargs: Any) -> None:
        """Set the brightness of the light with comprehensive logging and error handling."""
        host = self._entry.data['host']

        # Log brightness change attempt at INFO level
        _LOGGER.info(
            "WLED Light Set Brightness: %s | Available: %s | Current Brightness: %s -> %s",
            host, self.coordinator.available, self.brightness, brightness
        )

        if not self.coordinator.available:
            _LOGGER.warning(
                "WLED Light Set Brightness Failed: %s | Device unavailable | Last Error: %s",
                host, self.coordinator.last_error or "Unknown"
            )
            return

        if not isinstance(brightness, int) or not (0 <= brightness <= 255):
            _LOGGER.error(
                "WLED Light Set Brightness Invalid: %s | Brightness: %s | Must be integer 0-255",
                host, brightness
            )
            return

        transition = kwargs.get(ATTR_TRANSITION)

        # Log input parameters
        _LOGGER.debug(
            "WLED Light Set Brightness Params: %s | Brightness: %s, Transition: %s",
            host, brightness, transition
        )

        # Log the final command that will be sent
        _LOGGER.info(
            "WLED Light Set Brightness Command: %s | Brightness: %s | Transition: %s",
            host, brightness, transition
        )

        try:
            await self.coordinator.async_set_brightness(brightness, transition=transition)
            _LOGGER.info("WLED Light Set Brightness Success: %s | Brightness: %s", host, brightness)

        except WLEDTimeoutError as err:
            _LOGGER.error(
                "WLED Light Set Brightness Timeout: %s | Device may be busy or unresponsive | Error: %s",
                host, err
            )

        except WLEDNetworkError as err:
            _LOGGER.error(
                "WLED Light Set Brightness Network Error: %s | Check network connectivity and IP address | Error: %s",
                host, err
            )

        except WLEDCommandError as err:
            _LOGGER.error(
                "WLED Light Set Brightness Command Error: %s | Device may not support this command | Error: %s",
                host, err
            )

        except WLEDConnectionError as err:
            _LOGGER.error(
                "WLED Light Set Brightness Connection Error: %s | Check device status and network | Error: %s",
                host, err
            )

        except Exception as err:
            _LOGGER.exception(
                "WLED Light Set Brightness Unexpected Error: %s | Error: %s",
                host, err
            )

    async def async_set_effect(self, effect: str, **kwargs: Any) -> None:
        """Set the effect of the light with comprehensive logging and error handling."""
        host = self._entry.data['host']

        # Log effect change attempt at INFO level
        _LOGGER.info(
            "WLED Light Set Effect: %s | Available: %s | Current Effect: %s -> %s",
            host, self.coordinator.available, self.effect, effect
        )

        if not self.coordinator.available:
            _LOGGER.warning(
                "WLED Light Set Effect Failed: %s | Device unavailable | Last Error: %s",
                host, self.coordinator.last_error or "Unknown"
            )
            return

        if not isinstance(effect, str) or not effect.strip():
            _LOGGER.error(
                "WLED Light Set Effect Invalid: %s | Effect: '%s' | Must be non-empty string",
                host, effect
            )
            return

        effects = self.coordinator.data.get("effects", [])

        # Log effect lookup details
        _LOGGER.debug(
            "WLED Light Effect Lookup: %s | Requested: '%s' | Available: %s",
            host, effect, effects
        )

        if effect in effects:
            effect_id = effects.index(effect)
            _LOGGER.info(
                "WLED Light Effect Found: %s | Effect: '%s' -> ID: %s",
                host, effect, effect_id
            )

            # Log the final command that will be sent
            _LOGGER.info(
                "WLED Light Set Effect Command: %s | Effect: '%s' (ID: %s)",
                host, effect, effect_id
            )

            try:
                await self.coordinator.async_set_effect(effect_id)
                _LOGGER.info("WLED Light Set Effect Success: %s | Effect: '%s'", host, effect)

            except WLEDTimeoutError as err:
                _LOGGER.error(
                    "WLED Light Set Effect Timeout: %s | Device may be busy or unresponsive | Error: %s",
                    host, err
                )
            except WLEDNetworkError as err:
                _LOGGER.error(
                    "WLED Light Set Effect Network Error: %s | Check network connectivity and IP address | Error: %s",
                    host, err
                )
            except WLEDCommandError as err:
                _LOGGER.error(
                    "WLED Light Set Effect Command Error: %s | Device may not support this command | Error: %s",
                    host, err
                )
            except WLEDConnectionError as err:
                _LOGGER.error(
                    "WLED Light Set Effect Connection Error: %s | Check device status and network | Error: %s",
                    host, err
                )
            except Exception as err:
                _LOGGER.exception(
                    "WLED Light Set Effect Unexpected Error: %s | Error: %s",
                    host, err
                )
        else:
            _LOGGER.warning(
                "WLED Light Effect Not Found: %s | Effect: '%s' | Available: %s",
                host, effect, effects
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