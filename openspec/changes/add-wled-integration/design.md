## Context
WLED devices run on low-power ESP8266/ESP32 microcontrollers and can be slow to respond to API calls. The default Home Assistant integration relies on websockets which can be unreliable. This WLED JSONAPI integration will use the JSON API with robust retry mechanisms to provide more stable control.

## Goals / Non-Goals
- Goals:
  - Reliable control via JSON API with automatic retries
  - Device discovery via mDNS/zeroconf
  - Manual device addition fallback
  - On/off, brightness, preset, and playlist controls
  - 1-minute status polling
- Non-Goals:
  - Real-time LED control (avoid overwhelming devices)
  - Advanced segment controls (focus on basic light functionality)
  - Audio reactive features (requires additional hardware)

## Technical Architecture

### Core Components
1. **WLEDJSONAPIClient** - HTTP client with retry logic for JSON API communication
2. **WLEDJSONAPIDataCoordinator** - DataUpdateCoordinator for centralized state management
3. **WLEDJSONAPIConfigFlow** - Config flow for device discovery and manual setup
4. **WLEDJSONAPILightEntity** - Light entity with basic controls
5. **WLEDJSONAPIDevice** - Device representation with connection management

### API Communication Pattern
```
Home Assistant → WLEDJSONAPILightEntity → WLEDJSONAPIDataCoordinator → WLEDJSONAPIClient → WLED Device
```

### Retry Mechanism Details
- **Initial delay**: 1 second
- **Backoff multiplier**: 2x (1s, 2s, 4s, 8s, 16s)
- **Max retries**: 5 attempts
- **Timeout per request**: 10 seconds
- **Connection timeout**: 5 seconds

### Data Flow
1. Coordinator polls device every 60 seconds via GET /json
2. Entity commands sent via POST /json/state
3. Failed commands queued for retry with exponential backoff
4. Device availability tracked based on successful responses

### State Management
- **Device state**: Cached in coordinator, updated on successful polls
- **Command queue**: Pending commands with retry counts
- **Availability**: Marked unavailable after 3 consecutive failed polls
- **Error handling**: Connection errors logged, device marked unavailable

## Decisions
- Decision: Use DataUpdateCoordinator for centralized data fetching
  - Alternatives considered: Direct entity polling, websocket connection
  - Rationale: Coordinator pattern provides built-in retry logic and status management
- Decision: Implement exponential backoff for retries (max 5 attempts)
  - Alternatives considered: Fixed delay, linear backoff
  - Rationale: Exponential backoff prevents overwhelming slow devices
- Decision: Use mDNS/zeroconf for discovery with manual fallback
  - Alternatives considered: Network scanning, UPnP discovery
  - Rationale: WLED devices broadcast via mDNS, provides reliable discovery
- Decision: Separate command and data channels
  - Alternatives considered: Single HTTP client for all operations
  - Rationale: Allows independent retry logic for commands vs status polling

## Risks / Trade-offs
- Risk: WLED devices may become unresponsive to rapid API calls
  - Mitigation: Implement rate limiting and exponential backoff
- Trade-off: 1-minute polling vs real-time updates
  - Rationale: Reduces load on low-power devices while maintaining reasonable responsiveness
- Risk: Network connectivity issues may cause command failures
  - Mitigation: Robust retry mechanisms with connection recovery
- Risk: Memory usage from command queue
  - Mitigation: Limit queue size, drop oldest commands on overflow

## Migration Plan
- No migration needed (new integration)
- Users can add alongside existing WLED integration for comparison
- Eventually replace default integration if proven more reliable

## Open Questions
- How to handle different WLED versions with varying API capabilities?
- Should we implement preset synchronization (read/write) or read-only?
- How to handle device name changes after initial setup?
- What timeout values are optimal for different network conditions?