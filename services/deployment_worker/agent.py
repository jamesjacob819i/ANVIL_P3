from shared.tracing import trace
from tools import trigger_deploy, monitor_metrics, rollback


MONITOR_SECONDS = 120
ERROR_RATE_THRESHOLD = 0.1


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

    error_rates = [m.get("error_rate", 0) for m in metrics_snapshots if "error_rate" in m]
    success = True

    if error_rates:
        avg_error_rate = sum(error_rates) / len(error_rates)
        if avg_error_rate > ERROR_RATE_THRESHOLD:
            rollback_result = await rollback()
            success = False
            final_metrics = {
                "avg_error_rate": avg_error_rate,
                "snapshots": metrics_snapshots,
                "rolled_back": True,
                "rollback_result": rollback_result,
            }
        else:
            final_metrics = {
                "avg_error_rate": avg_error_rate,
                "snapshots": metrics_snapshots,
                "rolled_back": False,
                "stable": True,
            }
    else:
        final_metrics = {
            "error": "No metrics collected",
            "snapshots": metrics_snapshots,
        }

    return {
        "success": success,
        "deploy_result": deploy_result,
        "final_metrics": final_metrics,
        "incident_id": incident_id,
    }
