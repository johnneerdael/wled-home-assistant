---
status: resolved
priority: p1
issue_id: "001"
tags: [bug, network, api, wled, connection]
dependencies: []
---

# WLED API Client Connection Handling Issue

## Problem Statement
The WLED integration fails to connect to the WLED device despite successful curl commands from the same Docker container. The error shows "Connection closed" at api.py:424, indicating an issue with how the HTTP client is configured or handling connections, not network reachability.

## Findings
- Docker container can successfully curl WLED endpoints (confirmed working)
- Integration API client fails with "Connection closed" error
- Issue is in the HTTP client implementation, not network infrastructure
- User removed network bond, confirming basic connectivity works
- Location: custom_components/wled_jsonapi/api.py:424
- Error: "Network error connecting to WLED device at 192.168.51.201: Connection closed"
- Target device WLED v0.15.1 at 192.168.51.201 confirmed reachable via HTTP
- Working endpoints: /json and /presets.json both respond correctly to curl

## Proposed Solutions

### Option 1: Fix HTTP Client Configuration (Preferred)
- Review aiohttp ClientSession configuration in api.py
- Ensure proper timeout settings (connection vs request timeouts)
- Add appropriate headers for WLED device compatibility
- Verify connection pooling settings aren't causing premature closures
- Remove any SSL-related code that might interfere with HTTP connections

- **Pros**: Fixes root cause, maintains current architecture
- **Cons**: Requires detailed investigation of aiohttp configuration
- **Effort**: Medium (2-4 hours)
- **Risk**: Low

### Option 2: Add Connection Diagnostics
- Implement detailed connection logging to identify exact failure point
- Add connection state validation before requests
- Provide clearer error messages for troubleshooting
- Add connection retry logic specific to "Connection closed" errors

- **Pros**: Better debugging capabilities, improved user experience
- **Cons**: Doesn't fix underlying issue, adds complexity
- **Effort**: Medium (2-3 hours)
- **Risk**: Low

### Option 3: Simplify Connection Logic
- Replace complex aiohttp handling with basic HTTP requests similar to curl
- Use minimal configuration that matches working curl parameters
- Ensure compatibility with WLED's simple HTTP server
- Remove connection pooling that may cause issues

- **Pros**: Simple, reliable solution similar to working curl
- **Cons**: May lose some advanced HTTP client features
- **Effort**: Small (1-2 hours)
- **Risk**: Low

## Recommended Action
[Leave blank - will be filled during approval]

## Technical Details
- **Affected Files**: custom_components/wled_jsonapi/api.py
- **Related Components**: WLEDJSONAPIClient class, _execute_http_request method
- **Database Changes**: No
- **Network Protocol**: HTTP (non-SSL as required by WLED devices)
- **Device Details**: WLED v0.15.1 "DJ Booth" at 192.168.51.201

## Resources
- Original finding: User report during triage session
- Related issues: Network bond issue resolved, now isolated to API client
- Working reference: curl http://192.168.51.201/json works perfectly from container

## Acceptance Criteria
- [ ] Integration successfully connects to WLED device
- [ ] API client can fetch /json endpoint without "Connection closed" errors
- [ ] API client can fetch /presets.json endpoint
- [ ] Connection is stable and reliable over multiple requests
- [ ] Error handling provides meaningful diagnostics
- [ ] Tests pass for connection functionality

## Work Log

### 2025-10-18 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during network connectivity triage session
- User confirmed Docker networking works after removing bond interface
- Categorized as P1 critical (prevents integration from working)
- Estimated effort: Medium (2-4 hours)

**Learnings:**
- Network infrastructure is not the root cause
- Problem is specifically in aiohttp client configuration
- WLED devices require explicit HTTP (non-SSL) handling
- Simple curl commands work, indicating device is responsive

## Notes
Source: Triage session on 2025-10-18
Priority: Critical - integration completely non-functional
Context: User has confirmed network connectivity works, issue is in code