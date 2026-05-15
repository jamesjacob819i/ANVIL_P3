import os
import sys
import uuid
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.bus import EventBus
from shared.events import SentinelEvent
from shared.db import save_event, save_agent_run, complete_agent_run
from shared.tracing import set_trace, reset_trace
from agent import run_remediation


async def handle_rca_done(event: SentinelEvent):
    print(f"[remediation_worker] Processing RCA for {event.incident_id}")
    set_trace(event.trace_id)

    agent_run_id = str(uuid.uuid4())
    await save_agent_run(agent_run_id, event.incident_id, "remediation_worker", event.payload)

    try:
        result = await run_remediation(event.incident_id, event.payload)
        await complete_agent_run(agent_run_id, result)

        output_event = SentinelEvent(
            incident_id=event.incident_id,
            parent_event_id=event.id,
            topic="fix.done",
            agent_name="remediation_worker",
            payload=result,
            trace_id=event.trace_id,
        )

        await save_event(
            output_event.id, event.incident_id, event.id,
            output_event.topic, output_event.payload,
        )

        bus = EventBus()
        await bus.connect()
        await bus.publish(output_event)
        await bus.close()

        pr_url = result.get("pr", {}).get("pr_url", "N/A")
        print(f"[remediation_worker] Published fix.done for {event.incident_id}: PR={pr_url}")
    except Exception as e:
        print(f"[remediation_worker] Error processing {event.incident_id}: {e}")
        await complete_agent_run(agent_run_id, {"error": str(e)}, status="failed")
    finally:
        reset_trace()


async def main():
    bus = EventBus()
    await bus.connect()
    print("[remediation_worker] Subscribing to rca.done...")
    await bus.subscribe("rca.done", "remediation_worker_1", handle_rca_done)


if __name__ == "__main__":
    asyncio.run(main())
