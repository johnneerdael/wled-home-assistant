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