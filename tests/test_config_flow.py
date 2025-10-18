"""Tests for WLED Config Flow."""
import pytest
from unittest.mock import AsyncMock, Mock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_HOST
from homeassistant.components.zeroconf import ZeroconfServiceInfo

from custom_components.wled_jsonapi import config_flow
from custom_components.wled_jsonapi.const import DOMAIN
from custom_components.wled_jsonapi.exceptions import WLEDConnectionError


@pytest.fixture
def mock_zeroconf_info():
    """Create mock zeroconf service info."""
    return ZeroconfServiceInfo(
        host="192.168.1.100",
        port=80,
        hostname="wled.local.",
        type="_wled._tcp.local.",
        name="WLED",
        properties={"mac": "AA:BB:CC:DD:EE:FF"},
    )


@pytest.fixture
def mock_client():
    """Create a mock WLED API client."""
    client = AsyncMock()
    client.test_connection.return_value = True
    client.get_info.return_value = {
        "name": "Test WLED",
        "mac": "AA:BB:CC:DD:EE:FF",
        "ver": "0.13.0",
        "leds": {"count": 144},
    }
    return client


class MockWLEDConfigFlow(config_flow.WLEDJSONAPIConfigFlow):
    """Mock config flow for testing."""

    def __init__(self):
        """Initialize mock config flow."""
        super().__init__()
        self._mock_client = None


def test_flow_user_init():
    """Test user flow initialization."""
    flow = MockWLEDConfigFlow()
    assert flow._async_current_step() == "user"
    assert flow.VERSION == 1


@pytest.mark.asyncio
async def test_user_step_success(mock_client):
    """Test successful user step."""
    flow = MockWLEDConfigFlow()

    with patch.object(config_flow, "WLEDJSONAPIClient", return_value=mock_client):
        result = await flow.async_step_user({CONF_HOST: "192.168.1.100"})

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Test WLED"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_user_step_connection_failure():
    """Test user step with connection failure."""
    flow = MockWLEDConfigFlow()
    mock_client = AsyncMock()
    mock_client.test_connection.return_value = False

    with patch.object(config_flow, "WLEDJSONAPIClient", return_value=mock_client):
        result = await flow.async_step_user({CONF_HOST: "192.168.1.100"})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_user_step_invalid_host(mock_client):
    """Test user step with invalid host."""
    flow = MockWLEDConfigFlow()

    with patch.object(config_flow, "WLEDJSONAPIClient", return_value=mock_client):
        result = await flow.async_step_user({CONF_HOST: "invalid_host"})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_user_step_info_error(mock_client):
    """Test user step with info retrieval error."""
    flow = MockWLEDConfigFlow()
    mock_client.get_info.side_effect = WLEDConnectionError("Info fetch failed")

    with patch.object(config_flow, "WLEDJSONAPIClient", return_value=mock_client):
        result = await flow.async_step_user({CONF_HOST: "192.168.1.100"})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_zeroconf_confirm(mock_zeroconf_info, mock_client):
    """Test zeroconf discovery confirmation."""
    flow = MockWLEDConfigFlow()
    flow._discovery_info = mock_zeroconf_info

    with patch.object(config_flow, "WLEDJSONAPIClient", return_value=mock_client):
        result = await flow.async_step_zeroconf_confirm()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Test WLED"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_zeroconf_confirm_failure(mock_zeroconf_info):
    """Test zeroconf discovery confirmation with connection failure."""
    flow = MockWLEDConfigFlow()
    flow._discovery_info = mock_zeroconf_info
    mock_client = AsyncMock()
    mock_client.test_connection.return_value = False

    with patch.object(config_flow, "WLEDJSONAPIClient", return_value=mock_client):
        result = await flow.async_step_zeroconf_confirm()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.asyncio
async def test_reconfigure_success(mock_client):
    """Test successful reconfiguration."""
    flow = MockWLEDConfigFlow()
    mock_entry = Mock()
    mock_entry.data = {CONF_HOST: "192.168.1.100"}
    flow._entry = mock_entry

    with patch.object(config_flow, "WLEDJSONAPIClient", return_value=mock_client):
        result = await flow.async_step_reconfigure({CONF_HOST: "192.168.1.200"})

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert mock_entry.data[CONF_HOST] == "192.168.1.200"


@pytest.mark.asyncio
async def test_reconfigure_failure():
    """Test reconfiguration with connection failure."""
    flow = MockWLEDConfigFlow()
    mock_entry = Mock()
    mock_entry.data = {CONF_HOST: "192.168.1.100"}
    flow._entry = mock_entry
    mock_client = AsyncMock()
    mock_client.test_connection.return_value = False

    with patch.object(config_flow, "WLEDJSONAPIClient", return_value=mock_client):
        result = await flow.async_step_reconfigure({CONF_HOST: "192.168.1.200"})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"]["base"] == "cannot_connect"


def test_get_schema_for_step_user():
    """Test schema for user step."""
    flow = MockWLEDConfigFlow()
    schema = flow.get_schema_for_step("user")

    assert CONF_HOST in schema
    assert schema[CONF_HOST].description == "The IP address or hostname of your WLED device"


def test_get_schema_for_step_reconfigure():
    """Test schema for reconfigure step."""
    flow = MockWLEDConfigFlow()
    schema = flow.get_schema_for_step("reconfigure")

    assert CONF_HOST in schema
    assert schema[CONF_HOST].description == "The IP address or hostname of your WLED device"


