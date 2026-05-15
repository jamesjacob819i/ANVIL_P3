import asyncio

from shared.tracing import trace
from tools import (
    fetch_logs,
    query_metrics,
    get_recent_commits,
    check_dependencies,
)


@trace("diagnostics_agent")
async def run_diagnostics(incident_id: str, payload: dict) -> dict:
    service = payload.get("original_alert", {}).get("service", "target-app")

    log_results, metrics, commits, deps = await asyncio.gather(
        fetch_logs(service),
        query_metrics(service),
        get_recent_commits(),
        check_dependencies(service),
    )

    evidence = {
        "incident_id": incident_id,
        "service": service,
        "logs": log_results,
        "metrics": metrics,
        "recent_commits": commits,
        "dependencies": deps,
        "analysis_timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }

    return evidence
