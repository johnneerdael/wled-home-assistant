"""Example usage of the fixed WLED API client with proper SSL configuration."""
import asyncio
import logging

from custom_components.wled_jsonapi.api import WLEDJSONAPIClient

# Configure logging
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


async def example_basic_usage():
    """Example of basic WLED API usage with default HTTP configuration."""
    # Create client with default HTTP settings (most WLED devices use HTTP)
    async with WLEDJSONAPIClient("192.168.51.202") as client:
        try:
            # Test connection
            if await client.test_connection():
                print("✅ Connection successful!")

                # Get device info
                info = await client.get_info()
                print(f"Device info: {info}")

                # Get current state
                state = await client.get_state()
                print(f"Current state: {state}")

                # Turn on with brightness 200
                result = await client.turn_on(brightness=200)
                print(f"Turn on result: {result}")

            else:
                print("❌ Connection failed!")

        except Exception as e:
            print(f"❌ Error: {e}")


async def example_ssl_usage():
    """Example of WLED API usage with HTTPS configuration."""
    # Create client with HTTPS and SSL verification enabled
    async with WLEDJSONAPIClient(
        host="192.168.51.202",
        use_ssl=True,
        verify_ssl=True
    ) as client:
        try:
            # Test connection
            if await client.test_connection():
                print("✅ HTTPS connection successful!")

                # Get device info
                info = await client.get_info()
                print(f"Device info: {info}")

            else:
                print("❌ HTTPS connection failed!")

        except Exception as e:
            print(f"❌ HTTPS Error: {e}")


async def example_ssl_insecure_usage():
    """Example of WLED API usage with HTTPS but without SSL verification (insecure)."""
    # Create client with HTTPS but without SSL verification
    # Use only for devices with self-signed certificates
    async with WLEDJSONAPIClient(
        host="192.168.51.202",
        use_ssl=True,
        verify_ssl=False
    ) as client:
        try:
            # Test connection
            if await client.test_connection():
                print("✅ HTTPS connection successful (SSL verification disabled)!")

                # Get device info
                info = await client.get_info()
                print(f"Device info: {info}")

            else:
                print("❌ HTTPS connection failed!")

        except Exception as e:
            print(f"❌ HTTPS Error: {e}")


async def example_auto_detection():
    """Example of auto-detecting the best connection method."""
    async with WLEDJSONAPIClient("192.168.51.202") as client:
        try:
            # Auto-detect connection method
            if await client.auto_detect_connection():
                print(f"✅ Connection established using {'HTTPS' if client.use_ssl else 'HTTP'}")
                print(f"SSL verification: {'Enabled' if client.verify_ssl else 'Disabled'}")

                # Get device info
                info = await client.get_info()
                print(f"Device info: {info}")

                # Get current state
                state = await client.get_state()
                print(f"Current state: {state}")

            else:
                print("❌ Could not establish any connection to the device!")

        except Exception as e:
            print(f"❌ Error: {e}")


async def example_advanced_configuration():
    """Example of advanced configuration with custom SSL context."""
    import ssl

    # Create custom SSL context for specific requirements
    custom_ssl_context = ssl.create_default_context()
    # Add your custom SSL configuration here

    async with WLEDJSONAPIClient(
        host="192.168.51.202",
        use_ssl=True,
        verify_ssl=True,
        ssl_context=custom_ssl_context
    ) as client:
        try:
            # Test connection
            if await client.test_connection():
                print("✅ Custom SSL configuration successful!")

                # Get device info
                info = await client.get_info()
                print(f"Device info: {info}")

            else:
                print("❌ Custom SSL configuration failed!")

        except Exception as e:
            print(f"❌ Custom SSL Error: {e}")


async def main():
    """Run all examples."""
    print("🔌 WLED API Client Examples\n")

    print("1. Basic HTTP usage:")
    await example_basic_usage()
    print()

    print("2. HTTPS usage with SSL verification:")
    await example_ssl_usage()
    print()

    print("3. HTTPS usage without SSL verification (insecure):")
    await example_ssl_insecure_usage()
    print()

    print("4. Auto-detect connection method:")
    await example_auto_detection()
    print()

    print("5. Advanced SSL configuration:")
    await example_advanced_configuration()
    print()


if __name__ == "__main__":
    asyncio.run(main())