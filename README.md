# WLED Integration for Home Assistant

A robust Home Assistant integration for WLED LED controllers that provides reliable control through the JSON API with automatic retry mechanisms and device discovery.

## Features

- **Automatic Device Discovery**: Discovers WLED devices on your local network using mDNS/zeroconf
- **Manual Device Addition**: Add devices manually by IP address as fallback
- **Reliable Control**: JSON API communication with automatic retry mechanisms (up to 5 attempts)
- **Basic Light Controls**: On/off, brightness control
- **Preset Selection**: Dropdown selector for WLED presets
- **Status Monitoring**: 1-minute polling for device status updates
- **Error Handling**: Robust error handling with connection recovery
- **HACS Compatible**: Ready for installation via Home Assistant Community Store

## Installation

### Via HACS (Recommended)

1. Install HACS if you haven't already
2. Add this repository to HACS as a custom integration
3. Restart Home Assistant
4. Go to Settings > Integrations > Add Integration
5. Search for "WLED" and follow the setup instructions

### Manual Installation

1. Copy the `custom_components/wled` directory to your Home Assistant `config/custom_components` directory
2. Restart Home Assistant
3. Go to Settings > Integrations > Add Integration
4. Search for "WLED" and follow the setup instructions

## Configuration

### Automatic Discovery

The integration will automatically discover WLED devices on your local network. When a device is found, you'll be prompted to confirm the setup.

### Manual Addition

If automatic discovery doesn't work, you can add a device manually:

1. Go to Settings > Integrations > Add Integration
2. Search for "WLED" and select it
3. Enter the IP address of your WLED device
4. Follow the on-screen instructions

## Usage

Once configured, you'll have the following entities available:

### Light Entity
- **Main Light**: Control on/off state and brightness
- **Effect Selection**: Choose from available WLED effects
- **Transition Support**: Smooth transitions when changing states

### Preset Selector
- **Preset Control**: Select and activate WLED presets
- **Brightness as Preset ID**: Use brightness slider to select preset number (0-250)

## Integration Architecture

This integration is designed with reliability in mind:

- **Retry Mechanisms**: Failed commands are automatically retried with exponential backoff
- **Connection Recovery**: Automatically detects and recovers from connection issues
- **Rate Limiting**: Prevents overwhelming low-power WLED devices with rapid requests
- **Status Polling**: Regular status updates keep entity states synchronized

## Troubleshooting

### Device Not Discovered

1. Ensure your WLED device is on the same network as Home Assistant
2. Check that mDNS is enabled on your network
3. Try manual addition using the device's IP address

### Connection Issues

1. Verify the IP address is correct
2. Check that your WLED device is running a compatible version
3. Look at the Home Assistant logs for error messages
4. Ensure no firewall is blocking communication

### Commands Not Working

1. The integration includes automatic retry mechanisms
2. If commands consistently fail, check your network stability
3. Restart both Home Assistant and the WLED device if issues persist

## Development

This integration follows Home Assistant best practices:

- **Config Flow**: Standard Home Assistant configuration flow
- **Data Coordinator**: Centralized data fetching with error handling
- **Entity Platform**: Proper entity management and state updates
- **Type Hints**: Full type annotation support
- **Error Handling**: Comprehensive error handling and logging

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This integration is released under the MIT License.

## Support

If you encounter issues:

1. Check the [troubleshooting section](#troubleshooting)
2. Look at the Home Assistant logs
3. Open an issue on GitHub with details about your problem

## Requirements

- Home Assistant 2023.1.0 or newer
- Python 3.9 or newer
- aiohttp 3.8.0 or newer (automatically installed by Home Assistant)

## Compatibility

This integration is designed to work with most WLED devices running recent firmware versions. It has been tested with:

- WLED 0.13.x and newer
- ESP8266 and ESP32 based devices
- Various LED strip configurations

If you encounter compatibility issues with specific WLED versions or hardware, please open an issue with details.