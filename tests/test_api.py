"""Tests for WLED API client."""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientError, ClientResponseError

from custom_components.wled_jsonapi.api import WLEDJSONAPIClient
from custom_components.wled_jsonapi.exceptions import (
    WLEDCommandError,
    WLEDConnectionError,
    WLEDInvalidResponseError,
    WLEDDNSResolutionError,
    WLEDConnectionTimeoutError,
    WLEDConnectionRefusedError,
    WLEDConnectionResetError,
    WLEDNetworkError,
    WLEDHTTPError,
    WLEDInvalidJSONError,
)


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = AsyncMock()
    return session


@pytest.fixture
def wled_client(mock_session):
    """Create a WLED API client for testing."""
    return WLEDJSONAPIClient("192.168.1.100", mock_session)


@pytest.fixture
def wled_simple_client(mock_session):
    """Create a WLED API client with simple mode for testing."""
    return WLEDJSONAPIClient("192.168.1.100", mock_session, use_simple_client=True)


@pytest.fixture
def wled_simple_client_no_session():
    """Create a WLED API client with simple mode and no external session."""
    return WLEDJSONAPIClient("192.168.1.100", use_simple_client=True)


@pytest.mark.asyncio
async def test_get_state(wled_client, mock_session):
    """Test getting device state."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 128}
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.get_state()
    
    # Assertions
    assert result == {"on": True, "bri": 128}
    mock_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_get_state_invalid_response(wled_client, mock_session):
    """Test getting device state with invalid response."""
    # Mock response with invalid data
    mock_response = AsyncMock()
    mock_response.json.return_value = "invalid"
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Test and assert exception
    with pytest.raises(WLEDInvalidResponseError):
        await wled_client.get_state()


@pytest.mark.asyncio
async def test_get_info(wled_client, mock_session):
    """Test getting device info."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"name": "WLED Test", "ver": "0.13.0"}
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.get_info()
    
    # Assertions
    assert result == {"name": "WLED Test", "ver": "0.13.0"}
    mock_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_update_state(wled_client, mock_session):
    """Test updating device state."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 255}
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.update_state({"on": True, "bri": 255})
    
    # Assertions
    assert result == {"on": True, "bri": 255}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_turn_on(wled_client, mock_session):
    """Test turning on the device."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 200}
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.turn_on(brightness=200)
    
    # Assertions
    assert result == {"on": True, "bri": 200}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_turn_off(wled_client, mock_session):
    """Test turning off the device."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": False}
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.turn_off()
    
    # Assertions
    assert result == {"on": False}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_set_brightness(wled_client, mock_session):
    """Test setting brightness."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 150}
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.set_brightness(150)
    
    # Assertions
    assert result == {"on": True, "bri": 150}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_set_preset(wled_client, mock_session):
    """Test setting preset."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "ps": 5}
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.set_preset(5)
    
    # Assertions
    assert result == {"on": True, "ps": 5}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_set_effect(wled_client, mock_session):
    """Test setting effect."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "seg": [{"fx": 10}]}
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.set_effect(10, speed=128, intensity=64)
    
    # Assertions
    assert result == {"on": True, "seg": [{"fx": 10}]}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_test_connection_success(wled_client, mock_session):
    """Test successful connection test."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"name": "WLED Test"}
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.test_connection()
    
    # Assertions
    assert result is True
    mock_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_test_connection_failure(wled_client, mock_session):
    """Test failed connection test."""
    # Mock response that raises an error
    mock_session.get.side_effect = ClientError()

    # Test
    result = await wled_client.test_connection()
    
    # Assertions
    assert result is False


@pytest.mark.asyncio
async def test_retry_mechanism(wled_client, mock_session):
    """Test retry mechanism on connection failure."""
    # Mock responses - first few fail, last one succeeds
    mock_responses = [
        Mock(side_effect=ClientError()),
        Mock(side_effect=ClientError()),
        AsyncMock(),
    ]
    
    mock_session.get.side_effect = [
        ClientError(),
        ClientError(),
        AsyncMock(),
    ]
    
    # Setup the successful response
    mock_session.get.return_value.__aenter__.return_value.json.return_value = {
        "name": "WLED Test"
    }

    # Test
    result = await wled_client.get_info()
    
    # Assertions
    assert result == {"name": "WLED Test"}
    assert mock_session.get.call_count == 3


@pytest.mark.asyncio
async def test_max_retries_exceeded(wled_client, mock_session):
    """Test behavior when max retries are exceeded."""
    # Mock response that always fails
    mock_session.get.side_effect = ClientError()

    # Test and assert exception
    with pytest.raises(WLEDConnectionError):
        await wled_client.get_info()
    
    # Should have tried 6 times (1 initial + 5 retries)
    assert mock_session.get.call_count == 6


@pytest.mark.asyncio
async def test_close_session(wled_client, mock_session):
    """Test closing the HTTP session."""
    # Create client that manages its own session
    client = WLEDJSONAPIClient("192.168.1.100")
    
    # Mock the session close method
    client._session.close = AsyncMock()
    
    # Test
    await client.close()
    
    # Assertions
    client._session.close.assert_called_once()


# Connection Diagnostics Tests

@pytest.fixture
def wled_client_with_diagnostics():
    """Create a WLED API client with diagnostics enabled."""
    return WLEDJSONAPIClient("192.168.1.100", debug_mode=True)


@pytest.mark.asyncio
async def test_debug_mode_toggle(wled_client):
    """Test debug mode toggle functionality."""
    # Test initial state
    assert wled_client.debug_mode is False
    assert wled_client.diagnostics_manager.debug_mode is False

    # Test enabling debug mode
    wled_client.set_debug_mode(True)
    assert wled_client.debug_mode is True
    assert wled_client.diagnostics_manager.debug_mode is True

    # Test disabling debug mode
    wled_client.set_debug_mode(False)
    assert wled_client.debug_mode is False
    assert wled_client.diagnostics_manager.debug_mode is False


@pytest.mark.asyncio
async def test_diagnostics_summary_no_data(wled_client):
    """Test diagnostics summary when no data is available."""
    summary = wled_client.get_diagnostics_summary()

    assert summary["status"] == "no_diagnostics"
    assert "message" in summary
    assert summary["debug_mode"] is False


@pytest.mark.asyncio
async def test_diagnostics_summary_with_data(wled_client_with_diagnostics, mock_session):
    """Test diagnostics summary with actual data."""
    # Mock a successful response to generate diagnostics
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 128}
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.text.return_value = '{"on": true, "bri": 128}'
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Make a request to generate diagnostics
    await wled_client_with_diagnostics.get_state()

    # Get diagnostics summary
    summary = wled_client_with_diagnostics.get_diagnostics_summary()

    assert summary["status"] == "available"
    assert summary["host"] == "192.168.1.100"
    assert summary["debug_mode"] is True
    assert "performance_metrics" in summary
    assert "troubleshooting_summary" in summary
    assert "recent_errors" in summary


@pytest.mark.asyncio
async def test_dns_resolution_error_handling(wled_client_with_diagnostics, mock_session):
    """Test DNS resolution error handling with specific exception."""
    # Mock DNS resolution failure
    from aiohttp import ClientConnectorError
    mock_session.get.side_effect = ClientConnectorError(
        connection_key=None,
        os_error=None,
        str="Name resolution failed"
    )

    # Test and assert specific DNS exception
    with pytest.raises(WLEDDNSResolutionError) as exc_info:
        await wled_client_with_diagnostics.get_state()

    assert "192.168.1.100" in str(exc_info.value)
    assert hasattr(exc_info.value, 'troubleshooting_hint')
    assert "DNS" in exc_info.value.troubleshooting_hint


@pytest.mark.asyncio
async def test_connection_refused_error_handling(wled_client_with_diagnostics, mock_session):
    """Test connection refused error handling with specific exception."""
    from aiohttp import ClientConnectorError
    mock_session.get.side_effect = ClientConnectorError(
        connection_key=None,
        os_error=None,
        str="Connection refused"
    )

    # Test and assert specific connection refused exception
    with pytest.raises(WLEDConnectionRefusedError) as exc_info:
        await wled_client_with_diagnostics.get_state()

    assert "192.168.1.100" in str(exc_info.value)
    assert hasattr(exc_info.value, 'troubleshooting_hint')
    assert "refused the connection" in str(exc_info.value)


@pytest.mark.asyncio
async def test_connection_reset_error_handling(wled_client_with_diagnostics, mock_session):
    """Test connection reset error handling with specific exception."""
    from aiohttp import ClientConnectorError
    mock_session.get.side_effect = ClientConnectorError(
        connection_key=None,
        os_error=None,
        str="Connection reset by peer"
    )

    # Test and assert specific connection reset exception
    with pytest.raises(WLEDConnectionResetError) as exc_info:
        await wled_client_with_diagnostics.get_state()

    assert "192.168.1.100" in str(exc_info.value)
    assert hasattr(exc_info.value, 'troubleshooting_hint')
    assert "reset the connection" in str(exc_info.value)


@pytest.mark.asyncio
async def test_connection_timeout_error_handling(wled_client_with_diagnostics, mock_session):
    """Test connection timeout error handling with specific exception."""
    from aiohttp import ClientConnectorError
    mock_session.get.side_effect = ClientConnectorError(
        connection_key=None,
        os_error=None,
        str="Connection timeout"
    )

    # Test and assert specific timeout exception
    with pytest.raises(WLEDConnectionTimeoutError) as exc_info:
        await wled_client_with_diagnostics.get_state()

    assert "192.168.1.100" in str(exc_info.value)
    assert hasattr(exc_info.value, 'troubleshooting_hint')
    assert exc_info.value.timeout_stage == "connect"


@pytest.mark.asyncio
async def test_ssl_error_handling(wled_client_with_diagnostics, mock_session):
    """Test SSL error handling with specific exception."""
    from aiohttp import ClientConnectorError
    mock_session.get.side_effect = ClientConnectorError(
        connection_key=None,
        os_error=None,
        str="SSL verification failed"
    )

    # Test and assert specific SSL exception
    with pytest.raises(WLEDSSLError) as exc_info:
        await wled_client_with_diagnostics.get_state()

    assert "192.168.1.100" in str(exc_info.value)
    assert hasattr(exc_info.value, 'troubleshooting_hint')
    assert "SSL" in exc_info.value.troubleshooting_hint


@pytest.mark.asyncio
async def test_http_error_handling(wled_client_with_diagnostics, mock_session):
    """Test HTTP error handling with specific exception."""
    from aiohttp import ClientResponseError
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.message = "Not Found"
    mock_response.headers = {"Content-Type": "text/html"}

    mock_session.get.side_effect = ClientResponseError(
        request_info=Mock(),
        history=None,
        status=404,
        message="Not Found",
        headers=mock_response.headers
    )

    # Test and assert specific HTTP exception
    with pytest.raises(WLEDHTTPError) as exc_info:
        await wled_client_with_diagnostics.get_state()

    assert "192.168.1.100" in str(exc_info.value)
    assert exc_info.value.http_code == 404
    assert hasattr(exc_info.value, 'troubleshooting_hint')


@pytest.mark.asyncio
async def test_invalid_json_error_handling(wled_client_with_diagnostics, mock_session):
    """Test invalid JSON error handling with specific exception."""
    # Mock response with invalid JSON
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.text.return_value = '{"invalid": json}'  # Invalid JSON
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Test and assert specific JSON exception
    with pytest.raises(WLEDInvalidJSONError) as exc_info:
        await wled_client_with_diagnostics.get_state()

    assert "192.168.1.100" in str(exc_info.value)
    assert "invalid JSON" in str(exc_info.value)
    assert exc_info.value.response_data is not None


@pytest.mark.asyncio
async def test_empty_response_error_handling(wled_client_with_diagnostics, mock_session):
    """Test empty response error handling."""
    # Mock empty response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.text.return_value = ""  # Empty response
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Test and assert specific invalid response exception
    with pytest.raises(WLEDInvalidResponseError) as exc_info:
        await wled_client_with_diagnostics.get_state()

    assert "192.168.1.100" in str(exc_info.value)
    assert "empty response" in str(exc_info.value)
    assert exc_info.value.response_data == "<empty>"


@pytest.mark.asyncio
async def test_session_state_validation(wled_client_with_diagnostics, mock_session):
    """Test session state validation before requests."""
    # Mock closed session
    mock_session.closed = True

    # Test and assert session error exception
    with pytest.raises(Exception) as exc_info:  # Will be WLEDSessionError
        await wled_client_with_diagnostics.get_state()

    assert "session is closed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_timing_diagnostics_success(wled_client_with_diagnostics, mock_session):
    """Test that timing diagnostics are collected on successful requests."""
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 128}
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.text.return_value = '{"on": true, "bri": 128}'
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Make a request
    await wled_client_with_diagnostics.get_state()

    # Check that diagnostics were collected
    diagnostics = wled_client_with_diagnostics.get_connection_diagnostics()
    assert diagnostics is not None
    assert len(diagnostics.timing_breakdown) > 0

    # Check for expected timing steps
    expected_steps = [
        "session_validation",
        "request_setup",
        "http_request_complete",
        "response_processed"
    ]

    for step in expected_steps:
        assert any(step in key for key in diagnostics.timing_breakdown.keys())


@pytest.mark.asyncio
async def test_error_history_tracking(wled_client_with_diagnostics, mock_session):
    """Test that errors are tracked in diagnostics history."""
    # Mock a DNS error
    from aiohttp import ClientConnectorError
    mock_session.get.side_effect = ClientConnectorError(
        connection_key=None,
        os_error=None,
        str="Name resolution failed"
    )

    # Make a request that will fail
    try:
        await wled_client_with_diagnostics.get_state()
    except WLEDDNSResolutionError:
        pass  # Expected

    # Check that error was recorded
    diagnostics = wled_client_with_diagnostics.get_connection_diagnostics()
    assert diagnostics is not None
    assert len(diagnostics.error_history) > 0

    # Check error details
    error = diagnostics.error_history[0]
    assert error["error_type"] == "WLEDDNSResolutionError"
    assert "192.168.1.100" in error["details"]["message"]


@pytest.mark.asyncio
async def test_performance_metrics_calculation(wled_client_with_diagnostics, mock_session):
    """Test performance metrics calculation."""
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 128}
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.text.return_value = '{"on": true, "bri": 128}'
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Make a request
    await wled_client_with_diagnostics.get_state()

    # Get performance metrics
    diagnostics = wled_client_with_diagnostics.get_connection_diagnostics()
    metrics = diagnostics.calculate_performance_metrics()

    assert "total_request_time_ms" in metrics
    assert "timing_breakdown" in metrics
    assert "error_count" in metrics
    assert "recent_errors" in metrics

    # Check that total time is reasonable
    assert metrics["total_request_time_ms"] > 0


@pytest.mark.asyncio
async def test_troubleshooting_summary_generation(wled_client_with_diagnostics, mock_session):
    """Test troubleshooting summary generation."""
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 128}
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.text.return_value = '{"on": true, "bri": 128}'
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Make a request
    await wled_client_with_diagnostics.get_state()

    # Get troubleshooting summary
    diagnostics = wled_client_with_diagnostics.get_connection_diagnostics()
    summary = diagnostics.get_troubleshooting_summary()

    assert isinstance(summary, str)
    assert len(summary) > 0
    # Should indicate no issues for successful request
    assert "No obvious issues detected" in summary


# Simple Client Mode Tests

@pytest.mark.asyncio
async def test_simple_client_configuration(wled_simple_client_no_session):
    """Test that simple client uses correct configuration."""
    assert wled_simple_client_no_session.use_simple_client is True
    assert wled_simple_client_no_session._max_retries == 3
    assert wled_simple_client_no_session._retry_delay == 1.0

    # Check simplified session configuration
    config = wled_simple_client_no_session._session_config
    assert config["connector"]["force_close"] is True
    assert config["connector"]["limit"] == 1
    assert config["connector"]["limit_per_host"] == 1
    assert config["connector"]["use_dns_cache"] is False
    assert config["connector"]["keepalive_timeout"] == 0
    assert config["auto_decompress"] is False

    # Check minimal headers
    assert "User-Agent" in config["headers"]
    assert len(config["headers"]) == 1  # Only User-Agent

    # Check timeout configuration
    assert config["timeout"]["total"] == 30
    assert config["timeout"]["connect"] == 10
    assert config["timeout"]["sock_read"] is None


@pytest.mark.asyncio
async def test_simple_client_get_state(wled_simple_client, mock_session):
    """Test getting device state with simple client."""
    # Mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 128}
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_simple_client.get_state()

    # Assertions
    assert result == {"on": True, "bri": 128}
    mock_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_simple_client_retry_logic(wled_simple_client, mock_session):
    """Test simple client retry logic with failures then success."""
    # Mock responses - first 2 fail, 3rd succeeds
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise ClientError("Simulated failure")
        else:
            mock_response = AsyncMock()
            mock_response.json.return_value = {"on": True, "bri": 128}
            mock_response.status = 200
            mock_response.headers = {"Content-Type": "application/json"}
            mock_response.text.return_value = '{"on": true, "bri": 128}'
            return mock_response

    mock_session.get.side_effect = mock_get

    # Test
    result = await wled_simple_client.get_state()

    # Assertions
    assert result == {"on": True, "bri": 128}
    assert call_count == 3  # Should have tried 3 times


@pytest.mark.asyncio
async def test_simple_client_max_retries_exceeded(wled_simple_client, mock_session):
    """Test simple client when max retries are exceeded."""
    # Mock response that always fails
    mock_session.get.side_effect = ClientError("Persistent failure")

    # Test and assert exception
    with pytest.raises(ClientError):
        await wled_simple_client.get_state()

    # Should have tried 4 times (1 initial + 3 retries)
    assert mock_session.get.call_count == 4


@pytest.mark.asyncio
async def test_simple_client_vs_enhanced_client_configuration():
    """Test that simple and enhanced clients have different configurations."""
    simple_client = WLEDJSONAPIClient("192.168.1.100", use_simple_client=True)
    enhanced_client = WLEDJSONAPIClient("192.168.1.100", use_simple_client=False)

    # Check retry settings
    assert simple_client._max_retries == 3
    assert enhanced_client._max_retries == 5
    assert simple_client._retry_delay == 1.0
    assert enhanced_client._retry_delay is None

    # Check connector settings
    simple_config = simple_client._session_config["connector"]
    enhanced_config = enhanced_client._session_config["connector"]

    assert simple_config["force_close"] is True
    assert enhanced_config["force_close"] is False
    assert simple_config["use_dns_cache"] is False
    assert enhanced_config["use_dns_cache"] is True
    assert simple_config["keepalive_timeout"] == 0
    assert enhanced_config["keepalive_timeout"] == 30

    # Check headers
    simple_headers = simple_client._session_config["headers"]
    enhanced_headers = enhanced_client._session_config["headers"]

    assert len(simple_headers) == 1  # Only User-Agent
    assert len(enhanced_headers) == 4  # User-Agent, Accept, Accept-Encoding, Connection


@pytest.mark.asyncio
async def test_simple_client_with_external_session():
    """Test simple client configuration when using external session."""
    mock_session = AsyncMock()
    client = WLEDJSONAPIClient("192.168.1.100", session=mock_session, use_simple_client=True)

    # Should use simple retry logic even with external session
    assert client.use_simple_client is True
    assert client._max_retries == 3
    assert client._retry_delay == 1.0
    assert client._close_session is False  # Should not close external session


@pytest.mark.asyncio
async def test_simple_client_session_creation():
    """Test that simple client creates session with correct configuration."""
    client = WLEDJSONAPIClient("192.168.1.100", use_simple_client=True)

    # Mock session creation components
    with patch('aiohttp.TCPConnector') as mock_connector, \
         patch('aiohttp.ClientTimeout') as mock_timeout, \
         patch('aiohttp.ClientSession') as mock_session_class:

        # Setup mocks
        mock_connector_instance = AsyncMock()
        mock_timeout_instance = AsyncMock()
        mock_session_instance = AsyncMock()

        mock_connector.return_value = mock_connector_instance
        mock_timeout.return_value = mock_timeout_instance
        mock_session_class.return_value = mock_session_instance

        # Call _ensure_session to trigger session creation
        session = await client._ensure_session()

        # Verify correct configuration was used
        mock_connector.assert_called_once_with(
            enable_cleanup_closed=False,
            force_close=True,
            limit=1,
            limit_per_host=1,
            ttl_dns_cache=0,
            use_dns_cache=False,
            keepalive_timeout=0,
            disable_cleanup_closed=True,
        )

        mock_timeout.assert_called_once_with(
            total=30,
            connect=10,
            sock_read=None,
        )

        mock_session_class.assert_called_once_with(
            connector=mock_connector_instance,
            timeout=mock_timeout_instance,
            headers={"User-Agent": "Home-Assistant-WLED-JSONAPI/1.0"},
            auto_decompress=False,
        )


# Response Validation Tests

@pytest.mark.asyncio
async def test_successful_state_command_validation(wled_client, mock_session):
    """Test successful state command validation."""
    # Mock response with matching state
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 128, "ps": 5}
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.update_state({"on": True, "bri": 128, "ps": 5})

    # Assertions
    assert result == {"on": True, "bri": 128, "ps": 5}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_state_command_validation_critical_mismatch(wled_client, mock_session):
    """Test state command validation with critical mismatch."""
    # Mock response where device didn't apply the on=True command
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": False, "bri": 128}  # Device didn't turn on
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test and assert exception
    with pytest.raises(WLEDCommandError) as exc_info:
        await wled_client.update_state({"on": True, "bri": 128})

    assert "did not apply critical state changes" in str(exc_info.value)
    assert "on: expected True, got False" in str(exc_info.value)


@pytest.mark.asyncio
async def test_state_command_validation_non_critical_mismatch(wled_client, mock_session):
    """Test state command validation with non-critical mismatch."""
    # Mock response where device applied critical changes but not non-critical
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "bri": 127}  # Brightness slightly different
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test - should succeed despite minor difference
    result = await wled_client.update_state({"on": True, "bri": 128})

    # Assertions
    assert result == {"on": True, "bri": 127}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_wled_error_response_detection(wled_client, mock_session):
    """Test detection of WLED error responses."""
    # Mock response with WLED error (HTTP 200 but contains error)
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "error": {
            "message": "Invalid segment ID",
            "code": 400
        }
    }
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test and assert exception
    with pytest.raises(WLEDCommandError) as exc_info:
        await wled_client.update_state({"seg": [{"fx": 999}]})

    assert "WLED device error: Invalid segment ID" in str(exc_info.value)


@pytest.mark.asyncio
async def test_wled_success_false_response(wled_client, mock_session):
    """Test detection of WLED success=false responses."""
    # Mock response where WLED explicitly reports failure
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "success": False,
        "error": "Effect not available"
    }
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test and assert exception
    with pytest.raises(WLEDCommandError) as exc_info:
        await wled_client.update_state({"seg": [{"fx": 999}]})

    assert "WLED command failed: Effect not available" in str(exc_info.value)


@pytest.mark.asyncio
async def test_state_command_missing_response_fields(wled_client, mock_session):
    """Test validation when response is missing expected fields."""
    # Mock response missing critical fields
    mock_response = AsyncMock()
    mock_response.json.return_value = {"bri": 128}  # Missing "on" field
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test and assert exception
    with pytest.raises(WLEDCommandError) as exc_info:
        await wled_client.update_state({"on": True, "bri": 128})

    assert "did not apply critical state changes" in str(exc_info.value)


@pytest.mark.asyncio
async def test_segment_command_validation(wled_client, mock_session):
    """Test segment command validation."""
    # Mock response with segment data
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "on": True,
        "seg": [{"fx": 10, "sx": 128, "ix": 64}]  # Segment with effect, speed, intensity
    }
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.update_state({"seg": [{"fx": 10, "sx": 128}]})

    # Assertions
    assert result == {"on": True, "seg": [{"fx": 10, "sx": 128, "ix": 64}]}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_playlist_activation_validation_success(wled_client, mock_session):
    """Test successful playlist activation validation."""
    # Mock response with playlist applied
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "pl": 3}
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test
    result = await wled_client.activate_playlist(3)

    # Assertions
    assert result == {"on": True, "pl": 3}
    mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_playlist_activation_validation_failure(wled_client, mock_session):
    """Test playlist activation validation failure."""
    # Mock response where playlist wasn't applied
    mock_response = AsyncMock()
    mock_response.json.return_value = {"on": True, "pl": 0}  # Playlist not applied
    mock_session.post.return_value.__aenter__.return_value = mock_response

    # Test and assert exception
    with pytest.raises(WLEDCommandError) as exc_info:
        await wled_client.activate_playlist(3)

    assert "did not apply critical state changes" in str(exc_info.value)
    assert "pl: expected 3, got 0" in str(exc_info.value)


@pytest.mark.asyncio
async def test_info_response_structure_validation(wled_client, mock_session):
    """Test info response structure validation."""
    # Mock response missing required fields
    mock_response = AsyncMock()
    mock_response.json.return_value = {"ver": "0.13.0"}  # Missing "name" field
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Test - should succeed but log warning
    result = await wled_client.get_info()

    # Assertions
    assert result == {"ver": "0.13.0"}
    mock_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_presets_response_structure_validation(wled_client, mock_session):
    """Test presets response structure validation."""
    # Mock response with invalid presets structure
    mock_response = AsyncMock()
    mock_response.json.return_value = {"invalid": "structure"}  # Missing preset data
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # Test - should succeed but log warning
    result = await wled_client.get_presets()

    # Assertions - get_presets handles validation internally
    mock_session.get.assert_called_once()