"""
Tests for the attack CLI module.

Validates inject_fault and get_system_state HTTP client functions.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from attacks.main import inject_fault, get_system_state


@pytest.mark.asyncio
async def test_inject_fault():
    """inject_fault should POST to /inject with correct query params."""
    with patch("attacks.main.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        await inject_fault("c-001", "ddos", 5000)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        url = call_args[0][0]
        params = call_args[1].get("params", {})

        assert "/inject" in url
        assert params["target_id"] == "c-001"
        assert params["attack_type"] == "ddos"
        assert params["duration_ms"] == 5000


@pytest.mark.asyncio
async def test_get_system_state():
    """get_system_state should GET /state and return JSON."""
    with patch("attacks.main.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"containers": [], "tick": 42}
        mock_client.get.return_value = mock_response

        data = await get_system_state()

        assert data is not None
        assert data["containers"] == []
        assert data["tick"] == 42
