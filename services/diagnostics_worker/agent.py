import asyncio
from pydantic import BaseModel, Field

from shared.tracing import trace
from shared.llm import llm_call
from tools import (
    fetch_logs,
    query_metrics,
    get_recent_commits,
    check_dependencies,
)


class DiagnosticSummary(BaseModel):
    anomalies_detected: bool = Field(description="Whether any anomalies were detected in the evidence")
    summary: str = Field(description="A concise summary of the gathered diagnostic evidence, pointing out clear issues")
    severity_assessment: str = Field(description="Assessment of how severe the issues in the logs/metrics appear")


SYSTEM_PROMPT = """You are a diagnostic analysis agent for a production pipeline. Your ONLY job is to review raw logs, metrics, commits, and dependencies, and output a concise summary of anomalies.
You must NOT attempt to perform root cause analysis, and you must NOT suggest code fixes. Focus purely on summarizing the current health state based on the provided evidence."""


@trace("diagnostics_agent")
async def run_diagnostics(incident_id: str, payload: dict) -> dict:
    service = payload.get("original_alert", {}).get("service", "target-app")

    log_results, metrics, commits, deps = await asyncio.gather(
        fetch_logs(service),
        query_metrics(service),
        get_recent_commits(),
        check_dependencies(service),
    )

    user_prompt = f"""Review the following diagnostic evidence for service '{service}':
Logs: {log_results[:5]}
Metrics: {metrics}
Commits: {commits}
Dependencies: {deps}

Provide a summary of anomalies and current health."""

    llm_summary = await llm_call(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=DiagnosticSummary,
    )

    evidence = {
        "incident_id": incident_id,
        "service": service,
        "logs": log_results,
        "metrics": metrics,
        "recent_commits": commits,
        "dependencies": deps,
        "llm_summary": llm_summary,
        "analysis_timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
    }

    return evidence
