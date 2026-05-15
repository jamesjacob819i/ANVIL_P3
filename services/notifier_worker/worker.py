import os
import sys
import json
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import httpx
from shared.bus import EventBus
from shared.events import SentinelEvent, TOPICS
from shared.tracing import trace

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


def format_slack_message(event: SentinelEvent) -> dict:
    emoji_map = {
        "incidents.new": ":rotating_light:",
        "triage.done": ":mag:",
        "diagnostics.done": ":stethoscope:",
        "rca.done": ":microscope:",
        "fix.done": ":wrench:",
        "github.pr_merged": ":merged:",
        "deployment.done": ":rocket:",
        "postmortem.done": ":book:",
    }

    emoji = emoji_map.get(event.topic, ":bell:")
    title = f"{emoji} *Sentinel Event: {event.topic}*"

    fields = []
    fields.append({"type": "mrkdwn", "text": f"*Incident:* `{event.incident_id[:16]}...`"})
    fields.append({"type": "mrkdwn", "text": f"*Agent:* `{event.agent_name}`"})

    payload = event.payload
    if event.topic == "incidents.new":
        fields.append({"type": "mrkdwn", "text": f"*Message:* {payload.get('message', 'N/A')}"})
        fields.append({"type": "mrkdwn", "text": f"*Source:* {payload.get('source', 'N/A')}"})
    elif event.topic == "triage.done":
        fields.append({"type": "mrkdwn", "text": f"*Severity:* {payload.get('severity', 'N/A')}"})
        fields.append({"type": "mrkdwn", "text": f"*Auto-proceed:* {payload.get('autonomous_proceed', 'N/A')}"})
    elif event.topic == "rca.done":
        fields.append({"type": "mrkdwn", "text": f"*Root Cause:* {payload.get('root_cause', 'N/A')}"})
        fields.append({"type": "mrkdwn", "text": f"*Confidence:* {payload.get('confidence', 'N/A')}"})
    elif event.topic == "fix.done":
        pr_info = payload.get("pr", {})
        pr_url = pr_info.get("pr_url", "N/A")
        fields.append({"type": "mrkdwn", "text": f"*PR:* <{pr_url}|View PR>"})
    elif event.topic == "deployment.done":
        status = "Success :white_check_mark:" if payload.get("success") else "Failed :x:"
        fields.append({"type": "mrkdwn", "text": f"*Status:* {status}"})
    elif event.topic == "postmortem.done":
        commit_info = payload.get("commit", {})
        fields.append({"type": "mrkdwn", "text": f"*Post-mortem:* <{commit_info.get('url', 'N/A')}|View Document>"})

    return {
        "text": title,
        "attachments": [{"color": "#36a64f", "fields": fields, "ts": int(__import__("time").time())}],
    }


async def send_slack(message: dict) -> bool:
    if not SLACK_WEBHOOK_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json=message)
            return resp.status_code == 200
    except Exception:
        return False


async def handle_all_events(event: SentinelEvent):
    print(f"[notifier_worker] Event: {event.topic} for {event.incident_id[:16]}...")
    msg = format_slack_message(event)
    sent = await send_slack(msg)
    if sent:
        print(f"[notifier_worker] Slack notification sent for {event.topic}")
    else:
        print(f"[notifier_worker] Slack not configured, logging only: {event.topic}")


async def main():
    bus = EventBus()
    await bus.connect()
    print(f"[notifier_worker] Subscribing to ALL topics...")

    tasks = []
    for topic in TOPICS:
        tasks.append(
            bus.subscribe(topic, f"notifier_{topic.replace('.', '_')}", handle_all_events)
        )
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
