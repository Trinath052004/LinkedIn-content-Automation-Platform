"""
🔍 TREND AGENT
Analyzes trending topics, searches past high-performing content in Pinecone,
and generates strategic insights for the Writer Agent.
"""

import asyncio
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.models.schemas import AgentEvent, AgentName, AgentStatus
from app.services.pinecone_service import pinecone_service
from app.services.websocket_manager import ws_manager


class TrendAgent:

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.3,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a LinkedIn content trend analyst. Given a topic and
            past high-performing content, produce a strategic brief that includes:
            1. Key angles that resonate with the target audience on LinkedIn
            2. Trending hooks and formats (thought leadership, storytelling, hot takes)
            3. Hashtag recommendations for LinkedIn
            4. What to AVOID based on oversaturated angles

            Be specific and actionable. No fluff."""),
            ("human", """
Topic: {topic}
Target Audience: {target_audience}
Tone: {tone}
Platforms: {platforms}

Past high-performing content on similar topics:
{past_content}

Generate a strategic content brief."""),
        ])

    async def run(self, campaign_id: str, topic: str, target_audience: str,
                  tone: str, platforms: list[str]) -> str:
        """Analyze trends and return a strategic brief."""

        # -- Step 1: Broadcast "I'm starting" --
        await ws_manager.broadcast_event(AgentEvent(
            campaign_id=campaign_id,
            agent=AgentName.TREND,
            status=AgentStatus.RUNNING,
            message=f"🔍 Searching past content for '{topic}'...",
        ))
        await asyncio.sleep(1)  # small delay for visual effect

        # -- Step 2: Search Pinecone for similar past content --
        past_results = await pinecone_service.search_similar(
            query=topic, top_k=5
        )

        past_content_str = "\n".join([
            f"- [Platform: {r['platform']}, Engagement: {r['engagement']}] {r['text'][:200]}"
            for r in past_results
        ]) if past_results else "No past content found — this is a fresh topic."

        await ws_manager.broadcast_event(AgentEvent(
            campaign_id=campaign_id,
            agent=AgentName.TREND,
            status=AgentStatus.RUNNING,
            message=f"📊 Found {len(past_results)} similar past posts. Analyzing trends...",
        ))
        await asyncio.sleep(1)

        # -- Step 3: Generate strategic brief --
        chain = self.prompt | self.llm
        result = await chain.ainvoke({
            "topic": topic,
            "target_audience": target_audience,
            "tone": tone,
            "platforms": ", ".join(platforms),
            "past_content": past_content_str,
        })

        brief = result.content

        # -- Step 4: Broadcast completion --
        await ws_manager.broadcast_event(AgentEvent(
            campaign_id=campaign_id,
            agent=AgentName.TREND,
            status=AgentStatus.COMPLETED,
            message="✅ Trend analysis complete. Strategic brief ready.",
            data={"brief_preview": brief[:200]},
        ))

        return brief


trend_agent = TrendAgent()
