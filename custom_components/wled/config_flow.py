"""Config flow for WLED integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typING import ConfigType

from .api import WLEDAPIClient
from .const import DOMAIN
from .exceptions import WLEDConnectionError, WLEDInvalidResponseError

_LOGGER = logging.getLogger(__name__)


class WLEDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WLED."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: Optional[str] = None
        self._discovery_info: Optional[zeroconf.ZeroconfServiceInfo] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            
            # Test connection
            client = WLEDAPIClient(host)
            try:
                if not await client.test_connection():
                    errors["base"] = "cannot_connect"
                else:
                    # Get device info for unique ID
                    info = await client.get_info()
                    mac = info.get("mac")
                    if mac:
                        await self.async_set_unique_id(mac, raise_on_progress=False)
                        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                    
                    return self.async_create_entry(
                        title=f"WLED ({host})",
                        data={CONF_HOST: host},
                    )
            except (WLEDConnectionError, WLEDInvalidResponseError):
                errors["base"] = "cannot_connect"
            except Exception:  # pragma: no cover
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        self._discovery_info = discovery_info
        self._host = discovery_info.host

        # Try to get device info for unique ID
        client = WLEDAPIClient(self._host)
        try:
            info = await client.get_info()
            mac = info.get("mac")
            if mac:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: self._host}
                )

            # Set context for discovery confirmation
            self.context["title_placeholders"] = {
                "name": info.get("name", f"WLED ({self._host})")
            }
        except (WLEDConnectionError, WLEDInvalidResponseError):
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pragma: no cover
            _LOGGER.exception("Unexpected exception during discovery")
            return self.async_abort(reason="unknown")
        finally:
            await client.close()

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle user confirmation of discovered device."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"WLED ({self._host})",
                data={CONF_HOST: self._host},
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "host": self._host,
                "name": self._discovery_info.name
                if self._discovery_info
                else "WLED Device"
            },
        )

    async def async_step_reconfigure(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            
            # Test connection
            client = WLEDAPIClient(host)
            try:
                if not await client.test_connection():
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates={CONF_HOST: host},
                    )
            except (WLEDConnectionError, WLEDInvalidResponseError):
                errors["base"] = "cannot_connect"
            except Exception:  # pragma: no cover
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )