import asyncio
import json
from shared.bus import EventBus, SentinelEvent
from agent import find_or_create_issue, add_issue_comment

bus = EventBus()

async def handle_incidents_new(event: SentinelEvent):
    title = f"Incident {event.incident_id[:8]}"
    body = f"## Sentinel Incident Commander\n\n**Incident ID**: {event.incident_id}\n**Alert**: {event.payload.get('message', 'Unknown')}\n**Service**: {event.payload.get('service', 'unknown')}"
    issue_number = await find_or_create_issue(event.incident_id, title, body)
    print(f"[orchestrator] Created issue #{issue_number} for {event.incident_id}")

async def handle_triage_done(event: SentinelEvent):
    issue_number = await find_or_create_issue(event.incident_id, f"Incident {event.incident_id[:8]}", "Recovered")
    comment = f"**Triage Completed**\n- Severity: {event.payload.get('severity')}\n- Reason: {event.payload.get('reason')}\n- Autonomous: {event.payload.get('autonomous_proceed')}"
    await add_issue_comment(issue_number, comment)

async def handle_diagnostics_done(event: SentinelEvent):
    issue_number = await find_or_create_issue(event.incident_id, f"Incident {event.incident_id[:8]}", "Recovered")
    metrics = event.payload.get('metrics', {})
    comment = f"**Diagnostics Completed**\n- Error Rate: {metrics.get('error_rate')}\n- Latency p99: {metrics.get('latency_p99')}\n- Request Count: {metrics.get('request_count')}"
    await add_issue_comment(issue_number, comment)

async def handle_rca_done(event: SentinelEvent):
    issue_number = await find_or_create_issue(event.incident_id, f"Incident {event.incident_id[:8]}", "Recovered")
    comment = f"**Root Cause Analysis Completed**\n- Confidence: {event.payload.get('confidence')}\n- Root Cause: {event.payload.get('root_cause')}\n- Next Steps: {event.payload.get('next_steps')}"
    await add_issue_comment(issue_number, comment)

async def handle_remediation_done(event: SentinelEvent):
    issue_number = await find_or_create_issue(event.incident_id, f"Incident {event.incident_id[:8]}", "Recovered")
    patch = event.payload.get('patch')
    if patch:
        comment = f"**Remediation Generated**\nSentinel created a patch and pushed it to branch `{event.payload.get('branch')}`.\n\n```diff\n{patch[:1000]}\n```"
    else:
        comment = f"**Remediation Skipped**\nNo actionable patch could be generated."
    await add_issue_comment(issue_number, comment)

async def handle_deployment_done(event: SentinelEvent):
    issue_number = await find_or_create_issue(event.incident_id, f"Incident {event.incident_id[:8]}", "Recovered")
    comment = f"**Deployment Action**\nStatus: {'Success' if event.payload.get('success') else 'Skipped/Failed'}"
    await add_issue_comment(issue_number, comment)

async def handle_postmortem_done(event: SentinelEvent):
    issue_number = await find_or_create_issue(event.incident_id, f"Incident {event.incident_id[:8]}", "Recovered")
    commit_info = event.payload.get('commit', {})
    comment = f"**Postmortem Pushed**\nA full postmortem report was generated and committed to the repository.\n\n[View Postmortem]({commit_info.get('url', '#')})"
    await add_issue_comment(issue_number, comment)

async def main():
    await bus.connect()
    
    # We create concurrent tasks to listen to all events!
    await asyncio.gather(
        bus.subscribe("incidents.new", "orchestrator_worker", handle_incidents_new),
        bus.subscribe("triage.done", "orchestrator_worker", handle_triage_done),
        bus.subscribe("diagnostics.done", "orchestrator_worker", handle_diagnostics_done),
        bus.subscribe("rca.done", "orchestrator_worker", handle_rca_done),
        bus.subscribe("fix.done", "orchestrator_worker", handle_remediation_done),
        bus.subscribe("deployment.done", "orchestrator_worker", handle_deployment_done),
        bus.subscribe("postmortem.done", "orchestrator_worker", handle_postmortem_done),
    )

if __name__ == "__main__":
    asyncio.run(main())
