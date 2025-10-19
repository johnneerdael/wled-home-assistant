---
status: completed
priority: p1
issue_id: "020"
tags: [feature, select-entity, palettes, configuration, ui-improvement]
dependencies: []
---

# TODO: P1 - Add Palette Select Entity Using Home Assistant Select Patterns

## Problem Statement

The WLED integration currently only exposes light control functionality but doesn't provide access to color palettes, which are a core feature of WLED devices. The original WLED app shows a dedicated palette selection interface, and this functionality should be available in Home Assistant as a select entity for proper user experience.

**Missing Feature:** Users cannot select from WLED's extensive palette library (50+ color palettes) via Home Assistant UI.

## Root Cause Analysis

**Current Implementation Gaps:**

1. **No Palette Platform:** Integration only defines `Platform.LIGHT` and `Platform.SELECT` (for presets), missing palette select capability
2. **Missing Palette Entity:** No select entity implementation for palette selection
3. **Incomplete Data Exposure:** Palettes data from `/json` endpoint not exposed via Home Assistant entities
4. **Limited UI Controls:** Home Assistant users can't access one of WLED's main features

**WLED JSON API Palette Structure (from official docs):**
- `/json` → `{state, info, effects, palettes}` includes `palettes` array
- Each palette has an ID (0-50+) and name (e.g., "Default", "Rainbow", "Fire", "Ocean")
- Current segment state includes `pal` field indicating active palette ID
- Palettes are fundamental to WLED's color system

**User Experience Gap:**
1. Original WLED app has dedicated palette selector
2. Home Assistant integration should provide equivalent functionality
3. Palette selection is configuration-style control (select entity pattern)
4. Users expect all WLED features available in HA interface

## Proposed Solutions

### Option 1: Add Palette Select Entity (Recommended)
- **Fix:** Create new `select.py` platform file for palette selection
- **Implementation:** Follow Home Assistant Select entity patterns with proper naming
- **Benefit:** Native HA select entity with full UI integration
- **Effort:** Medium (2-3 hours)
- **Risk:** Low

### Option 2: Extend Light Entity with Palette Control
- **Fix:** Add palette control as additional feature in existing light entity
- **Implementation:** Add palette selection as light entity attribute or method
- **Benefit:** Keeps all controls in single entity
- **Effort:** Medium (2 hours)
- **Risk:** Medium - deviates from standard HA patterns

## Recommended Action

**Primary Fix:** Implement dedicated palette select entity following Home Assistant Select platform patterns with proper device naming and configuration entity behavior.

## Technical Details

**Affected Files:**
- `custom_components/wled_jsonapi/__init__.py` - Add `Platform.SELECT` to platforms list
- `custom_components/wled_jsonapi/select.py` - New file for palette select entity
- `custom_components/wled_jsonapi/const.py` - Add palette-related constants
- `custom_components/wled_jsonapi/coordinator.py` - Ensure palette data available

**New Palette Select Entity Implementation:**
```python
# select.py
class WLEDPaletteSelect(CoordinatorEntity, SelectEntity):
    """Representation of a WLED palette selection."""

    _attr_has_entity_name = True
    _attr_name = "Palette"
    _attr_translation_key = "palette"

    def __init__(self, coordinator: WLEDJSONAPIDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_palette"
        self._segment_ids = self._extract_segment_ids()

    def _extract_segment_ids(self) -> List[int]:
        """Extract all segment IDs from the current state."""
        state = self.coordinator.data.get("state", {})
        segments = state.get("seg", [])
        return [seg.get("id") for seg in segments if seg.get("id") is not None]

    @property
    def current_option(self) -> Optional[str]:
        """Return the current palette (from first segment or main segment)."""
        state = self.coordinator.data.get("state", {})
        segments = state.get("seg", [])

        # Try main segment first (if specified)
        mainseg = state.get("mainseg", 0)
        for seg in segments:
            if seg.get("id") == mainseg:
                palette_id = seg.get(KEY_PALETTE)
                if palette_id is not None:
                    palettes = self.coordinator.data.get("palettes", [])
                    if 0 <= palette_id < len(palettes):
                        return palettes[palette_id]

        # Fallback to first segment
        if segments:
            palette_id = segments[0].get(KEY_PALETTE)
            if palette_id is not None:
                palettes = self.coordinator.data.get("palettes", [])
                if 0 <= palette_id < len(palettes):
                    return palettes[palette_id]

        return None

    @property
    def options(self) -> List[str]:
        """Return the list of available palettes."""
        return self.coordinator.data.get("palettes", [])

    async def async_select_option(self, option: str) -> None:
        """Change the selected palette for all segments."""
        palettes = self.coordinator.data.get("palettes", [])
        if option in palettes:
            palette_id = palettes.index(option)
            await self.coordinator.async_set_palette_for_all_segments(palette_id)
```

**Coordinator Method Addition:**
```python
# coordinator.py
async def async_set_palette_for_all_segments(self, palette_id: int) -> None:
    """Set the palette on all segments of the WLED device."""
    state = self.data.get("state", {})
    segments = state.get("seg", [])

    if not segments:
        return

    # Create segment-specific palette commands for all segments
    segment_commands = []
    for seg in segments:
        seg_id = seg.get("id")
        if seg_id is not None:
            segment_commands.append({"id": seg_id, "pal": palette_id})

    command = {"seg": segment_commands}
    await self._async_send_command(command)
```

