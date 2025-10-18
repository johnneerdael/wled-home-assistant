# Project Context

## Purpose
Create a robust Home Assistant HACS integration for WLED LED controllers that provides reliable control through the JSON API with automatic retry mechanisms and device discovery.

## Tech Stack
- Python 3.9+
- Home Assistant Core
- HTTP/JSON API client
- mDNS/zeroconf for device discovery
- Asyncio for concurrent operations

## Project Conventions

### Code Style
- Follow PEP 8 Python style guidelines
- Use type hints for all function signatures
- Implement proper error handling with custom exceptions
- Use async/await patterns for all I/O operations

### Architecture Patterns
- Use DataUpdateCoordinator for centralized data fetching
- Implement ConfigFlow for device setup and discovery
- Create separate entity classes for different device capabilities
- Use retry mechanisms with exponential backoff

### Testing Strategy
- Unit tests for all API client methods
- Integration tests for config flow scenarios
- Mock WLED devices for testing retry logic
- Test coverage minimum 80%

### Git Workflow
- Feature branches for development
- Pull requests for code review
- Semantic versioning for releases
- Automated CI/CD pipeline

## Domain Context
WLED is an open-source LED controller firmware that runs on ESP8266/ESP32 microcontrollers. It provides a JSON API for controlling LED effects, brightness, colors, and presets. The integration needs to handle:
- Device discovery via mDNS
- Manual device addition
- Real-time status monitoring
- Command retry logic for unreliable networks
- Preset and playlist management

## Important Constraints
- WLED devices run on low-power hardware and can be slow to respond
- Network connectivity may be unreliable
- Must not overwhelm devices with rapid API calls
- Need to handle different WLED versions and capabilities
- Must be compatible with Home Assistant's integration quality standards

## External Dependencies
- Home Assistant Core (integration framework)
- aiohttp (HTTP client)
- zeroconf (mDNS discovery)
- voluptuous (configuration validation)
