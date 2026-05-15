from shared.tracing import trace
from shared.db import get_session, get_incident_events
from tools import (
    generate_postmortem,
    commit_postmortem,
    create_linear_ticket,
)


@trace("postmortem_agent")
async def run_postmortem(incident_id: str, deployment_result: dict) -> dict:
    async with get_session() as session:
        events = await get_incident_events(incident_id, session)

    timeline = [
        {
            "topic": e.topic,
            "payload_json": e.payload_json,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        }
        for e in events
    ]

    postmortem_content = await generate_postmortem(incident_id, timeline)

    commit_result = await commit_postmortem(incident_id, postmortem_content)

    action_items = f"Postmortem for incident {incident_id}\n\nReview the full postmortem at: {commit_result.get('url', 'N/A')}"
    linear_result = await create_linear_ticket(
        f"Postmortem: Incident {incident_id[:8]}",
        action_items,
    )

    return {
        "incident_id": incident_id,
        "postmortem_content": postmortem_content[:500],
        "commit": commit_result,
        "linear_ticket": linear_result,
        "deployment_success": deployment_result.get("success", False),
    }
