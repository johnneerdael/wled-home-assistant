## ADDED Requirements

### Requirement: WLED JSONAPI Device Discovery
The system SHALL automatically discover WLED devices on the local network using mDNS/zeroconf.

#### Scenario: Automatic device discovery
- **WHEN** a WLED device broadcasts its presence via mDNS
- **THEN** the WLED JSONAPI integration shall detect the device and offer it for setup

#### Scenario: Manual device addition
- **WHEN** a user manually adds a WLED device by IP address
- **THEN** the WLED JSONAPI integration shall validate the connection and create the device

### Requirement: WLED JSONAPI Light Control
The system SHALL provide basic light control for WLED devices including on/off, brightness, and preset selection.

#### Scenario: Turn light on/off
- **WHEN** a user toggles the WLED light
- **THEN** the WLED JSONAPI integration shall send the appropriate JSON API command with retry logic

#### Scenario: Adjust brightness
- **WHEN** a user changes the brightness
- **THEN** the WLED JSONAPI integration shall update the brightness value via JSON API

#### Scenario: Select preset
- **WHEN** a user selects a preset from the dropdown
- **THEN** the WLED JSONAPI integration shall activate the preset on the WLED device

### Requirement: WLED JSONAPI Retry Mechanism
The system SHALL automatically retry failed API commands up to 5 times with exponential backoff.

#### Scenario: Command retry on failure
- **WHEN** an API command fails due to network issues
- **THEN** the WLED JSONAPI integration shall retry the command with increasing delays

#### Scenario: Max retry limit
- **WHEN** a command fails 5 times consecutively
- **THEN** the WLED JSONAPI integration shall mark the device as unavailable and stop retrying

### Requirement: WLED JSONAPI Status Monitoring
The system SHALL monitor device status every minute and update entity states accordingly.

#### Scenario: Periodic status check
- **WHEN** one minute passes since the last status update
- **THEN** the WLED JSONAPI integration shall query the device status and update entity states

#### Scenario: Device availability detection
- **WHEN** a device stops responding to status queries
- **THEN** the WLED JSONAPI integration shall mark the device as unavailable

### Requirement: WLED JSONAPI HACS Compatibility
The system SHALL be compatible with Home Assistant Community Store requirements.

#### Scenario: Repository structure
- **WHEN** the WLED JSONAPI integration is published to HACS
- **THEN** it shall follow the required directory structure and include all necessary metadata files