"""
WebSocket Manager — broadcasts real-time agent events to connected dashboards.
This is what makes agent work VISIBLE to users.
"""

import json
from fastapi import WebSocket
from app.models.schemas import AgentEvent


class ConnectionManager:

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, campaign_id: str):
        await websocket.accept()
        if campaign_id not in self.active_connections:
            self.active_connections[campaign_id] = []
        self.active_connections[campaign_id].append(websocket)

    def disconnect(self, websocket: WebSocket, campaign_id: str):
        if campaign_id in self.active_connections:
            self.active_connections[campaign_id].remove(websocket)
            if not self.active_connections[campaign_id]:
                del self.active_connections[campaign_id]

    async def broadcast_event(self, event: AgentEvent):
        """Push agent status update to all watchers of this campaign."""
        campaign_id = event.campaign_id
        if campaign_id in self.active_connections:
            payload = json.dumps(event.model_dump(), default=str)
            dead = []
            for ws in self.active_connections[campaign_id]:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect(ws, campaign_id)


# Singleton
ws_manager = ConnectionManager()
