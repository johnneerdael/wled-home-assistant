"""Tests for WLED Select Entities."""
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from custom_components.wled_jsonapi.select import (
    WLEDJSONAPIPlaylistSelect,
    WLEDJSONAPIPresetSelect,
    WLEDPaletteSelect,
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


@pytest.fixture
def mock_coordinator_with_palettes():
    """Create a mock coordinator with palette data."""
    coordinator = AsyncMock()
    coordinator.data = {
        "state": {
            "on": True,
            "bri": 255,
            "ps": 1,
            "seg": [
                {"id": 0, "pal": 2, "fx": 1},
                {"id": 1, "pal": 2, "fx": 1}
            ],
            "mainseg": 0
        },
        "info": {"name": "Test WLED", "mac": "AA:BB:CC:DD:EE:FF", "arch": "ESP32", "ver": "0.13.0"},
        "palettes": [
            "Default",
            "Rainbow",
            "Sunset",
            "Ocean",
            "Forest"
        ],
        "presets": None,
    }
    coordinator.available = True
    coordinator.async_set_palette_for_all_segments = AsyncMock()
    return coordinator


@pytest.fixture
def palette_select(mock_hass, mock_coordinator_with_palettes):
    """Create a palette select entity."""
    entry = Mock()
    entry.entry_id = "test_entry_id"
    entry.unique_id = "AA:BB:CC:DD:EE:FF"
    entry.data = {"host": "192.168.1.100"}

    return WLEDPaletteSelect(mock_coordinator_with_palettes, entry)


def test_palette_select_init(palette_select):
    """Test palette select initialization."""
    assert palette_select._attr_unique_id == "test_entry_id_palette_select"
    assert palette_select._attr_has_entity_name is True
    assert palette_select.entity_description.key == "palette"
    assert palette_select.entity_description.translation_key == "palette"


def test_palette_select_available(palette_select):
    """Test palette select availability."""
    # Test when coordinator is available
    palette_select._coordinator.available = True
    assert palette_select.available is True

    # Test when coordinator is unavailable
    palette_select._coordinator.available = False
    assert palette_select.available is False


def test_palette_select_options(palette_select):
    """Test palette select options."""
    options = palette_select.options

    assert len(options) == 5
    assert options[0] == "Default"
    assert options[1] == "Rainbow"
    assert options[2] == "Sunset"
    assert options[3] == "Ocean"
    assert options[4] == "Forest"


def test_palette_select_current_option(palette_select):
    """Test getting current palette option."""
    # Current palette ID is 2, which should be "Sunset"
    current_option = palette_select.current_option
    assert current_option == "Sunset"


def test_palette_select_current_option_no_segments(palette_select):
    """Test getting current palette option when no segments exist."""
    palette_select._coordinator.data["state"]["seg"] = []

    current_option = palette_select.current_option
    assert current_option is None


def test_palette_select_current_option_no_palette_field(palette_select):
    """Test getting current palette option when palette field is missing."""
    palette_select._coordinator.data["state"]["seg"][0]["pal"] = None

    current_option = palette_select.current_option
    assert current_option is None


def test_palette_select_current_option_invalid_palette_id(palette_select):
    """Test getting current palette option with invalid palette ID."""
    palette_select._coordinator.data["state"]["seg"][0]["pal"] = 999

    current_option = palette_select.current_option
    assert current_option is None


def test_palette_select_current_option_uses_main_segment(palette_select):
    """Test that current option uses main segment when available."""
    # Change main segment to 1 and set different palette
    palette_select._coordinator.data["state"]["mainseg"] = 1
    palette_select._coordinator.data["state"]["seg"][1]["pal"] = 3  # Ocean

    current_option = palette_select.current_option
    assert current_option == "Ocean"


def test_palette_select_device_info(palette_select):
    """Test palette select device info."""
    device_info = palette_select.device_info

    assert device_info["identifiers"] == {("wled_jsonapi", "AA:BB:CC:DD:EE:FF")}
    assert device_info["name"] == "Test WLED"
    assert device_info["manufacturer"] == "WLED"
    assert device_info["model"] == "ESP32"
    assert device_info["sw_version"] == "0.13.0"
    assert device_info["configuration_url"] == "http://192.168.1.100"


@pytest.mark.asyncio
async def test_palette_select_select_option(palette_select):
    """Test selecting a palette option."""
    palette_select._coordinator.async_set_palette_for_all_segments.return_value = {"success": True}

    # Select "Ocean" palette (ID: 3)
    await palette_select.async_select_option("Ocean")

    # Verify API call was made with correct palette ID
    palette_select._coordinator.async_set_palette_for_all_segments.assert_called_once_with(3)


@pytest.mark.asyncio
async def test_palette_select_select_option_not_available(palette_select):
    """Test selecting a palette option when device is not available."""
    palette_select._coordinator.available = False

    # Should not raise exception, but should not call API
    await palette_select.async_select_option("Ocean")

    # Verify no API call was made
    palette_select._coordinator.async_set_palette_for_all_segments.assert_not_called()


@pytest.mark.asyncio
async def test_palette_select_select_option_invalid_option(palette_select):
    """Test selecting an invalid palette option."""
    # Should not raise exception, but should not call API
    await palette_select.async_select_option("Invalid Palette")

    # Verify no API call was made
    palette_select._coordinator.async_set_palette_for_all_segments.assert_not_called()


@pytest.mark.asyncio
async def test_palette_select_select_option_empty_string(palette_select):
    """Test selecting an empty palette option."""
    # Should not raise exception, but should not call API
    await palette_select.async_select_option("")

    # Verify no API call was made
    palette_select._coordinator.async_set_palette_for_all_segments.assert_not_called()


@pytest.mark.asyncio
async def test_palette_select_select_option_whitespace_only(palette_select):
    """Test selecting a whitespace-only palette option."""
    # Should not raise exception, but should not call API
    await palette_select.async_select_option("   ")

    # Verify no API call was made
    palette_select._coordinator.async_set_palette_for_all_segments.assert_not_called()


def test_palette_select_with_no_palettes(mock_hass, mock_coordinator):
    """Test palette select when no palettes are available."""
    mock_coordinator.data["palettes"] = []

    entry = Mock()
    entry.entry_id = "test_entry_id"
    entry.unique_id = "AA:BB:CC:DD:EE:FF"
    entry.data = {"host": "192.168.1.100"}

    palette_select = WLEDPaletteSelect(mock_coordinator, entry)

    options = palette_select.options
    assert len(options) == 0


def test_palette_select_device_info_fallback_naming(mock_hass, mock_coordinator_with_palettes):
    """Test device info with fallback naming when no name is provided."""
    # Remove device name
    mock_coordinator_with_palettes.data["info"]["name"] = None

    entry = Mock()
    entry.entry_id = "test_entry_id"
    entry.unique_id = "AA:BB:CC:DD:EE:FF"
    entry.data = {"host": "192.168.1.100"}

    palette_select = WLEDPaletteSelect(mock_coordinator_with_palettes, entry)

    # Should fall back to MAC-based naming
    device_info = palette_select.device_info
    assert device_info["name"] == "WLED-AABBCC"  # MAC suffix with prefix