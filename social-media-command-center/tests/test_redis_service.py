"""Tests for the Redis service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.redis_service import RedisService
from app.models.schemas import CampaignResponse, ContentPiece, Platform


@pytest.fixture
def redis_svc():
    return RedisService()


@pytest.fixture
def sample_campaign():
    return CampaignResponse(
        campaign_id="test1",
        topic="AI agents",
        status="completed",
        content=[ContentPiece(platform=Platform.LINKEDIN, content="Hello")],
        trend_insights="Use hooks",
    )


@pytest.mark.asyncio
async def test_store_and_get_without_connection(redis_svc, sample_campaign):
    """Should gracefully handle missing Redis connection."""
    await redis_svc.store_campaign(sample_campaign)  # should not crash
    result = await redis_svc.get_campaign("test1")
    assert result is None


@pytest.mark.asyncio
async def test_is_healthy_no_connection(redis_svc):
    assert await redis_svc.is_healthy() is False


@pytest.mark.asyncio
async def test_store_and_get_with_mock_redis(redis_svc, sample_campaign):
    """Should store and retrieve via Redis."""
    store = {}

    async def mock_set(key, value, ex=None):
        store[key] = value

    async def mock_get(key):
        return store.get(key)

    mock_client = AsyncMock()
    mock_client.set = mock_set
    mock_client.get = mock_get
    mock_client.ping = AsyncMock()
    redis_svc._client = mock_client

    await redis_svc.store_campaign(sample_campaign)
    result = await redis_svc.get_campaign("test1")

    assert result is not None
    assert result.campaign_id == "test1"
    assert result.topic == "AI agents"
    assert result.content[0].content == "Hello"


@pytest.mark.asyncio
async def test_list_campaigns_empty(redis_svc):
    """Should return empty list when no connection."""
    result = await redis_svc.list_campaigns()
    assert result == []


@pytest.mark.asyncio
async def test_is_healthy_with_connection(redis_svc):
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    redis_svc._client = mock_client

    assert await redis_svc.is_healthy() is True


@pytest.mark.asyncio
async def test_is_healthy_ping_fails(redis_svc):
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(side_effect=Exception("connection lost"))
    redis_svc._client = mock_client

    assert await redis_svc.is_healthy() is False
