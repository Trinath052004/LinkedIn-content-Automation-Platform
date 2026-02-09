"""
🚀 LINKEDIN COMMAND CENTER — FastAPI App
=============================================
POST /campaigns         → Launch a new multi-agent campaign
POST /campaigns/sync    → Launch and wait for completion
GET  /campaigns/{id}    → Get campaign results
GET  /campaigns         → List recent campaigns
WS   /ws/{campaign_id}  → Real-time agent status stream
GET  /                  → Live dashboard UI
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from pathlib import Path

from app.config import settings
from app.models.schemas import CampaignRequest, CampaignResponse
from app.agents.orchestrator import run_campaign
from app.services.websocket_manager import ws_manager
from app.services.redis_service import redis_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: connect and disconnect Redis."""
    await redis_service.connect()
    logger.info("LinkedIn Command Center started")
    yield
    await redis_service.disconnect()
    logger.info("LinkedIn Command Center stopped")


app = FastAPI(
    title="🎯 LinkedIn Command Center",
    description="Multi-agent AI system that researches, writes, and publishes LinkedIn content.",
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================
# CORS Middleware
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# API Key Auth (optional — skip if API_KEY not set)
# ============================================
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)):
    """Verify API key if one is configured. Skip auth if API_KEY is empty."""
    if not settings.API_KEY:
        return  # No API key configured — allow all requests
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ============================================
# REST Endpoints
# ============================================

@app.post("/campaigns", response_model=dict, dependencies=[Depends(verify_api_key)])
async def create_campaign(request: CampaignRequest, background_tasks: BackgroundTasks):
    """
    Launch a new campaign. Returns campaign_id immediately.
    Connect to WebSocket /ws/{campaign_id} to watch agents work in real-time.
    """
    campaign_id = str(uuid.uuid4())[:8]

    async def _run():
        result = await run_campaign(request, campaign_id=campaign_id)
        await redis_service.store_campaign(result)

    background_tasks.add_task(_run)

    return {
        "message": "Campaign launched! Connect to WebSocket to watch agents work.",
        "campaign_id": campaign_id,
        "websocket_url": f"/ws/{campaign_id}",
    }


@app.post("/campaigns/sync", response_model=CampaignResponse, dependencies=[Depends(verify_api_key)])
async def create_campaign_sync(request: CampaignRequest):
    """
    Launch a campaign and wait for completion (synchronous).
    Use this for testing or when you don't need real-time updates.
    """
    result = await run_campaign(request)
    await redis_service.store_campaign(result)
    return result


@app.get("/campaigns/{campaign_id}", dependencies=[Depends(verify_api_key)])
async def get_campaign(campaign_id: str):
    """Get results of a completed campaign."""
    campaign = await redis_service.get_campaign(campaign_id)
    if campaign:
        return campaign
    return {"status": "running or not found", "campaign_id": campaign_id}


@app.get("/campaigns", response_model=list[CampaignResponse], dependencies=[Depends(verify_api_key)])
async def list_campaigns():
    """List recent campaigns (up to 20)."""
    return await redis_service.list_campaigns()


@app.get("/health")
async def health():
    redis_ok = await redis_service.is_healthy()
    return {
        "status": "healthy" if redis_ok else "degraded",
        "agents": 3,
        "redis": "connected" if redis_ok else "disconnected",
        "service": "LinkedIn Command Center",
    }


# ============================================
# WebSocket — Real-time agent event stream
# ============================================

@app.websocket("/ws/{campaign_id}")
async def websocket_endpoint(websocket: WebSocket, campaign_id: str):
    """
    Connect here to watch agents work in real-time.
    Receives JSON events like:
    {
        "agent": "writer_agent",
        "status": "running",
        "platform": "linkedin",
        "message": "✍️ Writing LinkedIn post..."
    }
    """
    await ws_manager.connect(websocket, campaign_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, campaign_id)


# ============================================
# Dashboard UI
# ============================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the live dashboard."""
    html_path = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    return HTMLResponse(content="""
    <html><body>
        <h1>🎯 LinkedIn Command Center</h1>
        <p>Dashboard not found. Place frontend/index.html in the project root.</p>
        <p>API docs: <a href="/docs">/docs</a></p>
    </body></html>
    """)
