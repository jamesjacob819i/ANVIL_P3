import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from shared.llm import llm_call
from shared.db import get_open_incidents, get_session
from shared.tracing import trace


class TriageOutput(BaseModel):
    severity: str = Field(description="P1, P2, P3, or P4")
    autonomous_proceed: bool = Field(description="Whether to proceed autonomously")
    reason: str = Field(description="Explanation for the triage decision")
    duplicate_incident_id: str | None = Field(
        None, description="If duplicate, reference existing incident ID"
    )


SYSTEM_PROMPT = """You are a production incident triage agent. Classify the severity and decide if the incident should be handled autonomously.

Severity guidelines:
- P1: Critical - service down, data loss, security breach. AUTONOMOUS_PROCEED=true
- P2: High - degraded performance, non-critical feature broken. AUTONOMOUS_PROCEED=true
- P3: Medium - minor issue, cosmetic bug. AUTONOMOUS_PROCEED=false (needs human review)
- P4: Low - informational. AUTONOMOUS_PROCEED=false

If there are multiple open incidents with similar messages, flag as duplicate."""


@trace("triage_agent")
async def run_triage(incident_id: str, alert_payload: dict) -> dict:
    async with get_session() as session:
        open_incidents = await get_open_incidents(session)

    duplicates_info = ""
    if open_incidents:
        dupes = [inc for inc in open_incidents if inc.id != incident_id]
        if dupes:
            duplicates_info = "\nOpen incidents:\n" + "\n".join(
                f"- {inc.id}: {inc.alert_payload.get('message', 'N/A')}"
                for inc in dupes[:5]
            )

    user_prompt = f"""Incident ID: {incident_id}
Alert Payload: {alert_payload}
{duplicates_info}

Classify this incident's severity and whether to proceed autonomously."""

    result = await llm_call(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=TriageOutput,
    )

    return result
