import os
import sys
import asyncio
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.bus import EventBus, SentinelEvent
from agent import find_or_create_issue, add_issue_comment, close_issue

bus = EventBus()


async def handle_incidents_new(event: SentinelEvent):
    from shared.tracing import set_trace, reset_trace
    set_trace(event.trace_id, event.parent_event_id, event.id)
    
    try:
        incident_id = event.incident_id
        service = event.payload.get("raw_payload", {}).get("service", "unknown")
        message = event.payload.get("message", "No message")
        source = event.payload.get("source", "unknown")

        title = f"🚨 Incident {incident_id[:8]} — {service}"
        body = f"""## 🤖 Sentinel Autonomous Incident Commander

| Field | Value |
|-------|-------|
| **Incident ID** | `{incident_id}` |
| **Service** | `{service}` |
| **Source** | `{source}` |
| **Alert** | {message} |

## Pipeline Status

| Stage | Status |
|-------|--------|
| Webhook Ingress | ✅ Received |
| Triage | ⏳ In Progress |
| Diagnostics | ⏳ Pending |
| RCA | ⏳ Pending |
| Remediation | ⏳ Pending |
| Deployment | ⏳ Pending |
| Postmortem | ⏳ Pending |

> _This issue is automatically managed by Sentinel AI. Updates will be posted as comments._
"""
        issue_number = await find_or_create_issue(incident_id, title, body)
        print(f"[orchestrator] Created/found issue #{issue_number} for incident {incident_id[:8]}")
    finally:
        reset_trace()


async def handle_triage_done(event: SentinelEvent):
    from shared.tracing import set_trace, reset_trace
    set_trace(event.trace_id, event.parent_event_id, event.id)
    
    try:
        issue_number = await find_or_create_issue(
            event.incident_id, f"🚨 Incident {event.incident_id[:8]}", "Incident created"
        )
        severity = event.payload.get("severity", "Unknown")
        reason = event.payload.get("reason", "")
        proceed = event.payload.get("autonomous_proceed", False)
        duplicate = event.payload.get("duplicate_incident_id")

        comment = f"""### ✅ Triage Completed

| Field | Value |
|-------|-------|
| **Severity** | `{severity}` |
| **Autonomous Proceed** | `{'Yes' if proceed else 'No'}` |
| **Duplicate Of** | `{duplicate[:8] if duplicate else 'N/A'}` |

**Analysis:** {reason}
"""
        await add_issue_comment(issue_number, comment)
    finally:
        reset_trace()


async def handle_diagnostics_done(event: SentinelEvent):
    from shared.tracing import set_trace, reset_trace
    set_trace(event.trace_id, event.parent_event_id, event.id)
    
    try:
        issue_number = await find_or_create_issue(
            event.incident_id, f"🚨 Incident {event.incident_id[:8]}", "Incident created"
        )
        metrics = event.payload.get("metrics", {})
        llm_summary = event.payload.get("llm_summary", {})
        summary_text = llm_summary.get("summary", "N/A")
        severity = llm_summary.get("severity_assessment", "N/A")

        comment = f"""### 🔍 Diagnostics Completed

| Metric | Value |
|--------|-------|
| **Error Rate** | `{metrics.get('error_rate', 'N/A')}` |
| **Latency p99** | `{metrics.get('latency_p99', 'N/A')}ms` |
| **Request Count** | `{metrics.get('request_count', 'N/A')}` |
| **App Health** | `{event.payload.get('dependencies', {}).get('app_health', 'N/A')}` |

**Agent Analysis:**
- **Summary:** {summary_text}
- **Severity Assessment:** {severity}
"""
        await add_issue_comment(issue_number, comment)
    finally:
        reset_trace()


async def handle_rca_done(event: SentinelEvent):
    from shared.tracing import set_trace, reset_trace
    set_trace(event.trace_id, event.parent_event_id, event.id)
    
    try:
        issue_number = await find_or_create_issue(
            event.incident_id, f"🚨 Incident {event.incident_id[:8]}", "Incident created"
        )
        confidence = event.payload.get("confidence", 0)
        root_cause = event.payload.get("root_cause", "Unknown")
        next_steps = event.payload.get("next_steps", "")
        suspect_file = event.payload.get("suspect_file", "N/A")

        comment = f"""### 🧠 Root Cause Analysis Completed

| Field | Value |
|-------|-------|
| **Confidence** | `{confidence:.0%}` |
| **Suspect File** | `{suspect_file}` |

**Root Cause:** {root_cause}

**Recommended Next Steps:** {next_steps}
"""
        await add_issue_comment(issue_number, comment)
    finally:
        reset_trace()


