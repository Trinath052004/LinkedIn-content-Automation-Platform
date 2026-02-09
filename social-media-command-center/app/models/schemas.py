from pydantic import BaseModel
from typing import Optional
from enum import Enum


# ============================================
# Enums
# ============================================

class Platform(str, Enum):
    LINKEDIN = "linkedin"


class AgentStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentName(str, Enum):
    TREND = "trend_agent"
    WRITER = "writer_agent"
    PUBLISHER = "publisher_agent"


# ============================================
# Request / Response Models
# ============================================

class CampaignRequest(BaseModel):
    topic: str
    platforms: list[Platform] = [Platform.LINKEDIN]
    tone: str = "professional"
    target_audience: str = "tech professionals"
    auto_publish: bool = False  # safety: default to draft mode


class AgentEvent(BaseModel):
    """Real-time event pushed via WebSocket"""
    campaign_id: str
    agent: AgentName
    status: AgentStatus
    platform: Optional[Platform] = None
    message: str
    data: Optional[dict] = None


class ContentPiece(BaseModel):
    platform: Platform
    content: str
    hashtags: list[str] = []
    scheduled_time: Optional[str] = None
    published: bool = False


class CampaignResponse(BaseModel):
    campaign_id: str
    topic: str
    status: str
    content: list[ContentPiece] = []
    trend_insights: Optional[str] = None
