# WLED Connection Diagnostics Implementation Summary

## Overview
This implementation adds comprehensive connection diagnostics to the WLED integration to prevent future debugging issues and provide users with detailed insight into connection problems.

## Key Features Implemented

### 1. New Specific Exception Types (exceptions.py)
- **WLEDDNSResolutionError**: DNS resolution failures with specific troubleshooting steps
- **WLEDConnectionTimeoutError**: Connection timeouts with stage identification (connect/read/total)
- **WLEDConnectionRefusedError**: Active connection refusals with port information
- **WLEDConnectionResetError**: Unexpected connection resets with stage context
- **WLEDSSLError**: SSL/TLS related errors (for completeness)
- **WLEDHTTPError**: HTTP protocol errors with status codes and headers
- **WLEDSessionError**: aiohttp session management issues
- **WLEDConnectionStalledError**: Stalled/hanging connections with transfer metrics

Each exception includes:
- Detailed error messages with host information
- Specific troubleshooting hints for users
- Context information (timeout stage, port, etc.)

### 2. Connection Diagnostics Manager (api.py)
- **WLEDConnectionDiagnosticsManager**: Manages connection diagnostics and timing
- **WLEDConnectionDiagnostics**: Stores diagnostic information and provides analysis
- **Context manager for timing**: Comprehensive request lifecycle timing
- **Performance metrics**: Automatic calculation of timing breakdowns and slowest steps
- **Error history tracking**: Pattern analysis for repeated issues
- **Troubleshooting summaries**: Automated generation of user-friendly summaries

### 3. Enhanced HTTP Request Processing
- **Session state validation**: Checks session status before requests
- **Detailed timing breakdown**: Tracks every stage of request lifecycle
- **Connection lifecycle logging**: DEBUG level logging for connection states
- **Network information logging**: Captures request metadata for debugging
- **Error categorization**: Maps aiohttp errors to specific WLED exceptions

### 4. Debug Mode Support
- **Debug mode toggle**: `client.set_debug_mode(True/False)`
- **Verbose logging**: Detailed connection tracing when enabled
- **Performance analysis**: Enhanced timing information in debug mode
- **Troubleshooting hints**: Detailed guidance for connection issues

### 5. Session Management Improvements
- **Lazy session initialization**: Creates sessions only when needed
- **Session diagnostics**: Logs session configuration and state
- **Compatibility fixes**: Handles different aiohttp versions gracefully

## Implementation Details

### Files Modified
1. **custom_components/wled_jsonapi/exceptions.py**
   - Added 8 new specific exception types
   - Added WLEDConnectionDiagnostics class
   - Enhanced with troubleshooting hints and context information

2. **custom_components/wled_jsonapi/api.py**
   - Added WLEDConnectionDiagnosticsManager class
   - Enhanced WLEDJSONAPIClient with debug mode support
   - Completely rewrote _execute_http_request method
   - Added comprehensive error handling and diagnostics
   - Improved session management with lazy initialization

3. **tests/test_api.py**
   - Added 20+ new test cases for diagnostic functionality
   - Tests for all new exception types
   - Tests for timing diagnostics and error history
   - Tests for debug mode functionality

### Key Methods Added
- `set_debug_mode(bool)`: Enable/disable verbose diagnostics
- `get_connection_diagnostics()`: Get latest diagnostic data
- `get_diagnostics_summary()`: Get user-friendly summary
- `_ensure_session()`: Lazy session initialization
- `_execute_get_request()`: Enhanced GET request with diagnostics
- `_execute_post_request()`: Enhanced POST request with diagnostics
- `_handle_connector_error()`: Specific error type mapping

### Logging Levels
- **INFO**: Basic connection events and debug mode changes
- **DEBUG**: Detailed connection lifecycle, timing breakdowns, state changes
- **ERROR**: Specific error messages with troubleshooting hints

## Performance Impact
- **Minimal overhead**: Diagnostics are lightweight and don't impact normal operation
- **Optional debug mode**: Verbose logging only when explicitly enabled
- **Memory management**: Limited to last 10 diagnostic entries to prevent memory growth
- **Lazy evaluation**: Session creation only when needed

## Troubleshooting Features

### Error-Specific Guidance
Each error type provides specific troubleshooting steps:
- **DNS errors**: Verify hostname, try IP address, check router DNS
- **Connection refused**: Check device status, port conflicts, firewalls
- **Timeout errors**: Check device power, network connectivity, congestion
- **Connection resets**: Reduce request frequency, check device resources
- **HTTP errors**: Verify API support, check firmware version

### Performance Analysis
- **Total request time**: Overall performance measurement
- **Slowest step identification**: Pinpoint bottlenecks
- **Timing breakdown**: Detailed analysis of each request stage
- **Error pattern detection**: Identify repeated issues

## Usage Examples

### Enabling Debug Mode
```python
client = WLEDJSONAPIClient("192.168.1.100", debug_mode=True)
# or later:
client.set_debug_mode(True)
```

### Getting Diagnostics
```python
summary = client.get_diagnostics_summary()
diagnostics = client.get_connection_diagnostics()
```

### Exception Handling
```python
try:
    await client.get_state()
except WLEDDNSResolutionError as err:
    print(err.troubleshooting_hint)  # Specific DNS guidance
except WLEDConnectionTimeoutError as err:
    print(f"Timeout at stage: {err.timeout_stage}")
```

## Testing Coverage
- 20+ new test cases covering all diagnostic functionality
- Tests for each new exception type
- Performance metrics testing
- Error history tracking verification
- Debug mode functionality tests
- Timing diagnostics validation

## Benefits
1. **Reduced debugging time**: Specific error messages replace generic "Connection closed"
2. **User guidance**: Built-in troubleshooting steps for common issues
3. **Performance insights**: Detailed timing analysis for optimization
4. **Pattern recognition**: Automatic detection of repeated issues
5. **Development support**: Enhanced logging for troubleshooting during development
6. **Future maintenance**: Comprehensive diagnostic data for ongoing support

## Backward Compatibility
- All existing functionality preserved
- New features are opt-in via debug mode
- No breaking changes to existing API
- Enhanced error messages provide more context while maintaining compatibility

This implementation provides a robust foundation for diagnosing and troubleshooting WLED connection issues while maintaining performance and backward compatibility.