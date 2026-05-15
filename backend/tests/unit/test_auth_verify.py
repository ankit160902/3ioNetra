"""Tests for the /api/auth/verify endpoint's token-only behavior.

The verify endpoint must validate the Authorization header token specifically,
NOT fall back to cookie-based auth. This prevents false positives when a valid
cookie masks a bad header token.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from routers.auth import get_verified_user


@pytest.mark.asyncio
async def test_bad_header_token_raises_401_even_with_valid_cookie():
    """get_verified_user must reject bad header tokens, ignoring cookies."""
    mock_request = MagicMock()
    mock_request.cookies = {"auth_token": "valid_cookie_token"}

    with pytest.raises(HTTPException) as exc_info:
        await get_verified_user(
            authorization="Bearer fake_token_12345",
            request=mock_request,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_no_header_raises_401():
    """get_verified_user must reject requests with no Authorization header."""
    mock_request = MagicMock()
    mock_request.cookies = {"auth_token": "valid_cookie_token"}

    with pytest.raises(HTTPException) as exc_info:
        await get_verified_user(
            authorization=None,
            request=mock_request,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_valid_header_token_succeeds():
    """get_verified_user returns user dict for a valid header token."""
    mock_request = MagicMock()
    mock_request.cookies = {}

    fake_user = {"id": "u123", "name": "Test", "email": "t@t.com", "created_at": "2026-01-01"}
    with patch("routers.auth.get_auth_service") as mock_auth:
        mock_auth.return_value.verify_token.return_value = fake_user
        user = await get_verified_user(
            authorization="Bearer real_token_abc",
            request=mock_request,
        )
    assert user["id"] == "u123"
