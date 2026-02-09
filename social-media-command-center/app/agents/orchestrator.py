"""
🎯 ORCHESTRATOR
Chains all 3 agents in sequence:
  Trend → Writer → Publisher

Each step broadcasts real-time events so the dashboard stays alive.
If any agent fails, the error is broadcast and the pipeline stops gracefully.
"""

import logging
import uuid
from app.models.schemas import CampaignRequest, CampaignResponse, AgentEvent, AgentName, AgentStatus
from app.agents.trend_agent import trend_agent
from app.agents.writer_agent import writer_agent
from app.agents.publisher_agent import publisher_agent
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


async def run_campaign(request: CampaignRequest, campaign_id: str | None = None) -> CampaignResponse:
    """Execute the full multi-agent pipeline with error handling."""

    if not campaign_id:
        campaign_id = str(uuid.uuid4())[:8]
    platforms = request.platforms

    # =============================================
    # AGENT 1: Trend Analysis
    # =============================================
    try:
        brief = await trend_agent.run(
            campaign_id=campaign_id,
            topic=request.topic,
            target_audience=request.target_audience,
            tone=request.tone,
            platforms=[p.value for p in platforms],
        )
    except Exception as e:
        logger.error("Trend Agent failed for campaign %s: %s", campaign_id, e)
        await ws_manager.broadcast_event(AgentEvent(
            campaign_id=campaign_id,
            agent=AgentName.TREND,
            status=AgentStatus.FAILED,
            message=f"❌ Trend Agent failed: {e}",
            data={"final": True},
        ))
        return CampaignResponse(
            campaign_id=campaign_id,
            topic=request.topic,
            status="failed",
            trend_insights=f"Error: {e}",
        )

    # =============================================
    # AGENT 2: Content Writing
    # =============================================
    try:
        content_pieces = await writer_agent.run(
            campaign_id=campaign_id,
            topic=request.topic,
            tone=request.tone,
            target_audience=request.target_audience,
            platforms=platforms,
            brief=brief,
        )
    except Exception as e:
        logger.error("Writer Agent failed for campaign %s: %s", campaign_id, e)
        await ws_manager.broadcast_event(AgentEvent(
            campaign_id=campaign_id,
            agent=AgentName.WRITER,
            status=AgentStatus.FAILED,
            message=f"❌ Writer Agent failed: {e}",
            data={"final": True},
        ))
        return CampaignResponse(
            campaign_id=campaign_id,
            topic=request.topic,
            status="failed",
            trend_insights=brief,
        )

    # =============================================
    # AGENT 3: Publishing
    # =============================================
    try:
        content_pieces = await publisher_agent.run(
            campaign_id=campaign_id,
            content_pieces=content_pieces,
            auto_publish=request.auto_publish,
        )
    except Exception as e:
        logger.error("Publisher Agent failed for campaign %s: %s", campaign_id, e)
        await ws_manager.broadcast_event(AgentEvent(
            campaign_id=campaign_id,
            agent=AgentName.PUBLISHER,
            status=AgentStatus.FAILED,
            message=f"❌ Publisher Agent failed: {e}",
            data={"final": True},
        ))
        return CampaignResponse(
            campaign_id=campaign_id,
            topic=request.topic,
            status="failed",
            content=content_pieces,
            trend_insights=brief,
        )

    # =============================================
    # DONE — Return final response
    # =============================================
    await ws_manager.broadcast_event(AgentEvent(
        campaign_id=campaign_id,
        agent=AgentName.PUBLISHER,
        status=AgentStatus.COMPLETED,
        message="🎉 Campaign complete! All content ready.",
        data={"final": True},
    ))

    return CampaignResponse(
        campaign_id=campaign_id,
        topic=request.topic,
        status="completed",
        content=content_pieces,
        trend_insights=brief,
    )
