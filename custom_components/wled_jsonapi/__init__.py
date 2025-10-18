"""WLED JSONAPI integration for Home Assistant."""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, CONF_HOST
from .coordinator import WLEDJSONAPIDataCoordinator
from .api import WLEDJSONAPIClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the WLED JSONAPI component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WLED JSONAPI from a config entry."""
    _LOGGER.debug("Setting up WLED JSONAPI integration for entry: %s", entry.title)

    host = entry.data[CONF_HOST]
    
    # Create API client
    client = WLEDJSONAPIClient(host)
    
    # Create coordinator
    coordinator = WLEDJSONAPIDataCoordinator(hass, client)
    
    # Store coordinator and client in hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "entry": entry,
    }

    # Perform initial data refresh
    await coordinator.async_config_entry_first_refresh()

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when it's updated
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading WLED JSONAPI integration for entry: %s", entry.title)

    data = hass.data[DOMAIN].get(entry.entry_id)
    if data:
        # Close the API client
        await data["client"].close()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)