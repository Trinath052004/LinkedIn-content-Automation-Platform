"""Tests for Pydantic schemas and data models."""

import pytest
from app.models.schemas import (
    Platform, AgentStatus, AgentName,
    CampaignRequest, CampaignResponse, ContentPiece, AgentEvent,
)


class TestPlatformEnum:

    def test_linkedin_value(self):
        assert Platform.LINKEDIN.value == "linkedin"

    def test_only_linkedin(self):
        assert len(Platform) == 1


class TestCampaignRequest:

    def test_defaults(self):
        req = CampaignRequest(topic="AI trends")
        assert req.topic == "AI trends"
        assert req.platforms == [Platform.LINKEDIN]
        assert req.tone == "professional"
        assert req.target_audience == "tech professionals"
        assert req.auto_publish is False

    def test_custom_values(self):
        req = CampaignRequest(
            topic="Remote work",
            tone="casual",
            target_audience="HR managers",
            auto_publish=True,
        )
        assert req.tone == "casual"
        assert req.auto_publish is True

    def test_topic_required(self):
        with pytest.raises(Exception):
            CampaignRequest()


class TestContentPiece:

    def test_defaults(self):
        piece = ContentPiece(platform=Platform.LINKEDIN, content="Hello world")
        assert piece.hashtags == []
        assert piece.scheduled_time is None
        assert piece.published is False

    def test_with_hashtags(self):
        piece = ContentPiece(
            platform=Platform.LINKEDIN,
            content="Test",
            hashtags=["ai", "tech"],
        )
        assert piece.hashtags == ["ai", "tech"]


class TestCampaignResponse:

    def test_minimal(self):
        resp = CampaignResponse(
            campaign_id="abc123",
            topic="AI",
            status="completed",
        )
        assert resp.content == []
        assert resp.trend_insights is None

    def test_full(self):
        piece = ContentPiece(platform=Platform.LINKEDIN, content="Post text")
        resp = CampaignResponse(
            campaign_id="abc123",
            topic="AI",
            status="completed",
            content=[piece],
            trend_insights="Use hooks",
        )
        assert len(resp.content) == 1
        assert resp.trend_insights == "Use hooks"

    def test_json_roundtrip(self):
        piece = ContentPiece(platform=Platform.LINKEDIN, content="Hello")
        resp = CampaignResponse(
            campaign_id="x1",
            topic="Test",
            status="completed",
            content=[piece],
        )
        json_str = resp.model_dump_json()
        restored = CampaignResponse.model_validate_json(json_str)
        assert restored.campaign_id == "x1"
        assert restored.content[0].content == "Hello"


class TestAgentEvent:

    def test_minimal(self):
        event = AgentEvent(
            campaign_id="abc",
            agent=AgentName.TREND,
            status=AgentStatus.RUNNING,
            message="Analyzing...",
        )
        assert event.platform is None
        assert event.data is None

    def test_with_platform(self):
        event = AgentEvent(
            campaign_id="abc",
            agent=AgentName.WRITER,
            status=AgentStatus.COMPLETED,
            platform=Platform.LINKEDIN,
            message="Done",
            data={"preview": "text"},
        )
        assert event.platform == Platform.LINKEDIN
        assert event.data["preview"] == "text"
