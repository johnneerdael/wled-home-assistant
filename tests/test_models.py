"""Tests for WLED Data Models."""
import pytest

from custom_components.wled_jsonapi.models import (
    WLEDPreset,
    WLEDPlaylist,
    WLEDPresetsData,
)


def test_wled_preset_creation():
    """Test creating a WLED preset from data."""
    preset_data = {
        "n": "Test Preset",
        "on": True,
        "bri": 200,
        "transition": 7,
        "mainseg": 0,
        "seg": [
            {
                "id": 0,
                "start": 0,
                "stop": 144,
                "len": 144,
                "grp": 1,
                "spc": 0,
                "of": 0,
                "on": True,
                "frz": False,
                "bri": 255,
                "n": "Main Segment",
                "col": [[255, 255, 255], [0, 0, 0], [0, 0, 0]],
                "fx": 25,
                "sx": 128,
                "ix": 128,
                "pal": 0,
                "sel": True,
                "rev": False,
                "mi": False,
                "o1": False,
                "o2": False,
                "o3": False,
                "si": 0,
                "m12": 0
            }
        ]
    }

    preset = WLEDPreset("1", preset_data)

    assert preset.id == "1"
    assert preset.name == "Test Preset"
    assert preset.on is True
    assert preset.brightness == 200
    assert preset.transition == 7
    assert preset.main_segment == 0
    assert len(preset.segments) == 1
    assert preset.segments[0].id == 0
    assert preset.segments[0].name == "Main Segment"
    assert preset.segments[0].effect == 25


def test_wled_preset_minimal_data():
    """Test creating a WLED preset with minimal data."""
    preset_data = {
        "on": True,
        "bri": 255,
    }

    preset = WLEDPreset("2", preset_data)

    assert preset.id == "2"
    assert preset.name is None  # Default when no "n" field
    assert preset.on is True
    assert preset.brightness == 255
    assert preset.transition == 0  # Default value
    assert preset.segments == []  # Default empty list


def test_wled_preset_empty_data():
    """Test creating a WLED preset with empty data."""
    preset = WLEDPreset("3", {})

    assert preset.id == "3"
    assert preset.name is None
    assert preset.on is False  # Default when no "on" field
    assert preset.brightness == 255  # Default value
    assert preset.transition == 0
    assert preset.segments == []


def test_wled_preset_invalid_segment_data():
    """Test creating a WLED preset with invalid segment data."""
    preset_data = {
        "seg": "invalid_segment_data"  # Invalid data type
    }

    preset = WLEDPreset("4", preset_data)

    assert preset.id == "4"
    assert preset.segments == []  # Should handle invalid data gracefully


def test_wled_playlist_creation():
    """Test creating a WLED playlist from data."""
    playlist_data = {
        "n": "Test Playlist",
        "playlist": {
            "ps": [1, 2, 3],
            "dur": [30, 30, 30],
            "transition": [5, 5, 5],
            "repeat": 0,
            "end": 0,
            "r": 0
        },
        "on": True
    }

    playlist = WLEDPlaylist("101", playlist_data)

    assert playlist.id == "101"
    assert playlist.name == "Test Playlist"
    assert playlist.on is True
    assert playlist.preset_ids == [1, 2, 3]
    assert playlist.durations == [30, 30, 30]
    assert playlist.transitions == [5, 5, 5]
    assert playlist.repeat == 0
    assert playlist.end == 0
    assert playlist.shuffle == 0


def test_wled_playlist_minimal_data():
    """Test creating a WLED playlist with minimal data."""
    playlist_data = {
        "playlist": {
            "ps": [1, 2],
            "dur": [60, 60],
            "transition": [10, 10]
        }
    }

    playlist = WLEDPlaylist("102", playlist_data)

    assert playlist.id == "102"
    assert playlist.name is None  # Default when no "n" field
    assert playlist.on is False  # Default when no "on" field
    assert playlist.preset_ids == [1, 2]
    assert playlist.durations == [60, 60]
    assert playlist.transitions == [10, 10]
    assert playlist.repeat == 0  # Default value
    assert playlist.end == 0
    assert playlist.shuffle == 0


