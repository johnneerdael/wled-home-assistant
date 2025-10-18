#!/usr/bin/env python3
"""Simple test script to verify SSL/HTTP protocol fix."""

import asyncio
import logging
import sys
import os

# Add the custom_components directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

from wled_jsonapi.api import WLEDJSONAPIClient

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

_LOGGER = logging.getLogger(__name__)

async def test_http_connection():
    """Test HTTP connection to a WLED device."""
    # Test with a local WLED device - replace with your actual device IP
    host = "192.168.51.202"

    _LOGGER.info("Testing HTTP connection to WLED device at %s", host)

    try:
        # Create client with HTTP (no SSL)
        async with WLEDJSONAPIClient(host=host, use_ssl=False) as client:
            _LOGGER.info("Created WLED client with HTTP (use_ssl=False)")

            # Test basic connection
            if await client.test_connection():
                _LOGGER.info("✅ HTTP connection test successful!")

                # Try to get device info
                try:
                    info = await client.get_info()
                    _LOGGER.info("✅ Successfully retrieved device info: %s", info.get('name', 'Unknown'))
                except Exception as e:
                    _LOGGER.error("❌ Failed to get device info: %s", e)
                    return False

                # Try to get device state
                try:
                    state = await client.get_state()
                    _LOGGER.info("✅ Successfully retrieved device state")
                except Exception as e:
                    _LOGGER.error("❌ Failed to get device state: %s", e)
                    return False

                return True
            else:
                _LOGGER.error("❌ HTTP connection test failed")
                return False

    except Exception as e:
        _LOGGER.error("❌ Exception during HTTP connection test: %s", e)
        return False

async def test_auto_detection():
    """Test auto-detection of connection method."""
    host = "192.168.51.202"

    _LOGGER.info("Testing auto-detection for WLED device at %s", host)

    try:
        async with WLEDJSONAPIClient(host=host, use_ssl=False) as client:
            if await client.auto_detect_connection():
                _LOGGER.info("✅ Auto-detection successful! Using SSL: %s", client.use_ssl)
                return True
            else:
                _LOGGER.error("❌ Auto-detection failed")
                return False
    except Exception as e:
        _LOGGER.error("❌ Exception during auto-detection: %s", e)
        return False

async def main():
    """Main test function."""
    _LOGGER.info("=" * 60)
    _LOGGER.info("Testing WLED SSL/HTTP Protocol Fix")
    _LOGGER.info("=" * 60)

    # Test HTTP connection
    _LOGGER.info("\n1. Testing HTTP connection...")
    http_success = await test_http_connection()

    # Test auto-detection
    _LOGGER.info("\n2. Testing auto-detection...")
    auto_success = await test_auto_detection()

    # Summary
    _LOGGER.info("\n" + "=" * 60)
    _LOGGER.info("TEST RESULTS:")
    _LOGGER.info(f"HTTP Connection: {'✅ PASS' if http_success else '❌ FAIL'}")
    _LOGGER.info(f"Auto-Detection: {'✅ PASS' if auto_success else '❌ FAIL'}")

    if http_success and auto_success:
        _LOGGER.info("🎉 All tests passed! SSL/HTTP fix is working correctly.")
        return 0
    else:
        _LOGGER.error("💥 Some tests failed. Please check the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))