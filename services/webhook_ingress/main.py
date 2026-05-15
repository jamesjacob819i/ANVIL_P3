import os
import json
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager

from shared.bus import EventBus
from shared.events import SentinelEvent
from shared.db import save_incident, save_event

bus = EventBus()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bus.connect()
    yield
    await bus.close()


app = FastAPI(title="Sentinel Webhook Ingress", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "webhook_ingress", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/webhooks/alert")
async def webhook_alert(request: Request):
    body = await request.json()
    incident_id = str(uuid.uuid4())

    alert_source = body.get("source", body.get("alert_source", "unknown"))
    alert_message = body.get("message", body.get("alert_message", "No message"))

    alert_payload = {
        "incident_id": incident_id,
        "source": alert_source,
        "message": alert_message,
        "raw_payload": body,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    await save_incident(incident_id, alert_payload)

    event = SentinelEvent(
        incident_id=incident_id,
        topic="incidents.new",
        agent_name="webhook_ingress",
        payload=alert_payload,
    )

    await save_event(event.id, incident_id, None, event.topic, event.payload)
    await bus.publish(event)

    return {
        "status": "accepted",
        "incident_id": incident_id,
        "event_id": event.id,
    }


@app.post("/webhooks/github")
async def webhook_github(request: Request):
    body = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "unknown")

    if event_type == "pull_request" and body.get("action") == "closed" and body.get("pull_request", {}).get("merged"):
        pr = body["pull_request"]
        incident_id = str(uuid.uuid4())

        payload = {
            "incident_id": incident_id,
            "pr_number": pr["number"],
            "pr_url": pr["html_url"],
            "pr_title": pr["title"],
            "repo_full_name": body.get("repository", {}).get("full_name", "unknown"),
            "merged_by": pr.get("merged_by", {}).get("login", "unknown"),
            "merge_commit_sha": pr.get("merge_commit_sha", ""),
        }

        event = SentinelEvent(
            incident_id=incident_id,
            topic="github.pr_merged",
            agent_name="webhook_ingress",
            payload=payload,
        )

        await bus.publish(event)
        return {"status": "accepted", "event_id": event.id, "topic": "github.pr_merged"}

    return {"status": "ignored", "event_type": event_type, "action": body.get("action")}
