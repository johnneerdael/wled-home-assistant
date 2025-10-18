"""Config flow for WLED JSONAPI integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import ConfigType

from .api import WLEDJSONAPIClient
from .const import DOMAIN
from .exceptions import (
    WLEDConnectionError,
    WLEDInvalidResponseError,
    WLEDTimeoutError,
    WLEDNetworkError,
    WLEDAuthenticationError,
    WLEDConfigurationError,
)

_LOGGER = logging.getLogger(__name__)


class WLEDJSONAPIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WLED JSONAPI."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: Optional[str] = None
        self._discovery_info: Optional[zeroconf.ZeroconfServiceInfo] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step with enhanced error handling and user guidance."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            # Validate host input
            if not host:
                errors["base"] = "invalid_host"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                    errors=errors,
                    description_placeholders={"error_details": "Please enter a valid IP address or hostname"}
                )

            _LOGGER.debug("Testing connection to WLED device at %s", host)

            # Test connection
            client = WLEDJSONAPIClient(host)
            try:
                if not await client.test_connection():
                    errors["base"] = "cannot_connect"
                    _LOGGER.warning("Connection test failed for WLED device at %s", host)
                else:
                    # Get device info for unique ID
                    try:
                        info = await client.get_info()
                        mac = info.get("mac")
                        device_name = info.get("name", "WLED Device")

                        if mac:
                            await self.async_set_unique_id(mac, raise_on_progress=False)
                            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

                        _LOGGER.info("Successfully configured WLED device at %s (%s)", host, device_name)

                        return self.async_create_entry(
                            title=f"WLED ({device_name})",
                            data={CONF_HOST: host},
                        )
                    except WLEDInvalidResponseError as err:
                        _LOGGER.error("Invalid response from WLED device at %s: %s", host, err)
                        errors["base"] = "invalid_response"
                    except Exception as err:
                        _LOGGER.error("Error getting device info from %s: %s", host, err)
                        errors["base"] = "device_info_error"

            except WLEDTimeoutError as err:
                _LOGGER.warning("Connection timeout to WLED device at %s: %s", host, err)
                errors["base"] = "connection_timeout"
            except WLEDNetworkError as err:
                _LOGGER.warning("Network error connecting to WLED device at %s: %s", host, err)
                errors["base"] = "network_error"
            except WLEDAuthenticationError as err:
                _LOGGER.error("Authentication required for WLED device at %s: %s", host, err)
                errors["base"] = "authentication_required"
            except WLEDConnectionError as err:
                _LOGGER.warning("Connection error to WLED device at %s: %s", host, err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # pragma: no cover
                _LOGGER.exception("Unexpected exception during WLED setup for %s: %s", host, err)
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
            description_placeholders={
                "host": host if user_input else "your WLED device",
                "error_details": self._get_error_details(errors.get("base"))
            }
        )

    def _get_error_details(self, error_code: Optional[str]) -> str:
        """Get detailed error message for the user based on error code."""
        error_messages = {
            "invalid_host": "Please enter a valid IP address or hostname (e.g., 192.168.1.100 or wled.local)",
            "cannot_connect": "Could not connect to the WLED device. Please check:\n"
                              "• The device is powered on and connected to your network\n"
                              "• The IP address or hostname is correct\n"
                              "• No firewall is blocking the connection",
            "connection_timeout": "Connection timed out. The WLED device may be:\n"
                                 "• Powered off or rebooting\n"
                                 "• Too busy to respond\n"
                                 "• On a different network segment",
            "network_error": "Network connection failed. Please check:\n"
                            "• Your network connection\n"
                            "• The device is on the same network as Home Assistant\n"
                            "• DNS resolution is working (if using hostname)",
            "invalid_response": "The device responded but didn't provide valid WLED data. "
                              "This may not be a WLED device or it may be running incompatible firmware.",
            "authentication_required": "The WLED device requires authentication. "
                                     "This integration currently doesn't support password-protected devices.",
            "device_info_error": "Connected to the device but couldn't retrieve device information. "
                                "The device may be running incompatible firmware.",
            "unknown": "An unexpected error occurred. Please check the Home Assistant logs for details."
        }
        return error_messages.get(error_code, "Please check the logs for more details.")

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery with enhanced error handling."""
        self._discovery_info = discovery_info
        self._host = discovery_info.host
        device_name = discovery_info.name or f"WLED ({self._host})"

        _LOGGER.debug("Discovered WLED device via zeroconf: %s at %s", device_name, self._host)

        # Try to get device info for unique ID
        client = WLEDJSONAPIClient(self._host)
        try:
            info = await client.get_info()
            mac = info.get("mac")
            device_name = info.get("name", device_name)

            if mac:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: self._host}
                )

            # Set context for discovery confirmation
            self.context["title_placeholders"] = {
                "name": device_name
            }

            _LOGGER.info("Successfully discovered WLED device: %s at %s", device_name, self._host)

        except WLEDTimeoutError as err:
            _LOGGER.warning("Timeout during discovery of WLED device at %s: %s", self._host, err)
            return self.async_abort(reason="connection_timeout")
        except WLEDNetworkError as err:
            _LOGGER.warning("Network error during discovery of WLED device at %s: %s", self._host, err)
            return self.async_abort(reason="network_error")
        except WLEDAuthenticationError as err:
            _LOGGER.error("Authentication required during discovery of WLED device at %s: %s", self._host, err)
            return self.async_abort(reason="authentication_required")
        except WLEDInvalidResponseError as err:
            _LOGGER.error("Invalid response during discovery of WLED device at %s: %s", self._host, err)
            return self.async_abort(reason="invalid_response")
        except WLEDConnectionError as err:
            _LOGGER.warning("Connection error during discovery of WLED device at %s: %s", self._host, err)
            return self.async_abort(reason="cannot_connect")
        except Exception as err:  # pragma: no cover
            _LOGGER.exception("Unexpected exception during WLED discovery at %s: %s", self._host, err)
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
        """Handle reconfiguration with enhanced error handling."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()

            # Validate host input
            if not host:
                errors["base"] = "invalid_host"
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
                    errors=errors,
                )

            _LOGGER.debug("Testing reconfiguration connection to WLED device at %s", host)

            # Test connection
            client = WLEDJSONAPIClient(host)
            try:
                if not await client.test_connection():
                    errors["base"] = "cannot_connect"
                    _LOGGER.warning("Reconfiguration connection test failed for WLED device at %s", host)
                else:
                    _LOGGER.info("Successfully reconfigured WLED device at %s", host)
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates={CONF_HOST: host},
                    )

            except WLEDTimeoutError as err:
                _LOGGER.warning("Reconfiguration connection timeout to WLED device at %s: %s", host, err)
                errors["base"] = "connection_timeout"
            except WLEDNetworkError as err:
                _LOGGER.warning("Reconfiguration network error to WLED device at %s: %s", host, err)
                errors["base"] = "network_error"
            except WLEDAuthenticationError as err:
                _LOGGER.error("Reconfiguration authentication required for WLED device at %s: %s", host, err)
                errors["base"] = "authentication_required"
            except WLEDInvalidResponseError as err:
                _LOGGER.error("Reconfiguration invalid response from WLED device at %s: %s", host, err)
                errors["base"] = "invalid_response"
            except WLEDConnectionError as err:
                _LOGGER.warning("Reconfiguration connection error to WLED device at %s: %s", host, err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # pragma: no cover
                _LOGGER.exception("Unexpected exception during WLED reconfiguration for %s: %s", host, err)
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )