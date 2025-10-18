"""Data models for WLED presets and playlists."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class WLEDPreset:
    """Represents a WLED preset with its complete state and metadata."""

    id: int
    name: str
    state: Dict[str, Any]

    @classmethod
    def from_dict(cls, preset_id: str, data: Dict[str, Any]) -> "WLEDPreset":
        """Create a WLEDPreset from API response data."""
        # Extract the display name from the "n" field, fallback to ID
        name = data.get("n", f"Preset {preset_id}")

        # Create a copy of the data as the state
        state = data.copy()

        return cls(
            id=int(preset_id),
            name=name,
            state=state
        )


@dataclass
class WLEDPlaylist:
    """Represents a WLED playlist with preset sequences and settings."""

    id: int
    name: str
    presets: List[int]
    durations: List[int]
    transitions: List[int]
    repeat: int
    shuffle: bool

    @classmethod
    def from_dict(cls, playlist_id: str, data: Dict[str, Any]) -> "WLEDPlaylist":
        """Create a WLEDPlaylist from API response data."""
        # Extract the display name from the "n" field, fallback to ID
        name = data.get("n", f"Playlist {playlist_id}")

        # Extract playlist configuration
        playlist_data = data.get("playlist", {})

        # Extract preset IDs, durations, and transitions
        presets = playlist_data.get("ps", [])
        durations = playlist_data.get("dur", [])
        transitions = playlist_data.get("transition", [])

        # Extract repeat and shuffle settings
        repeat = playlist_data.get("repeat", 0)
        shuffle = playlist_data.get("shuffle", False)

        return cls(
            id=int(playlist_id),
            name=name,
            presets=presets,
            durations=durations,
            transitions=transitions,
            repeat=repeat,
            shuffle=shuffle
        )


@dataclass
class WLEDPresetsData:
    """Container for all WLED presets and playlists data."""

    presets: Dict[int, WLEDPreset]
    playlists: Dict[int, WLEDPlaylist]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WLEDPresetsData":
        """Create WLEDPresetsData from API response data."""
        presets = {}
        playlists = {}

        for key, value in data.items():
            # Skip non-numeric keys (like "0" which is often empty)
            if not key.isdigit():
                continue

            # Check if this is a playlist (has "playlist" field)
            if "playlist" in value:
                try:
                    playlist = WLEDPlaylist.from_dict(key, value)
                    playlists[playlist.id] = playlist
                except (ValueError, KeyError) as err:
                    # Skip invalid playlist entries
                    continue
            else:
                # This is a regular preset
                try:
                    preset = WLEDPreset.from_dict(key, value)
                    presets[preset.id] = preset
                except (ValueError, KeyError) as err:
                    # Skip invalid preset entries
                    continue

        return cls(
            presets=presets,
            playlists=playlists
        )

    def get_preset_by_id(self, preset_id: int) -> Optional[WLEDPreset]:
        """Get a preset by its ID."""
        return self.presets.get(preset_id)

    def get_playlist_by_id(self, playlist_id: int) -> Optional[WLEDPlaylist]:
        """Get a playlist by its ID."""
        return self.playlists.get(playlist_id)

    def get_all_preset_names(self) -> Dict[int, str]:
        """Get a mapping of all preset IDs to their names."""
        return {preset.id: preset.name for preset in self.presets.values()}

    def get_all_playlist_names(self) -> Dict[int, str]:
        """Get a mapping of all playlist IDs to their names."""
        return {playlist.id: playlist.name for playlist in self.playlists.values()}