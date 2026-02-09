"""Tests for FastAPI endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.schemas import CampaignResponse, ContentPiece, Platform


@pytest.fixture
def mock_redis():
    """Mock redis_service for all API tests."""
    with patch("app.main.redis_service") as mock:
        mock.connect = AsyncMock()
        mock.disconnect = AsyncMock()
        mock.is_healthy = AsyncMock(return_value=True)
        mock.store_campaign = AsyncMock()
        mock.get_campaign = AsyncMock(return_value=None)
        mock.list_campaigns = AsyncMock(return_value=[])
        yield mock


@pytest.fixture
async def client(mock_redis):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_endpoint(client, mock_redis):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agents"] == 3
    assert data["service"] == "LinkedIn Command Center"
    assert data["redis"] == "connected"


@pytest.mark.asyncio
async def test_health_redis_down(client, mock_redis):
    mock_redis.is_healthy = AsyncMock(return_value=False)
    resp = await client.get("/health")
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["redis"] == "disconnected"


@pytest.mark.asyncio
async def test_get_campaign_not_found(client, mock_redis):
    resp = await client.get("/campaigns/nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running or not found"


@pytest.mark.asyncio
async def test_get_campaign_found(client, mock_redis):
    campaign = CampaignResponse(
        campaign_id="test123",
        topic="AI trends",
        status="completed",
        content=[ContentPiece(platform=Platform.LINKEDIN, content="Hello LinkedIn")],
    )
    mock_redis.get_campaign = AsyncMock(return_value=campaign)

    resp = await client.get("/campaigns/test123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["campaign_id"] == "test123"
    assert data["content"][0]["content"] == "Hello LinkedIn"


@pytest.mark.asyncio
async def test_list_campaigns_empty(client, mock_redis):
    resp = await client.get("/campaigns")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_campaigns_with_data(client, mock_redis):
    campaigns = [
        CampaignResponse(campaign_id="a1", topic="Topic 1", status="completed"),
        CampaignResponse(campaign_id="a2", topic="Topic 2", status="completed"),
    ]
    mock_redis.list_campaigns = AsyncMock(return_value=campaigns)

    resp = await client.get("/campaigns")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_dashboard_serves_html(client, mock_redis):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "LinkedIn Command Center" in resp.text


@pytest.mark.asyncio
async def test_sync_campaign(client, mock_redis):
    mock_response = CampaignResponse(
        campaign_id="sync1",
        topic="Test topic",
        status="completed",
        content=[ContentPiece(platform=Platform.LINKEDIN, content="Post")],
    )

    with patch("app.main.run_campaign", new_callable=AsyncMock, return_value=mock_response):
        resp = await client.post("/campaigns/sync", json={
            "topic": "Test topic",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["campaign_id"] == "sync1"
        assert data["status"] == "completed"
