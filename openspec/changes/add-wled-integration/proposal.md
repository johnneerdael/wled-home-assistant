## Why
Create a robust Home Assistant integration for WLED LED controllers that provides more reliable control than the default integration by avoiding websockets and implementing retry mechanisms for low-power devices.

## What Changes
- Add new WLED JSONAPI integration with mDNS/zeroconf discovery
- Implement manual device addition via config flow
- Create light entities with on/off, brightness, and preset/playlist controls
- Add automatic retry mechanisms with exponential backoff (up to 5 retries)
- Implement 1-minute polling for device status monitoring
- Create HACS-compatible repository structure

## Impact
- Affected specs: None (new integration)
- Affected code: New custom_components/wled_jsonapi/ directory structure
- Dependencies: aiohttp, zeroconf, voluptuous