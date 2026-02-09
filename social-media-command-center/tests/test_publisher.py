"""Tests for the Publisher Agent."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.publisher_agent import PublisherAgent
from app.models.schemas import ContentPiece, Platform


@pytest.fixture
def publisher():
    return PublisherAgent()


@pytest.fixture
def sample_piece():
    return ContentPiece(
        platform=Platform.LINKEDIN,
        content="This is a test LinkedIn post about AI trends.",
        hashtags=["AI", "LinkedIn"],
    )


@pytest.fixture
def mock_ws():
    with patch("app.agents.publisher_agent.ws_manager") as mock:
        mock.broadcast_event = AsyncMock()
        yield mock


@pytest.fixture
def mock_pinecone():
    with patch("app.agents.publisher_agent.pinecone_service") as mock:
        mock.store_campaign_results = AsyncMock()
        yield mock


@pytest.mark.asyncio
async def test_draft_mode(publisher, sample_piece, mock_ws, mock_pinecone):
    """Draft mode should not call LinkedIn API."""
    result = await publisher.run("camp1", [sample_piece], auto_publish=False)
    assert len(result) == 1
    assert result[0].published is False
    mock_pinecone.store_campaign_results.assert_called_once()


@pytest.mark.asyncio
async def test_publish_no_token(publisher, sample_piece):
    """Publishing without a token should return False."""
    publisher._access_token = ""
    result = await publisher._publish_linkedin(sample_piece)
    assert result is False


@pytest.mark.asyncio
async def test_content_truncation(publisher):
    """Content exceeding 3000 chars should be truncated."""
    long_content = "A" * 3500
    piece = ContentPiece(platform=Platform.LINKEDIN, content=long_content)

    # We test that the method doesn't crash with long content
    # (it will fail on API call since no real token, but truncation happens before that)
    publisher._access_token = "fake-token"
    publisher._cached_user_urn = "urn:li:person:test123"

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=201))
        mock_client_cls.return_value = mock_client

        result = await publisher._publish_linkedin(piece)
        assert result is True

        # Verify the posted text was truncated
        call_kwargs = mock_client.post.call_args
        posted_text = call_kwargs.kwargs["json"]["commentary"]
        assert len(posted_text) <= 3000


@pytest.mark.asyncio
async def test_refresh_token_on_401(publisher):
    """Should attempt token refresh when getting 401."""
    publisher._access_token = "expired-token"
    publisher._cached_user_urn = "urn:li:person:test123"

    mock_401 = MagicMock(status_code=401, text="Unauthorized")
    mock_201 = MagicMock(status_code=201)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        # First call returns 401, second returns 201 after refresh
        mock_client.post = AsyncMock(side_effect=[mock_401, mock_201])
        mock_client.get = AsyncMock(return_value=MagicMock(
            status_code=200, json=lambda: {"sub": "test123"}
        ))
        mock_client_cls.return_value = mock_client

        with patch.object(publisher, "_refresh_token", new_callable=AsyncMock, return_value=True):
            piece = ContentPiece(platform=Platform.LINKEDIN, content="Test")
            result = await publisher._publish_linkedin(piece)
            assert result is True
