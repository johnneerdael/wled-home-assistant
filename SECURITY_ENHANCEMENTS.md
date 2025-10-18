# WLED Config Flow Security Enhancements

## Overview

This document describes the security enhancements implemented in the WLED JSON API config flow to prevent DNS rebinding attacks and malicious hostname injection.

## Security Improvements

### Enhanced Host Validation

The config flow now includes comprehensive host input validation to prevent various attack vectors:

#### 1. Protocol Injection Prevention
- **Risk**: Attackers could inject protocols like `http://` or `file://` to redirect connections
- **Protection**: Any hostname containing `://` is rejected
- **Example**: `http://malicious.com` → **Rejected**

#### 2. Command Injection Prevention
- **Risk**: Special characters could be used for command injection in certain environments
- **Protection**: Hostnames containing `;`, `&`, `|`, `` ` ``, `$`, `(`, `)`, `{`, `}`, `[`, `]`, `<`, `>`, `"`, `'` are rejected
- **Example**: `192.168.1.100; rm -rf /` → **Rejected**

#### 3. Path Traversal Prevention
- **Risk**: Path traversal sequences could access unintended files or paths
- **Protection**: Hostnames containing `../` or `..\\` are rejected
- **Example**: `../etc/passwd` → **Rejected**

#### 4. DNS Rebinding Protection
- **Risk**: DNS rebinding attacks could redirect connections to malicious servers
- **Protection**: Public IP addresses are rejected with security warnings
- **Example**: `8.8.8.8` → **Rejected**

#### 5. Hostname Format Validation
- **Risk**: Malformed hostnames could cause unexpected behavior
- **Protection**: Strict RFC-compliant hostname validation
  - Only letters, digits, hyphens, and dots allowed
  - Cannot start or end with dot or hyphen
  - No consecutive dots
  - Each label limited to 63 characters
  - Total length limited to 253 characters

### Allowed Host Formats

The validation accepts the following secure host formats:

#### IP Addresses
- **Private IPs**: `192.168.1.100`, `10.0.0.50`, `172.16.0.1`
- **Localhost**: `127.0.0.1`, `::1`
- **Link-local**: `169.254.1.1`, `fe80::1`

#### Hostnames
- **Local hostnames**: `wled.local`, `wled-device`, `living-room-wled`
- **FQDNs**: `wled.example.com`, `wled.home.lan`

### Security Logging

The enhanced validation includes security logging:
- **Debug logging**: All validation results with details
- **Warning logging**: Public IP address attempts (still logged for security monitoring)

## Implementation Details

### Validation Function

The `_validate_host()` method implements the security checks:

```python
def _validate_host(self, host: str) -> Tuple[bool, str]:
    """Validate host input to prevent malicious inputs."""
    # Length validation
    # Protocol injection prevention
    # Command injection prevention
    # Path traversal prevention
    # IP address validation (private vs public)
    # Hostname format validation
    return is_valid, validation_message
```

### Integration Points

The validation is applied in:
1. **User step** (`async_step_user`) - Initial device setup
2. **Reconfigure step** (`async_step_reconfigure`) - Device reconfiguration

### Error Handling

Invalid inputs are rejected with clear error messages:
- Form remains open with validation error
- User receives specific guidance about the validation failure
- No connection attempts are made for invalid inputs

## Testing

Comprehensive test coverage includes:
- Unit tests for all validation scenarios
- Integration tests for config flow steps
- Security-focused test cases for attack vectors
- Edge case testing for boundary conditions

## Security Benefits

1. **Prevents DNS Rebinding**: Public IPs rejected, reducing attack surface
2. **Stops Injection Attacks**: Protocol and command injection blocked
3. **Ensures Input Sanitization**: All inputs validated before processing
4. **Provides Clear Feedback**: Users understand why inputs are rejected
5. **Maintains Compatibility**: Legitimate IoT device hostnames still accepted

## Backward Compatibility

The security enhancements maintain full backward compatibility:
- Existing private IP and local hostname configurations continue to work
- No changes to device discovery process
- No impact on established integrations

## Recommendations

For optimal security:
1. Use private IP addresses for WLED devices when possible
2. Configure firewall rules to restrict IoT device access
3. Regularly review Home Assistant logs for security events
4. Keep WLED firmware updated to the latest version
5. Consider network segmentation for IoT devices