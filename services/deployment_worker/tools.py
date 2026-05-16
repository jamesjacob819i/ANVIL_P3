import os
import asyncio
import httpx
from shared.tracing import trace

TARGET_APP_URL = os.getenv("TARGET_APP_URL", "http://target_app:5000")


@trace("trigger_deploy")
async def trigger_deploy(service: str = "target-app") -> dict:
    """Simulate a deployment - in production this would call k8s/ECS APIs."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{TARGET_APP_URL}/health")
            healthy = resp.status_code == 200
    except Exception:
        healthy = False

    return {
        "success": True,
        "service": service,
        "status": "deployed" if healthy else "deployed_unhealthy_start",
        "message": "Sentinel initiated deployment rollout",
    }


@trace("monitor_metrics")
async def monitor_metrics(duration_seconds: int = 30, interval: int = 5) -> list[dict]:
    """Monitor target app metrics for a short window (fast pipeline)."""
    snapshots = []
    start = asyncio.get_event_loop().time()

    while (asyncio.get_event_loop().time() - start) < duration_seconds:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{TARGET_APP_URL}/metrics")
                if resp.status_code == 200:
                    data = resp.json()
                    snapshots.append({
                        "time_offset": round(asyncio.get_event_loop().time() - start, 1),
                        "error_rate": data.get("error_rate", 0),
                        "latency_p99": data.get("latency_p99", 0),
                        "request_count": data.get("request_count", 0),
                    })
        except Exception as e:
            snapshots.append({
                "time_offset": round(asyncio.get_event_loop().time() - start, 1),
                "error": str(e),
            })

        await asyncio.sleep(interval)

    return snapshots


@trace("rollback")
async def rollback(commits: list[str] | None = None) -> dict:
    """Signal a rollback - in production calls deployment platform."""
    return {
        "success": True,
        "action": "rollback_signaled",
        "message": "Sentinel signaled rollback to previous stable version",
    }
