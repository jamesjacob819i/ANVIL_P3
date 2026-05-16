import os
import sys
import uuid
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.bus import EventBus
from shared.events import SentinelEvent
from shared.db import save_event, save_agent_run, complete_agent_run
from shared.tracing import set_trace, reset_trace
from agent import run_triage


async def handle_incident_new(event: SentinelEvent):
    print(f"[triage_worker] Processing incident: {event.incident_id}")
    set_trace(event.trace_id, event.parent_event_id, event.id)

    agent_run_id = str(uuid.uuid4())
    await save_agent_run(agent_run_id, event.incident_id, "triage_worker", event.payload)

    try:
        result = await run_triage(event.incident_id, event.payload)
        await complete_agent_run(agent_run_id, result)

        output_event = SentinelEvent(
            incident_id=event.incident_id,
            parent_event_id=event.id,
            topic="triage.done",
            agent_name="triage_worker",
            payload={
                "severity": result["severity"],
                "autonomous_proceed": result["autonomous_proceed"],
                "reason": result["reason"],
                "duplicate_incident_id": result.get("duplicate_incident_id"),
                "original_alert": event.payload,
            },
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

        print(f"[triage_worker] Published triage.done for {event.incident_id}: severity={result['severity']}, proceed={result['autonomous_proceed']}")
    except Exception as e:
        print(f"[triage_worker] Error processing {event.incident_id}: {e}")
        await complete_agent_run(agent_run_id, {"error": str(e)}, status="failed")
    finally:
        reset_trace()


async def main():
    bus = EventBus()
    await bus.connect()
    print("[triage_worker] Subscribing to incidents.new...")
    await bus.subscribe("incidents.new", "triage_worker_1", handle_incident_new)


if __name__ == "__main__":
    asyncio.run(main())
