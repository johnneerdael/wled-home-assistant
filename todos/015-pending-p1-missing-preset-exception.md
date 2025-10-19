# TODO: P1 - Fix Missing WLEDPresetNotFoundError Exception Class

**Priority:** P1 (CRITICAL)
**Status:** Pending
**Target Version:** 1.3.3
**Estimated Time:** 30-60 minutes
**Component:** Exception Handling / Platform Integration

## Problem Description

The WLED integration cannot complete device setup because the `WLEDPresetNotFoundError` exception class is missing from the exceptions module. This prevents the integration from loading entirely.

**Error Pattern:**
```
Unexpected error during setup of WLED device at 192.168.51.205: cannot import name 'WLEDPresetNotFoundError' from 'custom_components.wled_jsonapi.exceptions'
```

**Location:** `custom_components/wled_jsonapi/__init__.py:66` - during device setup

## Root Cause Analysis

- Exception class was removed during v1.3.0 simplification but imports weren't cleaned up
- Platform files (likely `select.py` and/or `light.py`) still reference this exception
- Creates complete integration loading failure
- This is a regression from previous fixes

## Solution Approach

**Option 1: Add Missing Exception Class (Recommended)**
1. Add `WLEDPresetNotFoundError` class back to `exceptions.py`
2. Inherit from appropriate base exception (`WLEDPresetError`)
3. Minimal implementation to maintain existing API
4. Ensure proper exception hierarchy

**Implementation Details:**
```python
class WLEDPresetNotFoundError(WLEDPresetError):
    """Raised when a requested preset is not found."""

    def __init__(self, preset_id: str, message: str | None = None) -> None:
        """Initialize preset not found error."""
        super().__init__(message or f"Preset '{preset_id}' not found")
        self.preset_id = preset_id
```

**Alternative Options:**
- **Option 2:** Remove unused exception imports from platform files
- **Option 3:** Replace usage with `WLEDPresetError` base class

## Investigation Required

1. Identify which platform files import `WLEDPresetNotFoundError`
2. Check if the exception is actually used in error handling
3. Determine if removing imports or adding the class is better

## Testing Requirements

- Verify integration loads successfully after fix
- Test device setup and configuration flow
- Ensure no regression in preset-related functionality
- Test with multiple WLED device models

## Impact

**Current Impact:** COMPLETE INTEGRATION SETUP FAILURE
- No new devices can be configured
- Integration cannot be loaded by Home Assistant
- Blocks all users from setting up WLED devices

**Fix Impact:** Restores ability to configure and use WLED integration

## Dependencies

- Review all platform files for exception imports
- Check for any usage of the missing exception
- May need updates to test cases
- Ensure consistency with exception hierarchy

## Notes

This error appeared after the v1.3.2 critical fixes release, suggesting it's a regression from the architectural simplification in v1.3.0. The fact that multiple devices are showing this error indicates it's a systematic issue affecting all setup attempts.

**Devices Affected:** Multiple (192.168.51.205, 204, 212, 201)
**Error Frequency:** Every device setup attempt fails