"""
✍️ WRITER AGENT
Takes the strategic brief from Trend Agent and generates
LinkedIn-specific content (professional tone, hooks, CTAs).
"""

import asyncio
import json
import logging
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.models.schemas import AgentEvent, AgentName, AgentStatus, Platform, ContentPiece
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


LINKEDIN_RULES = {
    "max_chars": 3000,
    "style": "Professional, thought-leadership. Use line breaks for readability. Start with a hook. End with a CTA or question.",
    "format": "Single post with line breaks",
}


class WriterAgent:

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.7,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert LinkedIn copywriter. Write content
            following the platform rules EXACTLY.

            Return ONLY valid JSON:
            {{
                "content": "the post text",
                "hashtags": ["tag1", "tag2"]
            }}"""),
            ("human", """
Platform: LinkedIn
Platform Rules: {platform_rules}
Max Characters: {max_chars}

Strategic Brief:
{brief}

Topic: {topic}
Tone: {tone}
Target Audience: {target_audience}

Write the content now. Return ONLY JSON."""),
        ])

    async def run(self, campaign_id: str, topic: str, tone: str,
                  target_audience: str, platforms: list[Platform],
                  brief: str) -> list[ContentPiece]:
        """Generate LinkedIn content."""
        content_pieces = []

        for platform in platforms:
            await ws_manager.broadcast_event(AgentEvent(
                campaign_id=campaign_id,
                agent=AgentName.WRITER,
                status=AgentStatus.RUNNING,
                platform=platform,
                message="✍️ Writing LinkedIn post...",
            ))
            await asyncio.sleep(0.5)

            chain = self.prompt | self.llm
            result = await chain.ainvoke({
                "platform_rules": LINKEDIN_RULES["style"],
                "max_chars": LINKEDIN_RULES["max_chars"],
                "brief": brief,
                "topic": topic,
                "tone": tone,
                "target_audience": target_audience,
            })

            # Parse LLM response
            try:
                raw = result.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
                parsed = json.loads(raw)
            except (json.JSONDecodeError, IndexError):
                parsed = {
                    "content": result.content,
                    "hashtags": [],
                }

            content_text = parsed.get("content", "")
            if len(content_text) > LINKEDIN_RULES["max_chars"]:
                content_text = content_text[:LINKEDIN_RULES["max_chars"]]
                logger.warning("Content exceeded %d chars, truncated", LINKEDIN_RULES["max_chars"])

            piece = ContentPiece(
                platform=platform,
                content=content_text,
                hashtags=parsed.get("hashtags", []),
            )
            content_pieces.append(piece)

            await ws_manager.broadcast_event(AgentEvent(
                campaign_id=campaign_id,
                agent=AgentName.WRITER,
                status=AgentStatus.COMPLETED,
                platform=platform,
                message=f"✅ LinkedIn content ready ({len(piece.content)} chars)",
                data={
                    "preview": piece.content[:150],
                    "hashtags": piece.hashtags,
                },
            ))

        return content_pieces


writer_agent = WriterAgent()
