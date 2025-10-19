---
status: pending
priority: p1
issue_id: "019"
tags: [bug, critical, effects, data-retrieval, coordinator, api-endpoint]
dependencies: []
---

# TODO: P1 - Fix Missing Effects Data in WLED Coordinator

## Problem Statement

The WLED integration is not retrieving and storing effects data from the WLED device because the coordinator is only calling the `/json/state` endpoint, which doesn't include the effects array. According to the official WLED JSON API documentation, effects are only available in the full `/json` response.

**Critical Issue:** Light entities cannot show or control effects because effects data is missing from coordinator.data.

## Root Cause Analysis

**API Endpoint Misunderstanding:**
- Current: Coordinator calls `get_essential_state()` → `/json/state` → `{state}` only
- Required: Effects are only in full `/json` response → `{state, info, effects, palettes}`

**Data Flow Issue:**
1. Coordinator `_async_update_data()` calls `client.get_essential_state()`
2. `get_essential_state()` makes GET request to `/json/state`
3. Response only contains state data (on, bri, ps, pl) - NO effects
4. Light entities call `self.coordinator.data.get("effects", [])` → returns empty array
5. Effects control functionality completely broken

**WLED JSON API Structure (from official docs):**
- `/json` → Returns `{state, info, effects, palettes}` ✅ (includes effects)
- `/json/state` → Returns only `{state}` ❌ (no effects)
- `/json/info` → Returns only `{info}` ❌ (no effects)

## Impact Assessment

**User Experience:**
- Light entities show no effects in Home Assistant UI
- Effects selection controls are empty/non-functional
- Users cannot control WLED effects via Home Assistant
- Integration appears incomplete despite working on/off controls

**Technical Impact:**
- Complete failure of effects functionality
- Light entity effect methods return None or empty arrays
- Cannot leverage WLED's extensive effect library (187+ effects)

## Proposed Solutions

### Option 1: Optimize API Calls - Use Single /json Endpoint (Recommended)
- **Fix:** Modify coordinator to use `get_full_state()` → `/json` for all state data
- **Implementation:** Change `_async_update_data()` to call single endpoint containing everything
- **Benefit:** Single API call gets {state, info, effects, palettes} - optimal performance
- **Effort:** Small (30 minutes)
- **Risk:** Low

### Option 2: Keep Dual-Call Pattern (Current with Fix)
- **Fix:** Keep existing `/presets.json` call, replace `/json/state` with `/json`
- **Implementation:** Change `get_essential_state()` to call `/json` instead of `/json/state`
- **Benefit:** Minimal change to existing architecture
- **Effort:** Small (15 minutes)
- **Risk:** Low

## Recommended Action

**Primary Fix:** Optimize to single `/json` API call for all state data while maintaining separate `/presets.json` call for preset dropdown data.

## Implementation Strategy

**Optimal API Call Pattern:**
1. **Main Data:** `GET /json` → `{state, info, effects, palettes}` (every minute polling)
2. **Preset Data:** `GET /presets.json` → `{presets, playlists}` (hourly refresh)

**Benefits:**
- Single API call for all operational data (state, effects, palettes)
- Effects array (187+ effects) available for light entity UI
- Preset data only refreshed when needed for dropdowns
- Optimal network performance and device load

## Technical Details

**Affected Files:**
- `custom_components/wled_jsonapi/coordinator.py` - `_async_update_data()` method
- Possibly `custom_components/wled_jsonapi/api.py` - verify `get_full_state()` implementation

**Current Implementation:**
```python
# coordinator.py line 168
essential_state = await self.client.get_essential_state()
data = essential_state.to_state_dict()
```

**Required Change:**
```python
# coordinator.py line 168 - Replace essential state with full state
full_state = await self.client.get_full_state()
data = full_state  # Use complete state dict with effects, palettes, info
```

**Optimized API Call Pattern:**
- **Main Polling (every minute):** `GET /json` → `{state, info, effects, palettes}`
- **Preset Refresh (hourly):** `GET /presets.json` → `{presets, playlists}` (already implemented)

**Verification Required:**
- Ensure `get_full_state()` returns effects array properly from `/json` endpoint
- Verify light entity can access effects via `coordinator.data.get("effects", [])`
- Test effects selection and control functionality in Home Assistant UI
- Confirm no regression in existing state/brightness/preset functionality
- Validate single API call performance (no multiple endpoint calls needed)

## WLED Effects Example (from real device response):

```json
{
  "effects": [
    "Solid", "Blink", "Breathe", "Wipe", "Wipe Random",
    "Random Colors", "Sweep", "Dynamic", "Colorloop", "Rainbow",
    "Scan", "Scan Dual", "Fade", "Theater", "Theater Rainbow",
    // ... 187 total effects
  ]
}
```

## Acceptance Criteria

- [ ] Coordinator uses single `GET /json` API call for all operational data
- [ ] Effects array (187+ effects) available via coordinator.data.get("effects", [])
- [ ] State data (on, bri, transition) continues to work correctly
- [ ] Info data (name, version, led count) available for device info
- [ ] Palettes data available for future palette control features
- [ ] Light entities show effects in Home Assistant UI with proper names
- [ ] Effects selection and control work properly via effect IDs
- [ ] Separate `/presets.json` call continues for preset dropdown population
- [ ] No regression in existing on/off/brightness/preset functionality
- [ ] Optimized performance: single API call for main data, no redundant endpoint calls

## Work Log

### 2025-10-19 - Effects Data Missing Discovery
**By:** Claude Code Review System with Jina AI MCP Documentation Analysis
**Actions:**
- Analyzed WLED JSON API official documentation via Jina AI MCP
- Identified that effects are only available in `/json` endpoint, not `/json/state`
- Found coordinator using wrong endpoint for data retrieval
- Traced data flow from API client to light entity effects methods
- Created as P1 critical (effects functionality completely broken)
- Estimated effort: Small to Medium (30 minutes to 2 hours depending on approach)

**Learnings:**
- WLED JSON API has different endpoints with different data contents
- Full `/json` response includes {state, info, effects, palettes} - optimal single call
- `/json/state` only includes {state} - no effects or palettes
- Effects are essential for complete WLED functionality (187+ effects available)
- API endpoint selection is critical for feature completeness
- **Performance Optimization:** Single `/json` call eliminates need for multiple endpoints
- **Data Architecture:** {state, info, effects, palettes} covers all main functionality
- **Preset Separation:** `/presets.json` correctly separated for dropdown population only

## Notes

Source: WLED JSON API documentation analysis via Jina AI MCP
Priority: Critical - effects functionality completely non-functional
User Impact: High - major WLED feature unavailable in Home Assistant
Discovery Method: Documentation analysis + code flow tracing
Recommendation: Fix immediately to restore complete WLED functionality

**Real WLED Response Analysis:**
- Device shows 187 effects available in full `/json` response
- Effects array contains names like "Solid", "Blink", "Breathe", "Rainbow", etc.
- Light entity effects methods expect effects array in coordinator.data
- Current implementation returns empty array, breaking all effects functionality