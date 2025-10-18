---
status: resolved
priority: p2
issue_id: "003"
tags: [refactoring, simplification, http-client, wled, reliability]
dependencies: ["001-pending-p1-wled-api-connection-issue.md"]
---

# WLED Connection Logic Simplification

## Problem Statement
The current WLED integration uses complex aiohttp configuration with connection pooling, advanced timeout handling, and sophisticated error management that may be interfering with basic HTTP communication to WLED devices. This complexity could be causing the "Connection closed" errors despite the device being reachable via simple curl commands.

## Findings
- Current implementation uses complex aiohttp ClientSession configuration
- Connection pooling and advanced features may conflict with WLED's simple HTTP server
- Multiple timeout configurations (connection timeout, request timeout, total timeout)
- Complex error handling that may mask underlying connection issues
- Working curl commands use minimal configuration and succeed reliably
- WLED devices have simple HTTP servers that may not handle advanced HTTP client features

## Proposed Solutions

### Option 1: Minimal aiohttp Configuration (Preferred)
- Simplify ClientSession to basic configuration
- Use minimal headers (User-Agent only)
- Set simple timeouts (10s connection, 30s total)
- Disable connection pooling for WLED requests
- Remove SSL/TLS related configuration completely
- Use basic retry logic instead of complex exponential backoff

- **Pros**: Maintains async benefits while reducing complexity, matches working curl behavior
- **Cons**: May lose some performance optimizations
- **Effort**: Medium (2-3 hours)
- **Risk**: Low

### Option 2: urllib Alternative Implementation
- Replace aiohttp with urllib for HTTP requests
- Use synchronous requests in async context with run_in_executor
- Implement simple retry logic
- Match curl command parameters exactly
- Add timeout and error handling

- **Pros**: Proven to work (curl uses similar underlying libraries), simple implementation
- **Cons**: Performance overhead from thread pool, less async-native
- **Effort**: Medium (2-3 hours)
- **Risk**: Medium (performance impact)

### Option 3: Hybrid Approach
- Use simplified aiohttp for primary requests
- Fall back to urllib/curl-equivalent for connection failures
- Implement circuit breaker pattern
- Add connection method detection and adaptation
- Maintain both simple and complex request paths

- **Pros**: Best of both worlds, automatic fallback, robust handling
- **Cons**: Increased complexity, potential for inconsistent behavior
- **Effort**: Large (4-6 hours)
- **Risk**: Medium

## Recommended Action
[Leave blank - will be filled during approval]

## Technical Details
- **Affected Files**: custom_components/wled_jsonapi/api.py
- **Related Components**: WLEDJSONAPIClient class, HTTP request methods
- **Database Changes**: No
- **Target Configuration**: Match working curl: `curl http://192.168.51.201/json`
- **Performance**: Accept minor performance loss for reliability
- **Compatibility**: Must work with WLED v0.15.1 simple HTTP server

## Resources
- Original finding: Triage session identified complex client as potential issue
- Related issues: 001-pending-p1-wled-api-connection-issue.md (primary fix)
- Reference: Working curl command parameters and aiohttp minimal configuration docs
- WLED documentation: Simple HTTP API without advanced features

## Acceptance Criteria
- [ ] aiohttp configuration simplified to minimal working parameters
- [ ] Connection pooling disabled for WLED requests
- [ ] Timeouts simplified to connection + total timeout
- [ ] Headers minimized to essentials (User-Agent only)
- [ ] SSL/TLS configuration completely removed
- [ ] Connection logic matches working curl behavior
- [ ] Error handling simplified but remains informative
- [ ] Tests pass with simplified connection logic
- [ ] Integration successfully connects to WLED device
- [ ] Performance remains acceptable for Home Assistant use

## Work Log

### 2025-10-18 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Identified complex aiohttp configuration as potential root cause
- User confirmed simple curl commands work reliably
- Created as fallback/alternative approach to connection issues
- Categorized as P2 important (improves reliability significantly)
- Estimated effort: Medium (2-3 hours)

**Learnings:**
- Sometimes advanced HTTP client features conflict with simple servers
- WLED devices have basic HTTP servers that don't support advanced features
- Simple, reliable HTTP requests may be preferable to complex optimized ones
- Matching working curl parameters is a good validation approach

## Notes
Source: Triage session on 2025-10-18
Priority: Important - provides reliable alternative connection method
Dependency: Should be implemented alongside or after the primary connection fix
Context: Simplification strategy to ensure basic HTTP communication works