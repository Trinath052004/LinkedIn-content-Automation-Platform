# 🎯 LinkedIn Command Center

**A multi-agent AI system that researches, writes, and publishes LinkedIn content — with a real-time dashboard to watch every agent work.**

![Stack](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Stack](https://img.shields.io/badge/LangChain-121212?style=flat)
![Stack](https://img.shields.io/badge/Pinecone-000?style=flat)
![Stack](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

---

## How It Works

```
User enters topic
        │
        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  🔍 Trend Agent │ ──▶ │  ✍️ Writer Agent │ ──▶ │  📤 Publisher    │
│                 │     │                 │     │     Agent        │
│ Searches past   │     │ Writes LinkedIn │     │ Posts or saves   │
│ content in      │     │ posts with      │     │ as drafts.       │
│ Pinecone.       │     │ hooks, CTAs,    │     │ Stores results   │
│ Produces a      │     │ and hashtags.   │     │ in Pinecone for  │
│ strategic brief.│     │                 │     │ future learning. │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        └───────────────────────┴───────────────────────┘
                                │
                           WebSocket
                                │
                        ┌───────▼────────┐
                        │  📡 Live        │
                        │  Dashboard      │
                        │  (Real-time     │
                        │   agent feed)   │
                        └─────────────────┘
```

Every agent broadcasts its status via **WebSocket**, so users can watch the entire pipeline execute in real-time on the dashboard.

---

## Quick Start

### 1. Clone & Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Required keys:**
- `ANTHROPIC_API_KEY` — for LLM (Claude)
- `PINECONE_API_KEY` — for content memory / vector search

**Optional keys (for auto-publishing):**
- `LINKEDIN_ACCESS_TOKEN` — to post on LinkedIn

### 2. Run with Docker

```bash
docker-compose up --build
```

### 3. Open Dashboard

Go to **http://localhost:8000** — you'll see the live command center.

Or use the API directly at **http://localhost:8000/docs**.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/campaigns` | Launch campaign (async, returns immediately) |
| `POST` | `/campaigns/sync` | Launch campaign (waits for completion) |
| `GET` | `/campaigns/{id}` | Get campaign results |
| `WS` | `/ws/{campaign_id}` | Real-time agent event stream |
| `GET` | `/health` | Health check |
| `GET` | `/` | Live dashboard UI |

### Example Request

```bash
curl -X POST http://localhost:8000/campaigns/sync \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "AI agents are replacing SaaS tools",
    "platforms": ["linkedin"],
    "tone": "provocative",
    "target_audience": "tech founders",
    "auto_publish": false
  }'
```

---

## Project Structure

```
social-media-command-center/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
│
├── app/
│   ├── main.py                  # FastAPI app + routes + WebSocket
│   ├── config.py                # Environment config
│   │
│   ├── agents/
│   │   ├── trend_agent.py       # 🔍 Searches Pinecone, analyzes LinkedIn trends
│   │   ├── writer_agent.py      # ✍️ Writes LinkedIn-specific content
│   │   ├── publisher_agent.py   # 📤 Posts to LinkedIn
│   │   └── orchestrator.py      # 🎯 Chains all agents together
│   │
│   ├── services/
│   │   ├── pinecone_service.py  # Vector store for content memory
│   │   └── websocket_manager.py # Real-time event broadcasting
│   │
│   └── models/
│       └── schemas.py           # Pydantic models
│
└── frontend/
    └── index.html               # Live dashboard with WebSocket
```

---

## How Pinecone Is Used

Pinecone serves as the **learning memory** of the system:

1. **Before writing** — Trend Agent searches Pinecone for past high-performing content on similar topics to inform strategy
2. **After publishing** — Publisher Agent stores the generated content + metadata back into Pinecone
3. **Over time** — The system gets smarter as it accumulates more data about what content performs well

---

## License

MIT
