from pydantic import BaseModel, Field

from shared.tracing import trace
from shared.llm import llm_call
from tools import trigger_deploy, monitor_metrics, rollback


MONITOR_SECONDS = 120


class DeploymentDecision(BaseModel):
    is_stable: bool = Field(description="Whether the deployment is stable based on the metrics")
    requires_rollback: bool = Field(description="Whether a rollback is required due to high error rates or latency")
    reasoning: str = Field(description="Explanation of the deployment health evaluation")


SYSTEM_PROMPT = """You are a deployment monitoring agent. Your ONLY job is to review post-deployment metrics and decide if the deployment is healthy or if it requires a rollback.
You must NOT attempt to fix code or diagnose the root cause. Focus purely on the metric snapshots. If the error rate averages above 0.1 (10%) or there are severe latency spikes, you should trigger a rollback."""


@trace("deployment_agent")
async def run_deployment(incident_id: str, pr_info: dict) -> dict:
    deploy_result = await trigger_deploy()

    if not deploy_result.get("success"):
        return {
            "success": False,
            "error": "Deploy failed to trigger",
            "deploy_result": deploy_result,
        }

    metrics_snapshots = await monitor_metrics(duration_seconds=MONITOR_SECONDS)
    
    user_prompt = f"""Review the following post-deployment metrics:
{metrics_snapshots}

Evaluate if the deployment is stable or needs a rollback."""

    decision = await llm_call(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=DeploymentDecision,
    )

    success = decision.get("is_stable", False) and not decision.get("requires_rollback", True)
    
    if decision.get("requires_rollback", True):
        rollback_result = await rollback()
        final_metrics = {
            "decision": decision,
            "snapshots": metrics_snapshots,
            "rolled_back": True,
            "rollback_result": rollback_result,
        }
    else:
        final_metrics = {
            "decision": decision,
            "snapshots": metrics_snapshots,
            "rolled_back": False,
            "stable": True,
        }

    return {
        "success": success,
        "deploy_result": deploy_result,
        "final_metrics": final_metrics,
        "incident_id": incident_id,
    }
