"""
Pinecone Service — stores and retrieves past content + trend data.
Acts as the "memory" layer so agents learn from past campaigns.
Model loads in background thread — never blocks the pipeline.
"""

import logging
import threading
from pinecone import Pinecone, ServerlessSpec
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.config import settings

logger = logging.getLogger(__name__)


class PineconeService:

    def __init__(self):
        self._pc = None
        self._index = None
        self._embeddings = None
        self._ready = False
        self._loading = False

    def _init_sync(self):
        """Heavy init — runs in background thread."""
        try:
            logger.info("Loading HuggingFace embeddings model in background...")
            self._embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            logger.info("Embeddings model loaded")

            self._pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            index_name = settings.PINECONE_INDEX_NAME

            existing = [idx.name for idx in self._pc.list_indexes()]
            if index_name not in existing:
                self._pc.create_index(
                    name=index_name,
                    dimension=384,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
            self._index = self._pc.Index(index_name)

            self._ready = True
            logger.info("Pinecone service ready")
        except Exception as e:
            logger.error("Failed to initialize Pinecone: %s", e)
        finally:
            self._loading = False

    def start_loading(self):
        """Kick off model loading in background thread."""
        if self._ready or self._loading:
            return
        self._loading = True
        thread = threading.Thread(target=self._init_sync, daemon=True)
        thread.start()

    async def search_similar(self, query: str, top_k: int = 5, filter: dict = None):
        """Find similar past content. Returns empty if not ready yet."""
        self.start_loading()

        if not self._ready:
            logger.info("Pinecone still loading — skipping search")
            return []

        vector = self._embeddings.embed_query(query)
        results = self._index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter,
        )
        return [
            {
                "id": match.id,
                "score": match.score,
                "text": match.metadata.get("text", ""),
                "platform": match.metadata.get("platform", ""),
                "engagement": match.metadata.get("engagement", 0),
            }
            for match in results.matches
        ]

    async def store_content(self, content_id: str, text: str, metadata: dict):
        """Embed and store content. Skips if not ready yet."""
        self.start_loading()

        if not self._ready:
            logger.info("Pinecone still loading — skipping store")
            return

        vector = self._embeddings.embed_query(text)
        self._index.upsert(
            vectors=[
                {
                    "id": content_id,
                    "values": vector,
                    "metadata": {
                        "text": text,
                        **metadata,
                    },
                }
            ]
        )

    async def store_campaign_results(self, campaign_id: str, platform: str,
                                      content: str, engagement: int = 0):
        """Store completed campaign content for future learning."""
        await self.store_content(
            content_id=f"{campaign_id}_{platform}",
            text=content,
            metadata={
                "campaign_id": campaign_id,
                "platform": platform,
                "engagement": engagement,
                "type": "published_content",
            },
        )


# Singleton — instant init, model loads in background on first use
pinecone_service = PineconeService()
