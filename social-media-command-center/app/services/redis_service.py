"""
🗄️ REDIS SERVICE
Persistent campaign storage using Redis.
Replaces the in-memory dict so data survives restarts.
"""

import json
import logging
import redis.asyncio as redis
from app.config import settings
from app.models.schemas import CampaignResponse

logger = logging.getLogger(__name__)

CAMPAIGN_KEY_PREFIX = "campaign:"
CAMPAIGN_TTL = 60 * 60 * 24 * 7  # 7 days


class RedisService:

    def __init__(self):
        self._client: redis.Redis | None = None

    async def connect(self):
        """Initialize the Redis connection."""
        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            await self._client.ping()
            logger.info("Connected to Redis at %s", settings.REDIS_URL)
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            self._client = None

    async def disconnect(self):
        """Close the Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def is_healthy(self) -> bool:
        """Check if Redis is reachable."""
        if not self._client:
            return False
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    async def store_campaign(self, campaign: CampaignResponse) -> None:
        """Store a campaign result in Redis."""
        if not self._client:
            logger.warning("Redis not available — campaign %s not persisted", campaign.campaign_id)
            return

        key = f"{CAMPAIGN_KEY_PREFIX}{campaign.campaign_id}"
        data = campaign.model_dump_json()
        await self._client.set(key, data, ex=CAMPAIGN_TTL)
        logger.info("Stored campaign %s in Redis (TTL: %ds)", campaign.campaign_id, CAMPAIGN_TTL)

    async def get_campaign(self, campaign_id: str) -> CampaignResponse | None:
        """Retrieve a campaign result from Redis."""
        if not self._client:
            return None

        key = f"{CAMPAIGN_KEY_PREFIX}{campaign_id}"
        data = await self._client.get(key)
        if not data:
            return None

        return CampaignResponse.model_validate_json(data)

    async def list_campaigns(self, limit: int = 20) -> list[CampaignResponse]:
        """List recent campaigns."""
        if not self._client:
            return []

        keys = []
        async for key in self._client.scan_iter(match=f"{CAMPAIGN_KEY_PREFIX}*", count=100):
            keys.append(key)
            if len(keys) >= limit:
                break

        campaigns = []
        for key in keys:
            data = await self._client.get(key)
            if data:
                campaigns.append(CampaignResponse.model_validate_json(data))

        return campaigns


redis_service = RedisService()
