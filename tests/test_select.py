"""Tests for WLED Select Entities."""
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from custom_components.wled_jsonapi.select import (
    WLEDJSONAPIPlaylistSelect,
    WLEDJSONAPIPresetSelect,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = AsyncMock()
    coordinator.data = {
        "state": {"on": True, "bri": 255, "ps": 1},
        "info": {"name": "Test WLED", "mac": "AA:BB:CC:DD:EE:FF"},
        "presets": None,
    }
    return coordinator


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock(spec=HomeAssistant)
    hass.async_add_job = Mock()
    return hass


@pytest.fixture
def preset_select(mock_hass, mock_coordinator):
    """Create a preset select entity."""
    return WLEDJSONAPIPresetSelect(mock_coordinator, "test_preset")


@pytest.fixture
def playlist_select(mock_hass, mock_coordinator):
    """Create a playlist select entity."""
    return WLEDJSONAPIPlaylistSelect(mock_coordinator, "test_playlist")


def test_preset_select_init(preset_select):
    """Test preset select initialization."""
    assert preset_select._attr_unique_id == "AA:BB:CC:DD:EE:FF_preset"
    assert preset_select._attr_name == "Preset"
    assert preset_select._attr_has_entity_name is True
    assert preset_select.entity_category == EntityCategory.CONFIG


def test_playlist_select_init(playlist_select):
    """Test playlist select initialization."""
    assert playlist_select._attr_unique_id == "AA:BB:CC:DD:EE:FF_playlist"
    assert playlist_select._attr_name == "Playlist"
    assert playlist_select._attr_has_entity_name is True
    assert playlist_select.entity_category == EntityCategory.CONFIG


def test_preset_select_options_no_presets(preset_select):
    """Test preset select options when no presets are available."""
    preset_select._coordinator.get_all_preset_names.return_value = {}

    options = preset_select._attr_options

    assert len(options) == 0


def test_preset_select_options_with_presets(preset_select):
    """Test preset select options with presets available."""
    preset_select._coordinator.get_all_preset_names.return_value = {
        "1": "Preset One",
        "2": "Preset Two",
        "3": "Preset Three"
    }

    options = preset_select._attr_options

    assert len(options) == 3
    assert options[0] == ("1", "Preset One")
    assert options[1] == ("2", "Preset Two")
    assert options[2] == ("3", "Preset Three")


def test_playlist_select_options_no_playlists(playlist_select):
    """Test playlist select options when no playlists are available."""
    playlist_select._coordinator.get_all_playlist_names.return_value = {}

    options = playlist_select._attr_options

    assert len(options) == 0


def test_playlist_select_options_with_playlists(playlist_select):
    """Test playlist select options with playlists available."""
    playlist_select._coordinator.get_all_playlist_names.return_value = {
        "1": "Playlist One",
        "2": "Playlist Two",
    }

    options = playlist_select._attr_options

    assert len(options) == 2
    assert options[0] == ("1", "Playlist One")
    assert options[1] == ("2", "Playlist Two")


def test_preset_select_current_option(preset_select):
    """Test getting current preset option."""
    preset_select._coordinator.data["state"]["ps"] = 2
    preset_select._coordinator.get_all_preset_names.return_value = {
        "1": "Preset One",
        "2": "Preset Two",
    }

    current_option = preset_select.current_option

    assert current_option == ("2", "Preset Two")


def test_preset_select_current_option_no_preset(preset_select):
    """Test getting current preset option when no preset is active."""
    preset_select._coordinator.data["state"]["ps"] = -1
    preset_select._coordinator.get_all_preset_names.return_value = {}

    current_option = preset_select.current_option

    assert current_option is None


def test_playlist_select_current_option(playlist_select):
    """Test getting current playlist option."""
    playlist_select._coordinator.data["state"]["pl"] = 1
    playlist_select._coordinator.get_all_playlist_names.return_value = {
        "1": "Playlist One",
        "2": "Playlist Two",
    }

    current_option = playlist_select.current_option

    assert current_option == ("1", "Playlist One")


def test_playlist_select_current_option_no_playlist(playlist_select):
    """Test getting current playlist option when no playlist is active."""
    playlist_select._coordinator.data["state"]["pl"] = -1
    playlist_select._coordinator.get_all_playlist_names.return_value = {}

    current_option = playlist_select.current_option

    assert current_option is None


def test_preset_select_available(preset_select):
    """Test preset select availability."""
    # Test when coordinator is available
    preset_select._coordinator.available = True
    assert preset_select.available is True

    # Test when coordinator is unavailable
    preset_select._coordinator.available = False
    assert preset_select.available is False


def test_playlist_select_available(playlist_select):
    """Test playlist select availability."""
    # Test when coordinator is available
    playlist_select._coordinator.available = True
    assert playlist_select.available is True

    # Test when coordinator is unavailable
    playlist_select._coordinator.available = False
    assert playlist_select.available is False


@pytest.mark.asyncio
async def test_preset_select_select_option(preset_select):
    """Test selecting a preset option."""
    preset_select._coordinator.async_set_preset.return_value = {"on": True}
    preset_select.async_write_ha_state_value = AsyncMock()

    # Select preset "2"
    await preset_select.async_select_option(("2", "Preset Two"))

    # Verify API call was made
    preset_select._coordinator.async_set_preset.assert_called_once_with(2)
    preset_select.async_write_ha_state_value.assert_called_once()


@pytest.mark.asyncio
async def test_preset_select_select_option_invalid(preset_select):
    """Test selecting an invalid preset option."""
    # Select invalid preset
    with pytest.raises(ValueError, match="Invalid preset selected"):
        await preset_select.async_select_option(("999", "Invalid Preset"))


@pytest.mark.asyncio
async def test_playlist_select_select_option(playlist_select):
    """Test selecting a playlist option."""
    playlist_select._coordinator.async_activate_playlist.return_value = {"on": True}
    playlist_select.async_write_ha_state_value = AsyncMock()

    # Select playlist "1"
    await playlist_select.async_select_option(("1", "Playlist One"))

    # Verify API call was made
    playlist_select._coordinator.async_activate_playlist.assert_called_once_with("1")
    playlist_select.async_write_ha_state_value.assert_called_once()


@pytest.mark.asyncio
async def test_playlist_select_select_option_invalid(playlist_select):
    """Test selecting an invalid playlist option."""
    # Select invalid playlist
    with pytest.raises(ValueError, match="Invalid playlist selected"):
        await playlist_select.async_option(("999", "Invalid Playlist"))


def test_preset_select_device_info(preset_select):
    """Test preset select device info."""
    device_info = preset_select.device_info

    assert device_info["identifiers"] == [(DOMAIN, "AA:BB:CC:DD:EE:FF")]
    assert device_info["name"] == "Test WLED"
    assert device_info["via_device"] is None


def test_playlist_select_device_info(playlist_select):
    """Test playlist select device info."""
    device_info = playlist_select.device_info

    assert device_info["identifiers"] == [(DOMAIN, "AA:BB:CC:DD:EE:FF")]
    assert device_info["name"] == "Test WLED"
    assert device_info["via_device"] is None


def test_preset_select_extra_state_attributes(preset_select):
    """Test preset select extra state attributes."""
    preset_select._coordinator.get_all_preset_names.return_value = {
        "1": "Preset One",
        "2": "Preset Two"
    }

    extra_attrs = preset_select.extra_state_attributes

    assert "options" in extra_attrs
    assert "1" in extra_attrs["options"]
    assert "2" in extra_attrs["options"]


def test_playlist_select_extra_state_attributes(playlist_select):
    """Test playlist select extra state attributes."""
    playlist_select._coordinator.get_all_playlist_names.return_value = {
        "1": "Playlist One",
        "2": "Playlist Two"
    }

    extra_attrs = playlist_select.extra_state_attributes

    assert "options" in extra_attrs
    assert "1" in extra_attrs["options"]
    assert "2" in extra_attrs["options"]


# Import DOMAIN for device info tests
from custom_components.wled_jsonapi.const import DOMAIN