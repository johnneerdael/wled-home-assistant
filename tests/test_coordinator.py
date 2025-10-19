"""Tests for WLED Data Coordinator."""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.wled_jsonapi.coordinator import WLEDJSONAPIDataCoordinator
from custom_components.wled_jsonapi.exceptions import (
    WLEDConnectionError,
    WLEDTimeoutError,
    WLEDInvalidResponseError,
)
from custom_components.wled_jsonapi.models import WLEDPresetsData, WLEDEssentialPresetsData


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.async_add_executor_job = Mock()
    return hass


@pytest.fixture
def mock_client():
    """Create a mock WLED API client."""
    client = AsyncMock()
    return client


@pytest.fixture
def coordinator(mock_hass, mock_client):
    """Create a WLED data coordinator for testing."""
    return WLEDJSONAPIDataCoordinator(mock_hass, mock_client)


@pytest.mark.asyncio
async def test_async_config_entry_first_refresh_success(coordinator):
    """Test successful initial data refresh."""
    # Mock successful API responses with full state data including effects
    coordinator._client.get_full_state.return_value = {
        "state": {"on": True, "bri": 255},
        "info": {"name": "Test WLED", "ver": "0.13.0"},
        "effects": ["Solid", "Blink", "Breathe"],
        "palettes": ["Default", "Rainbow", "Sunset"]
    }
    coordinator._client.get_essential_presets.return_value = WLEDEssentialPresetsData()

    # Test initial refresh
    await coordinator.async_config_entry_first_refresh()

    # Verify data was fetched including effects
    assert coordinator.data["state"]["on"] is True
    assert coordinator.data["info"]["name"] == "Test WLED"
    assert "effects" in coordinator.data
    assert "palettes" in coordinator.data
    assert len(coordinator.data["effects"]) == 3
    assert coordinator.connection_state == "connected"


@pytest.mark.asyncio
async def test_async_config_entry_first_refresh_failure(coordinator):
    """Test initial data refresh failure."""
    # Mock API failure
    coordinator._client.get_state.side_effect = WLEDConnectionError("Connection failed")

    # Test that ConfigEntryNotReady is raised
    with pytest.raises(Exception):  # ConfigEntryNotReady
        await coordinator.async_config_entry_first_refresh()


@pytest.mark.asyncio
async def test_async_update_data_success(coordinator):
    """Test successful data update."""
    # Mock successful API responses with full state including effects
    coordinator._client.get_full_state.return_value = {
        "state": {"on": True, "bri": 200},
        "info": {"name": "Test WLED", "ver": "0.13.0"},
        "effects": ["Solid", "Blink", "Breathe", "Wipe"],
        "palettes": ["Default", "Rainbow"]
    }

    # Test data update
    result = await coordinator._async_update_data()

    # Verify data was fetched and returned including effects
    assert result["state"]["on"] is True
    assert result["state"]["bri"] == 200
    assert result["info"]["name"] == "Test WLED"
    assert "effects" in result
    assert len(result["effects"]) == 4
    assert "palettes" in result
    assert len(result["palettes"]) == 2


@pytest.mark.asyncio
async def test_async_update_data_connection_error(coordinator):
    """Test data update with connection error."""
    # Mock connection error
    coordinator._client.get_full_state.side_effect = WLEDConnectionError("Connection failed")

    # Test that UpdateFailed is raised
    with pytest.raises(UpdateFailed, match="Error communicating with API"):
        await coordinator._async_update_data()

    # Verify connection state is updated
    assert coordinator.connection_state == "error"


@pytest.mark.asyncio
async def test_async_update_data_timeout_error(coordinator):
    """Test data update with timeout error."""
    # Mock timeout error
    coordinator._client.get_full_state.side_effect = WLEDTimeoutError("Request timeout")

    # Test that UpdateFailed is raised
    with pytest.raises(UpdateFailed, match="Error communicating with API"):
        await coordinator._async_update_data()

    # Verify connection state is updated
    assert coordinator.connection_state == "error"


@pytest.mark.asyncio
async def test_async_update_data_invalid_response(coordinator):
    """Test data update with invalid response."""
    # Mock invalid response
    coordinator._client.get_full_state.side_effect = WLEDInvalidResponseError("Invalid JSON")

    # Test that UpdateFailed is raised
    with pytest.raises(UpdateFailed, match="Error communicating with API"):
        await coordinator._async_update_data()

    # Verify connection state is updated
    assert coordinator.connection_state == "error"


@pytest.mark.asyncio
async def test_async_update_presets_if_needed(coordinator):
    """Test preset update when needed."""
    # Mock presets response
    mock_presets_data = WLEDPresetsData()
    coordinator._client.get_presets.return_value = mock_presets_data

    # Set last update time to more than an hour ago
    coordinator._presets_last_updated = None

    # Test preset update
    await coordinator._async_update_presets_if_needed()

    # Verify presets were fetched
    assert coordinator._presets_data == mock_presets_data
    assert coordinator._presets_last_updated is not None


@pytest.mark.asyncio
async def test_async_update_presets_if_needed_not_required(coordinator):
    """Test preset update when not needed (recent update)."""
    # Mock recent update time
    coordinator._presets_last_updated = asyncio.get_event_loop().time() - 1800  # 30 minutes ago
    coordinator._presets_data = WLEDPresetsData()

    # Test that no update occurs
    await coordinator._async_update_presets_if_needed()

    # Verify no API calls were made
    coordinator._client.get_presets.assert_not_called()