**Integration Setup Changes:**
```python
# __init__.py
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SELECT]

# select.py setup
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities([WLEDPaletteSelect(coordinator, entry)])
```

**Constants Addition:**
```python
# const.py
KEY_PALETTE = "pal"
ATTR_PALETTE = "palette"
```

## Implementation Strategy

**Entity Naming Strategy:**
- Use `_attr_has_entity_name = True` for proper device naming
- Entity will appear as "[Device Name] Palette" in Home Assistant
- Follow HA naming conventions with translation key support

**Data Access Pattern:**
- Palette data available via `coordinator.data.get("palettes", [])` from `/json` endpoint
- Current palette from each segment: `state.seg[i].pal` (multiple segments possible)
- Main segment ID from `state.mainseg` for determining current palette
- Need to extract and store all segment IDs for comprehensive palette control
- Leverage existing coordinator data fetching (no additional API calls needed)

**Command Integration:**
- Palette changes sent via existing `/json` command endpoint
- Use segment-specific palette control: `{"seg": [{"id": 0, "pal": 18}, {"id": 1, "pal": 18}]}`
- Apply selected palette to ALL segments for consistent user experience
- Integrate with existing error handling and retry logic

## Validation Requirements

**WLED JSON API Compliance:**
- Verify palette IDs match WLED documentation (0-70+ range based on real device)
- Confirm command format: `{"seg": [{"id": seg_id, "pal": palette_id}]}`
- Validate palette names array structure from `/json` response
- Test palette changes affect all segments consistently
- Verify main segment detection works correctly

**Home Assistant Select Entity Compliance:**
- Follow HA Select entity patterns from developer documentation
- Proper implementation of `current_option`, `options`, `async_select_option`
- Use translation keys for proper localization support
- Implement proper device info and unique ID patterns

**Integration Testing:**
- Test palette selection via Home Assistant UI
- Verify palette changes reflect on WLED device
- Confirm state synchronization after palette changes
- Test error handling for invalid palette selections

## Acceptance Criteria

- [ ] Palette select entity created following Home Assistant Select patterns
- [ ] Entity named as "[Device Name] Palette" using device name from info
- [ ] All available palettes (70+) exposed as selectable options
- [ ] Current palette properly reflected in entity state
- [ ] Palette selection changes WLED device in real-time
- [ ] Proper error handling for invalid palette selections
- [ ] Entity uses `_attr_has_entity_name = True` for proper naming
- [ ] Translation key support for localization
- [ ] Integration with existing coordinator data (no extra API calls)
- [ ] Device registry integration with proper unique IDs
- [ ] State synchronization after palette changes
- [ ] No regression in existing light and preset functionality

## Work Log

### 2025-10-19 - Palette Select Entity Analysis
**By:** Claude Code Review System with Context7 MCP Documentation Analysis
**Actions:**
- Analyzed Home Assistant Select entity patterns using Context7 MCP developer docs
- Reviewed WLED JSON API documentation for palette structure and control methods
- Identified missing palette functionality compared to original WLED app interface
- Created as P1 important (adds core WLED feature to Home Assistant integration)
- Estimated effort: Medium (2-3 hours for full implementation)

**Learnings:**
- Home Assistant Select entities follow specific patterns with `current_option`, `options`, `async_select_option`
- Entity naming uses `_attr_has_entity_name = True` for device-based naming
- Translation keys support proper localization: `_attr_translation_key = "palette"`
- WLED palettes are controlled via segment-specific commands: `{"seg": [{"id": seg_id, "pal": palette_id}]}`
- Palette data available in existing coordinator data from `/json` endpoint (71 palettes on real device)
- Each WLED device can have multiple segments, each with independent palette settings
- For consistent user experience, palette selection should apply to ALL segments
- Select entities are ideal for configuration-style controls like palette selection
- Proper device integration requires unique IDs and device registry support
- **Context7 MCP Usage:** Essential for accessing official Home Assistant development documentation
- **Entity Patterns:** Select entities perfect for exposing configuration options with discrete choices
- **WLED API Integration:** Palette control follows same command patterns as other WLED features
- **UI/UX Consistency:** Home Assistant users expect native select entities for option selection

## Notes

Source: WLED JSON API documentation + Home Assistant Select entity developer documentation via Context7 MCP
Priority: Important - adds core WLED feature missing from Home Assistant integration
User Impact: High - provides access to 70+ color palettes for enhanced lighting control
Discovery Method: Feature gap analysis comparing original WLED app vs Home Assistant integration
Recommendation: Implement immediately to provide feature parity with original WLED application

**Real WLED Palette Integration:**
- WLED devices typically have 70+ built-in color palettes (71 on real device example)
- Palettes range from simple color gradients to complex animated patterns
- Each WLED device can have multiple segments with independent palette settings
- For consistent user experience, palette selection should apply to ALL segments
- Palette selection is fundamental to WLED's advanced lighting capabilities
- Home Assistant users expect access to all device features via native entities
- Select entity pattern provides optimal user experience for palette selection

**Validation Requirements:**
- Cross-reference palette IDs with WLED official documentation
- Ensure palette names match device response exactly
- Test palette changes reflect correctly on physical WLED devices
- Verify Home Assistant UI displays palette options correctly
- Confirm state synchronization between HA and WLED device