async def handle_remediation_done(event: SentinelEvent):
    from shared.tracing import set_trace, reset_trace
    set_trace(event.trace_id, event.parent_event_id, event.id)
    
    try:
        issue_number = await find_or_create_issue(
            event.incident_id, f"🚨 Incident {event.incident_id[:8]}", "Incident created"
        )
        pr_info = event.payload.get("pr", {})
        patch = event.payload.get("patch", "")
        branch = event.payload.get("branch", "N/A")
        pr_url = pr_info.get("pr_url", "")
        pr_error = pr_info.get("error", "")

        if pr_url:
            pr_section = f"**Pull Request:** [{pr_url}]({pr_url})"
        elif pr_error:
            pr_section = f"**PR Error:** {pr_error}"
        else:
            pr_section = "**PR:** Pending"

        patch_section = f"```diff\n{patch[:1500]}\n```" if patch else "_No patch generated_"

        comment = f"""### 🔧 Remediation Generated

| Field | Value |
|-------|-------|
| **Branch** | `{branch}` |
| **Auto-Merge** | `{'Yes' if event.payload.get('auto_merge') else 'No'}` |

{pr_section}

**Patch:**
{patch_section}
"""
        await add_issue_comment(issue_number, comment)
    finally:
        reset_trace()


async def handle_deployment_done(event: SentinelEvent):
    from shared.tracing import set_trace, reset_trace
    set_trace(event.trace_id, event.parent_event_id, event.id)
    
    try:
        issue_number = await find_or_create_issue(
            event.incident_id, f"🚨 Incident {event.incident_id[:8]}", "Incident created"
        )
        success = event.payload.get("success", False)
        final_metrics = event.payload.get("final_metrics", {})
        rolled_back = final_metrics.get("rolled_back", False)
        decision = final_metrics.get("decision", {})
        reasoning = decision.get("reasoning", "N/A")

        comment = f"""### 🚀 Deployment {"✅ Successful" if success else "⚠️ Rolled Back"}

| Field | Value |
|-------|-------|
| **Status** | `{'Deployed & Stable' if success and not rolled_back else 'Rolled Back' if rolled_back else 'Deployed'}` |
| **Monitoring Samples** | `{len(final_metrics.get('snapshots', []))}` |

**Agent Evaluation:**
{reasoning}
"""
        await add_issue_comment(issue_number, comment)
    finally:
        reset_trace()


async def handle_postmortem_done(event: SentinelEvent):
    from shared.tracing import set_trace, reset_trace
    set_trace(event.trace_id, event.parent_event_id, event.id)
    
    try:
        issue_number = await find_or_create_issue(
            event.incident_id, f"🚨 Incident {event.incident_id[:8]}", "Incident created"
        )
        commit_info = event.payload.get("commit", {})
        postmortem_url = commit_info.get("url", "")
        commit_sha = commit_info.get("commit_sha", "")

        final_comment = f"""### 📝 Postmortem Published — Incident Resolved

A full post-mortem report has been generated and committed to the repository.

| Field | Value |
|-------|-------|
| **Commit SHA** | `{commit_sha[:12] if commit_sha else 'N/A'}` |
| **Report** | {f'[View Postmortem]({postmortem_url})' if postmortem_url else 'N/A'} |

---
✅ **This incident has been fully resolved by Sentinel AI.**
_Pipeline: Ingress → Triage → Diagnostics → RCA → Remediation → Deployment → Postmortem_
"""
        await close_issue(issue_number, final_comment)
        
        from shared.tracing import _omium_available
        if _omium_available:
            from omium.integrations.core import score
            try:
                score(
                    trace_id=event.trace_id,
                    name="resolution_success",
                    value=1.0,
                    comment="Incident autonomously resolved end-to-end"
                )
                print(f"[orchestrator] Omium success score reported for trace {event.trace_id}")
            except Exception as e:
                print(f"[orchestrator] Failed to report score: {e}")
    finally:
        reset_trace()


async def main():
    await bus.connect()
    print("[orchestrator] Connected. Subscribing to all pipeline events...")

    await asyncio.gather(
        bus.subscribe("incidents.new", "orchestrator_worker_1", handle_incidents_new, group_name="orchestrator"),
        bus.subscribe("triage.done", "orchestrator_worker_2", handle_triage_done, group_name="orchestrator"),
        bus.subscribe("diagnostics.done", "orchestrator_worker_3", handle_diagnostics_done, group_name="orchestrator"),
        bus.subscribe("rca.done", "orchestrator_worker_4", handle_rca_done, group_name="orchestrator"),
        bus.subscribe("fix.done", "orchestrator_worker_5", handle_remediation_done, group_name="orchestrator"),
        bus.subscribe("deployment.done", "orchestrator_worker_6", handle_deployment_done, group_name="orchestrator"),
        bus.subscribe("postmortem.done", "orchestrator_worker_7", handle_postmortem_done, group_name="orchestrator"),
    )


if __name__ == "__main__":
    asyncio.run(main())
