"""
📤 PUBLISHER AGENT
Posts content to LinkedIn via the REST API.
Supports draft mode (just saves) and live publish mode.
Handles token refresh when access tokens expire.
"""

import asyncio
import logging
import os
import httpx
from app.config import settings
from app.models.schemas import (
    AgentEvent, AgentName, AgentStatus, Platform, ContentPiece,
)
from app.services.pinecone_service import pinecone_service
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


class PublisherAgent:

    def __init__(self):
        self._cached_user_urn: str | None = None
        self._access_token: str = settings.LINKEDIN_ACCESS_TOKEN

    async def run(self, campaign_id: str, content_pieces: list[ContentPiece],
                  auto_publish: bool = False) -> list[ContentPiece]:
        """Publish or save content for LinkedIn."""

        for piece in content_pieces:
            platform = piece.platform

            if auto_publish:
                await ws_manager.broadcast_event(AgentEvent(
                    campaign_id=campaign_id,
                    agent=AgentName.PUBLISHER,
                    status=AgentStatus.RUNNING,
                    platform=platform,
                    message="📤 Publishing to LinkedIn...",
                ))
                await asyncio.sleep(0.5)

                success = await self._publish_linkedin(piece)

                if success:
                    piece.published = True
                    await ws_manager.broadcast_event(AgentEvent(
                        campaign_id=campaign_id,
                        agent=AgentName.PUBLISHER,
                        status=AgentStatus.COMPLETED,
                        platform=platform,
                        message="✅ Published to LinkedIn!",
                    ))
                else:
                    await ws_manager.broadcast_event(AgentEvent(
                        campaign_id=campaign_id,
                        agent=AgentName.PUBLISHER,
                        status=AgentStatus.FAILED,
                        platform=platform,
                        message="⚠️ Failed to publish to LinkedIn. Saved as draft.",
                    ))
            else:
                await ws_manager.broadcast_event(AgentEvent(
                    campaign_id=campaign_id,
                    agent=AgentName.PUBLISHER,
                    status=AgentStatus.COMPLETED,
                    platform=platform,
                    message="💾 LinkedIn content saved as draft (auto-publish off)",
                ))

            # Store in Pinecone for future learning
            await pinecone_service.store_campaign_results(
                campaign_id=campaign_id,
                platform=platform.value,
                content=piece.content,
            )

        return content_pieces

    async def _refresh_token(self) -> bool:
        """Refresh the LinkedIn access token using the refresh token."""
        if not settings.LINKEDIN_REFRESH_TOKEN or not settings.LINKEDIN_CLIENT_ID:
            logger.warning("Cannot refresh token — missing LINKEDIN_REFRESH_TOKEN or LINKEDIN_CLIENT_ID")
            return False

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://www.linkedin.com/oauth/v2/accessToken",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": settings.LINKEDIN_REFRESH_TOKEN,
                        "client_id": settings.LINKEDIN_CLIENT_ID,
                        "client_secret": settings.LINKEDIN_CLIENT_SECRET,
                    },
                )

                if resp.status_code != 200:
                    logger.error("Token refresh failed: %s %s", resp.status_code, resp.text)
                    return False

                data = resp.json()
                self._access_token = data["access_token"]

                # Update the refresh token if a new one was returned
                new_refresh = data.get("refresh_token")
                if new_refresh:
                    settings.LINKEDIN_REFRESH_TOKEN = new_refresh
                    os.environ["LINKEDIN_REFRESH_TOKEN"] = new_refresh

                # Persist the new access token in env for this process
                settings.LINKEDIN_ACCESS_TOKEN = self._access_token
                os.environ["LINKEDIN_ACCESS_TOKEN"] = self._access_token

                # Clear cached URN since token changed
                self._cached_user_urn = None

                logger.info("LinkedIn access token refreshed successfully")
                return True

        except httpx.HTTPError as e:
            logger.error("Token refresh request failed: %s", e)
            return False

    async def _get_user_urn(self, client: httpx.AsyncClient) -> str | None:
        """Fetch and cache the LinkedIn user URN."""
        if self._cached_user_urn:
            return self._cached_user_urn

        try:
            resp = await client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            if resp.status_code != 200:
                logger.error("Failed to fetch LinkedIn user info: %s %s", resp.status_code, resp.text)
                return None

            user_sub = resp.json().get("sub", "")
            if user_sub:
                self._cached_user_urn = f"urn:li:person:{user_sub}"
            return self._cached_user_urn
        except httpx.HTTPError as e:
            logger.error("LinkedIn userinfo request failed: %s", e)
            return None

    async def _publish_linkedin(self, piece: ContentPiece, max_retries: int = 3) -> bool:
        """Post to LinkedIn via the Posts API with retry logic and token refresh."""
        if not self._access_token:
            logger.warning("No LINKEDIN_ACCESS_TOKEN configured")
            return False

        text = piece.content
        if piece.hashtags:
            tags = " ".join(f"#{t}" for t in piece.hashtags)
            text = f"{text}\n\n{tags}"

        # Enforce LinkedIn's 3000 char limit
        text = text[:3000]

        async with httpx.AsyncClient(timeout=30.0) as client:
            author = await self._get_user_urn(client)
            if not author:
                return False

            payload = {
                "author": author,
                "commentary": text,
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "lifecycleState": "PUBLISHED",
            }

            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
                "LinkedIn-Version": "202401",
                "X-Restli-Protocol-Version": "2.0.0",
            }

            token_refreshed = False

            for attempt in range(1, max_retries + 1):
                try:
                    resp = await client.post(
                        "https://api.linkedin.com/rest/posts",
                        headers=headers,
                        json=payload,
                    )

                    if resp.status_code in (200, 201):
                        logger.info("LinkedIn post published successfully")
                        return True

                    # Token expired — try refresh once
                    if resp.status_code == 401 and not token_refreshed:
                        logger.info("Access token expired, attempting refresh...")
                        refreshed = await self._refresh_token()
                        if refreshed:
                            token_refreshed = True
                            headers["Authorization"] = f"Bearer {self._access_token}"
                            # Re-fetch user URN with new token
                            author = await self._get_user_urn(client)
                            if author:
                                payload["author"] = author
                            continue
                        else:
                            logger.error("Token refresh failed — cannot publish")
                            return False

                    # Other auth error — don't retry
                    if resp.status_code == 403:
                        logger.error("LinkedIn 403 Forbidden — check app permissions")
                        return False

                    logger.error(
                        "LinkedIn publish attempt %d/%d failed: %s %s",
                        attempt, max_retries, resp.status_code, resp.text,
                    )

                except httpx.HTTPError as e:
                    logger.error("LinkedIn publish attempt %d/%d error: %s", attempt, max_retries, e)

                if attempt < max_retries:
                    wait = 2 ** attempt
                    logger.info("Retrying in %ds...", wait)
                    await asyncio.sleep(wait)

            return False


publisher_agent = PublisherAgent()
