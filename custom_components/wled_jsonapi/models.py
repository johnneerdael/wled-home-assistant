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


@dataclass
class WLEDEssentialState:
    """Streamlined data model containing only essential WLED state parameters."""

    # Basic state
    on: bool = False
    brightness: Optional[int] = None

    # Preset and playlist information
    preset_id: Optional[int] = None
    preset_name: Optional[str] = None
    playlist_id: Optional[int] = None
    playlist_name: Optional[str] = None

    # Raw essential data for fallback
    raw_state: Optional[Dict[str, Any]] = None

    @classmethod
    def from_state_response(cls, response_data: Dict[str, Any]) -> "WLEDEssentialState":
        """Create WLEDEssentialState from state response data with targeted extraction."""
        essential = cls()
        essential.raw_state = response_data.copy() if response_data else {}

        # Extract only essential parameters
        if isinstance(response_data, dict):
            # Extract on/off state
            if 'on' in response_data:
                essential.on = bool(response_data['on'])

            # Extract brightness
            if 'bri' in response_data:
                essential.brightness = int(response_data['bri']) if response_data['bri'] is not None else None

            # Extract preset ID
            if 'ps' in response_data:
                essential.preset_id = int(response_data['ps']) if response_data['ps'] is not None else None

            # Extract playlist ID
            if 'pl' in response_data:
                essential.playlist_id = int(response_data['pl']) if response_data['pl'] is not None else None

        return essential

    def update_preset_info(self, preset_id: int, preset_name: str) -> None:
        """Update preset information."""
        self.preset_id = preset_id
        self.preset_name = preset_name

    def update_playlist_info(self, playlist_id: int, playlist_name: str) -> None:
        """Update playlist information."""
        self.playlist_id = playlist_id
        self.playlist_name = playlist_name

    def to_state_dict(self) -> Dict[str, Any]:
        """Convert to minimal state dictionary for Home Assistant."""
        state = {
            "on": self.on,
        }

        if self.brightness is not None:
            state["brightness"] = self.brightness

        if self.preset_id is not None:
            state["preset_id"] = self.preset_id
            if self.preset_name:
                state["preset_name"] = self.preset_name

        if self.playlist_id is not None:
            state["playlist_id"] = self.playlist_id
            if self.playlist_name:
                state["playlist_name"] = self.playlist_name

        return state

    def is_valid(self) -> bool:
        """Check if the essential state has valid data."""
        return self.raw_state is not None

    def has_minimal_state(self) -> bool:
        """Check if we have at least basic on/off state."""
        return self.raw_state is not None and isinstance(self.raw_state, dict)


@dataclass
class WLEDEssentialPreset:
    """Simplified preset model containing only essential information."""

    id: int
    name: str

    @classmethod
    def from_preset_response(cls, preset_id: str, preset_data: Dict[str, Any]) -> "WLEDEssentialPreset":
        """Create WLEDEssentialPreset from preset response data."""
        # Extract the display name from the "n" field, fallback to ID
        name = preset_data.get("n", f"Preset {preset_id}")

        return cls(
            id=int(preset_id),
            name=name
        )


@dataclass
class WLEDEssentialPlaylist:
    """Simplified playlist model containing only essential information."""

    id: int
    name: str

    @classmethod
    def from_playlist_response(cls, playlist_id: str, playlist_data: Dict[str, Any]) -> "WLEDEssentialPlaylist":
        """Create WLEDEssentialPlaylist from playlist response data."""
        # Extract the display name from the "n" field, fallback to ID
        name = playlist_data.get("n", f"Playlist {playlist_id}")

        return cls(
            id=int(playlist_id),
            name=name
        )


@dataclass
class WLEDEssentialPresetsData:
    """Simplified container for essential presets and playlists data."""

    presets: Dict[int, WLEDEssentialPreset]
    playlists: Dict[int, WLEDEssentialPlaylist]

    @classmethod
    def from_presets_response(cls, response_data: Dict[str, Any]) -> "WLEDEssentialPresetsData":
        """Create WLEDEssentialPresetsData from presets response with targeted extraction."""
        presets = {}
        playlists = {}

        if not isinstance(response_data, dict):
            return cls(presets={}, playlists={})

        # Only process the essential structure, skip complex state data
        for key, value in response_data.items():
            # Skip non-numeric keys
            if not key.isdigit():
                continue

            # Check if this is a playlist (has "playlist" field)
            if isinstance(value, dict) and "playlist" in value:
                try:
                    playlist = WLEDEssentialPlaylist.from_playlist_response(key, value)
                    playlists[playlist.id] = playlist
                except (ValueError, KeyError):
                    # Skip invalid playlist entries for reliability
                    continue
            elif isinstance(value, dict):
                # This is a regular preset
                try:
                    preset = WLEDEssentialPreset.from_preset_response(key, value)
                    presets[preset.id] = preset
                except (ValueError, KeyError):
                    # Skip invalid preset entries for reliability
                    continue

        return cls(
            presets=presets,
            playlists=playlists
        )

    def get_preset_name(self, preset_id: int) -> Optional[str]:
        """Get preset name by ID."""
        preset = self.presets.get(preset_id)
        return preset.name if preset else None

    def get_playlist_name(self, playlist_id: int) -> Optional[str]:
        """Get playlist name by ID."""
        playlist = self.playlists.get(playlist_id)
        return playlist.name if playlist else None

    def get_all_preset_names(self) -> Dict[int, str]:
        """Get a mapping of all preset IDs to their names."""
        return {preset.id: preset.name for preset in self.presets.values()}

    def get_all_playlist_names(self) -> Dict[int, str]:
        """Get a mapping of all playlist IDs to their names."""
        return {playlist.id: playlist.name for playlist in self.playlists.values()}

    def has_presets(self) -> bool:
        """Check if any presets are available."""
        return bool(self.presets)

    def has_playlists(self) -> bool:
        """Check if any playlists are available."""
        return bool(self.playlists)