def test_wled_playlist_empty_data():
    """Test creating a WLED playlist with empty data."""
    playlist = WLEDPreset("103", {})

    assert playlist.id == "103"
    assert playlist.name is None
    assert playlist.on is False
    assert playlist.segments == []  # Preset should handle empty playlist data


def test_wled_playlist_invalid_playlist_data():
    """Test creating a WLED playlist with invalid playlist data."""
    playlist_data = {
        "playlist": "invalid_playlist_data"  # Invalid data type
    }

    playlist = WLEDPlaylist("104", playlist_data)

    assert playlist.id == "104"
    assert playlist.preset_ids == []  # Should handle invalid data gracefully
    assert playlist.durations == []
    assert playlist.transitions == []


def test_wled_presets_data_creation():
    """Test creating WLED presets data from full response."""
    data = {
        "1": {
            "n": "Preset One",
            "on": True,
            "bri": 200,
        },
        "2": {
            "n": "Preset Two",
            "on": False,
            "bri": 100,
        },
        "101": {
            "n": "Playlist One",
            "playlist": {
                "ps": [1, 2],
                "dur": [30, 30],
                "transition": [5, 5]
            }
        },
        "102": {
            "n": "Playlist Two",
            "playlist": {
                "ps": [3, 4],
                "dur": [60, 60],
                "transition": [10, 10]
            }
        }
    }

    presets_data = WLEDPresetsData.from_json_response(data)

    # Test presets
    assert len(presets_data.presets) == 2
    assert "1" in presets_data.presets
    assert "2" in presets_data.presets
    assert presets_data.presets["1"].name == "Preset One"
    assert presets_data.presets["2"].name == "Preset Two"
    assert presets_data.presets["1"].on is True
    assert presets_data.presets["2"].on is False

    # Test playlists
    assert len(presets_data.playlists) == 2
    assert "101" in presets_data.playlists
    assert "102" in presets_data.playlists
    assert presets_data.playlists["101"].name == "Playlist One"
    assert presets_data.playlists["102"].name == "Playlist Two"
    assert presets_data.playlists["101"].preset_ids == [1, 2]
    assert presets_data.playlists["102"].preset_ids == [3, 4]


def test_wled_presets_data_empty_response():
    """Test creating WLED presets data from empty response."""
    data = {}

    presets_data = WLEDPresetsData.from_json_response(data)

    assert len(presets_data.presets) == 0
    assert len(presets_data.playlists) == 0


def test_wled_presets_data_invalid_response():
    """Test creating WLED presets data from invalid response."""
    data = "invalid_json_data"

    presets_data = WLEDPresetsData.from_json_response(data)

    assert len(presets_data.presets) == 0
    assert len(presets_data.playlists) == 0


def test_wled_presets_data_malformed_entries():
    """Test creating WLED presets data with malformed entries."""
    data = {
        "1": "invalid_preset_data",
        "2": {"n": "Valid Preset", "on": True},
        "101": "invalid_playlist_data",
        "102": {"n": "Valid Playlist", "playlist": {"ps": [1], "dur": [30]}}
    }

    presets_data = WLEDPresetsData.from_json_response(data)

    # Should handle malformed entries gracefully
    assert len(presets_data.presets) == 1  # Only the valid preset
    assert "2" in presets_data.presets
    assert presets_data.presets["2"].name == "Valid Preset"

    assert len(presets_data.playlists) == 1  # Only the valid playlist
    assert "102" in presets_data.playlists
    assert presets_data.playlists["102"].name == "Valid Playlist"


def test_wled_preset_str_representation():
    """Test string representation of WLED preset."""
    preset_data = {
        "n": "Test Preset",
        "on": True,
        "bri": 200,
    }

    preset = WLEDPreset("1", preset_data)

    str_repr = str(preset)
    assert "WLEDPreset" in str_repr
    assert "1" in str_repr
    assert "Test Preset" in str_repr


def test_wled_playlist_str_representation():
    """Test string representation of WLED playlist."""
    playlist_data = {
        "n": "Test Playlist",
        "playlist": {
            "ps": [1, 2, 3],
            "dur": [30, 30, 30]
        }
    }

    playlist = WLEDPlaylist("101", playlist_data)

    str_repr = str(playlist)
    assert "WLEDPlaylist" in str_repr
    assert "101" in str_repr
    assert "Test Playlist" in str_repr