import os
import json
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from shared.bus import EventBus, TOPICS
from shared.db import get_session, get_incident_events, Incident, select, EventRecord, AgentRun

bus = EventBus()
connected_websockets: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bus.connect()
    asyncio.create_task(event_forwarder())
    yield
    await bus.close()


app = FastAPI(title="Sentinel Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def event_forwarder():
    async def forward(event):
        data = {
            "type": "event",
            "topic": event.topic,
            "incident_id": event.incident_id,
            "agent_name": event.agent_name,
            "payload": event.payload,
            "timestamp": event.timestamp,
        }
        dead = set()
        for ws in connected_websockets:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        connected_websockets.difference_update(dead)

    tasks = []
    for topic in TOPICS:
        tasks.append(
            bus.subscribe(topic, f"dashboard_{topic.replace('.', '_')}", forward, group_name="dashboard_group")
        )
    await asyncio.gather(*tasks)


import httpx

@app.post("/api/incidents")
async def trigger_incident(payload: dict):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post("http://webhook_ingress:8000/webhooks/alert", json=payload)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}, 500

@app.get("/health")
async def health():
    return {"status": "ok", "service": "dashboard_api"}


@app.get("/api/incidents")
async def list_incidents(status: str = None, limit: int = 50):
    async with get_session() as session:
        query = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
        if status:
            query = query.where(Incident.status == status)
        result = await session.execute(query)
        incidents = result.scalars().all()
        return [
            {
                "id": inc.id,
                "status": inc.status,
                "alert_payload": inc.alert_payload,
                "created_at": inc.created_at.isoformat() if inc.created_at else None,
                "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
            }
            for inc in incidents
        ]


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    async with get_session() as session:
        inc_result = await session.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        incident = inc_result.scalar_one_or_none()
        if not incident:
            return {"error": "Incident not found"}, 404

        events_result = await session.execute(
            select(EventRecord)
            .where(EventRecord.incident_id == incident_id)
            .order_by(EventRecord.created_at)
        )
        events = events_result.scalars().all()

        runs_result = await session.execute(
            select(AgentRun)
            .where(AgentRun.incident_id == incident_id)
            .order_by(AgentRun.started_at)
        )
        runs = runs_result.scalars().all()

        return {
            "incident": {
                "id": incident.id,
                "status": incident.status,
                "alert_payload": incident.alert_payload,
                "created_at": incident.created_at.isoformat() if incident.created_at else None,
                "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            },
            "events": [
                {
                    "id": e.id,
                    "topic": e.topic,
                    "parent_event_id": e.parent_event_id,
                    "payload": e.payload_json,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ],
            "agent_runs": [
                {
                    "id": r.id,
                    "agent_name": r.agent_name,
                    "input": r.input_json,
                    "output": r.output_json,
                    "status": r.status,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                }
                for r in runs
            ],
        }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_websockets.discard(websocket)
    except Exception:
        connected_websockets.discard(websocket)
