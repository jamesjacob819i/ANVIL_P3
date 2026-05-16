import os
import sys
import uuid
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.bus import EventBus
from shared.events import SentinelEvent
from shared.db import save_event, save_agent_run, complete_agent_run, update_incident_status
from shared.tracing import set_trace, reset_trace
from agent import run_deployment


async def handle_fix_done(event: SentinelEvent):
    print(f"[deployment_worker] Processing fix result for {event.incident_id}")
    set_trace(event.trace_id, event.parent_event_id, event.id)

    agent_run_id = str(uuid.uuid4())
    await save_agent_run(agent_run_id, event.incident_id, "deployment_worker", event.payload)

    try:
        pr_info = event.payload.get("pr", {})
        result = await run_deployment(event.incident_id, pr_info)
        await complete_agent_run(agent_run_id, result)

        if result.get("success"):
            await update_incident_status(event.incident_id, "resolved")

        output_event = SentinelEvent(
            incident_id=event.incident_id,
            parent_event_id=event.id,
            topic="deployment.done",
            agent_name="deployment_worker",
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

        status = "success" if result.get("success") else "failed"
        print(f"[deployment_worker] Published deployment.done for {event.incident_id}: {status}")
    except Exception as e:
        print(f"[deployment_worker] Error processing {event.incident_id}: {e}")
        await complete_agent_run(agent_run_id, {"error": str(e)}, status="failed")
    finally:
        reset_trace()


async def handle_github_pr_merged(event: SentinelEvent):
    print(f"[deployment_worker] PR merged for {event.incident_id}")
    set_trace(event.trace_id)

    agent_run_id = str(uuid.uuid4())
    await save_agent_run(agent_run_id, event.incident_id, "deployment_worker", event.payload)

    try:
        result = await run_deployment(event.incident_id, event.payload)
        await complete_agent_run(agent_run_id, result)

        output_event = SentinelEvent(
            incident_id=event.incident_id,
            parent_event_id=event.id,
            topic="deployment.done",
            agent_name="deployment_worker",
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

        print(f"[deployment_worker] Published deployment.done for PR merge: {event.incident_id}")
    except Exception as e:
        print(f"[deployment_worker] Error processing PR merge {event.incident_id}: {e}")
        await complete_agent_run(agent_run_id, {"error": str(e)}, status="failed")
    finally:
        reset_trace()


async def main():
    bus = EventBus()
    await bus.connect()
    print("[deployment_worker] Subscribing to fix.done and github.pr_merged...")
    await asyncio.gather(
        bus.subscribe("fix.done", "deployment_worker_1", handle_fix_done),
        bus.subscribe("github.pr_merged", "deployment_worker_2", handle_github_pr_merged),
    )


if __name__ == "__main__":
    asyncio.run(main())
