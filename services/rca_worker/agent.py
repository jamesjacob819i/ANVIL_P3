from pydantic import BaseModel, Field

from shared.llm import llm_call
from shared.tracing import trace
from tools import web_search, read_source_code


class RCAHypothesis(BaseModel):
    root_cause: str = Field(description="Root cause description")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    suspect_commit: str | None = Field(None, description="SHA of suspect commit")
    suspect_file: str | None = Field(None, description="Path to suspect file")
    suspect_lines: str | None = Field(None, description="Line numbers or range")
    evidence_summary: str = Field(description="Summary of evidence")
    next_steps: str = Field(description="What to investigate next if confidence < 0.7")

    class Config:
        json_schema_extra = {
            "required": ["root_cause", "confidence", "evidence_summary"]
        }


SYSTEM_PROMPT = """You are a root cause analysis agent. Given diagnostics evidence, hypothesize the root cause of a production incident.

Analyze the evidence:
1. Logs - look for error messages and stack traces
2. Metrics - look for error rates, latency spikes
3. Recent commits - look for recently changed code that could cause the issue
4. Dependencies - check for connectivity issues

Self-evaluate your confidence. If below 0.7, suggest what additional evidence to gather."""


@trace("rca_agent")
async def run_rca(incident_id: str, evidence: dict) -> dict:
    logs = evidence.get("logs", [])
    metrics = evidence.get("metrics", {})
    commits = evidence.get("recent_commits", [])
    deps = evidence.get("dependencies", {})

    user_prompt = f"""Incident ID: {incident_id}

Metrics: {metrics}

Recent Commits: {commits}

Dependencies: {deps}

Logs: {logs[:3]}

Analyze this evidence and determine the root cause."""

    hypothesis = await llm_call(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=RCAHypothesis,
    )

    if hypothesis["confidence"] < 0.7:
        error_msg = hypothesis.get("root_cause", "")
        search_results = await web_search(f"production error: {error_msg}")

        suspect_file = hypothesis.get("suspect_file")
        if suspect_file:
            repo = evidence.get("service", "jamesjacob819i/ANVIL_P3")
            source = await read_source_code(repo, suspect_file)
            search_results.append({"source": "github_source", "data": source})

        user_prompt2 = f"""Initial hypothesis: {hypothesis}
Additional evidence from web search: {search_results}

Refine your root cause analysis with this new information."""

        hypothesis = await llm_call(
            system_prompt=SYSTEM_PROMPT + "\nRefine your analysis with the additional evidence provided.",
            user_prompt=user_prompt2,
            response_model=RCAHypothesis,
        )

    return hypothesis