@pytest.mark.asyncio
async def test_async_update_presets_if_needed_failure(coordinator):
    """Test preset update with failure (should not break regular updates)."""
    # Mock preset API failure
    coordinator._client.get_presets.side_effect = WLEDConnectionError("Presets unavailable")

    # Test that failure doesn't raise exception
    await coordinator._async_update_presets_if_needed()

    # Verify error is handled gracefully
    assert coordinator._presets_data is None
    assert coordinator.last_error is not None


def test_get_preset_by_id_exists(coordinator):
    """Test getting preset by ID when it exists."""
    # Create mock preset data
    mock_presets = WLEDPresetsData()
    mock_presets.presets["1"] = Mock()
    mock_presets.presets["1"].name = "Test Preset"

    coordinator._presets_data = mock_presets

    # Test getting existing preset
    preset = coordinator.get_preset_by_id("1")
    assert preset is not None
    assert preset.name == "Test Preset"


def test_get_preset_by_id_not_exists(coordinator):
    """Test getting preset by ID when it doesn't exist."""
    # Create empty preset data
    coordinator._presets_data = WLEDPresetsData()

    # Test getting non-existent preset
    preset = coordinator.get_preset_by_id("999")
    assert preset is None


def test_get_playlist_by_id_exists(coordinator):
    """Test getting playlist by ID when it exists."""
    # Create mock playlist data
    mock_presets = WLEDPresetsData()
    mock_presets.playlists["1"] = Mock()
    mock_presets.playlists["1"].name = "Test Playlist"

    coordinator._presets_data = mock_presets

    # Test getting existing playlist
    playlist = coordinator.get_playlist_by_id("1")
    assert playlist is not None
    assert playlist.name == "Test Playlist"


def test_get_playlist_by_id_not_exists(coordinator):
    """Test getting playlist by ID when it doesn't exist."""
    # Create empty preset data
    coordinator._presets_data = WLEDPresetsData()

    # Test getting non-existent playlist
    playlist = coordinator.get_playlist_by_id("999")
    assert playlist is None


def test_get_all_preset_names(coordinator):
    """Test getting all preset names."""
    # Create mock preset data
    mock_presets = WLEDPresetsData()
    mock_presets.presets["1"] = Mock()
    mock_presets.presets["1"].name = "Preset One"
    mock_presets.presets["2"] = Mock()
    mock_presets.presets["2"].name = "Preset Two"

    coordinator._presets_data = mock_presets

    # Test getting preset names
    preset_names = coordinator.get_all_preset_names()
    assert preset_names == {"1": "Preset One", "2": "Preset Two"}


def test_get_all_playlist_names(coordinator):
    """Test getting all playlist names."""
    # Create mock playlist data
    mock_presets = WLEDPresetsData()
    mock_presets.playlists["1"] = Mock()
    mock_presets.playlists["1"].name = "Playlist One"
    mock_presets.playlists["2"] = Mock()
    mock_presets.playlists["2"].name = "Playlist Two"

    coordinator._presets_data = mock_presets

    # Test getting playlist names
    playlist_names = coordinator.get_all_playlist_names()
    assert playlist_names == {"1": "Playlist One", "2": "Playlist Two"}


@pytest.mark.asyncio
async def test_async_activate_playlist_success(coordinator):
    """Test successful playlist activation."""
    # Mock playlist and API response
    mock_playlist = Mock()
    mock_playlist.playlist = Mock()
    mock_playlist.playlist.ps = [1, 2, 3]
    coordinator._presets_data = WLEDPresetsData()
    coordinator._presets_data.playlists["1"] = mock_playlist
    coordinator._client.update_state.return_value = {"on": True}

    # Test playlist activation
    result = await coordinator.async_activate_playlist("1")

    # Verify API was called with playlist preset ID
    coordinator._client.update_state.assert_called_once_with({"pl": "1"})
    assert result["on"] is True


@pytest.mark.asyncio
async def test_async_activate_playlist_not_found(coordinator):
    """Test playlist activation when playlist doesn't exist."""
    # Create empty preset data
    coordinator._presets_data = WLEDPresetsData()

    # Test that ValueError is raised for non-existent playlist
    with pytest.raises(ValueError, match="Playlist 1 not found"):
        await coordinator.async_activate_playlist("1")


@pytest.mark.asyncio
async def test_async_set_brightness(coordinator):
    """Test setting brightness."""
    # Mock API response
    coordinator._client.update_state.return_value = {"on": True, "bri": 128}

    # Test setting brightness
    result = await coordinator.async_set_brightness(128)

    # Verify API was called
    coordinator._client.update_state.assert_called_once_with({"bri": 128})
    assert result["on"] is True


@pytest.mark.asyncio
async def test_async_set_effect(coordinator):
    """Test setting effect."""
    # Mock API response
    coordinator._client.update_state.return_value = {"on": True}

    # Test setting effect
    result = await coordinator.async_set_effect(5, speed=128, intensity=200, palette=3)

    # Verify API was called with effect parameters
    coordinator._client.update_state.assert_called_once_with({
        "seg": [{"fx": 5, "sx": 128, "ix": 200, "pal": 3}]
    })
    assert result["on"] is True


def test_connection_state_property(coordinator):
    """Test connection state property."""
    # Test initial state
    assert coordinator.connection_state == "unknown"

    # Test successful update
    coordinator._last_successful_update = 123456
    assert coordinator.connection_state == "connected"

    # Test error state
    coordinator._last_error = "Connection failed"
    assert coordinator.connection_state == "error"


def test_available_property(coordinator):
    """Test available property."""
    # Test initial availability
    assert coordinator.available is False  # No successful update yet

    # Test after successful update
    coordinator._last_successful_update = 123456
    assert coordinator.available is True

    # Test after error
    coordinator._last_error = "Connection failed"
    assert coordinator.available is False