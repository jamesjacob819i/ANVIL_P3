import os
import asyncio
import httpx
from shared.tracing import trace

TARGET_APP_URL = os.getenv("TARGET_APP_URL", "http://target_app:5000")


@trace("trigger_deploy")
async def trigger_deploy(service: str = "target-app") -> dict:
    try:
        proc = await asyncio.create_subprocess_shell(
            "docker compose up -d --build target_app",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode()[-500:],
            "stderr": stderr.decode()[-500:],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@trace("monitor_metrics")
async def monitor_metrics(duration_seconds: int = 120, interval: int = 10) -> list[dict]:
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
                        "error_rate": data.get("error_rate", -1),
                        "latency_p99": data.get("latency_p99", -1),
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
    try:
        proc = await asyncio.create_subprocess_shell(
            "git revert HEAD --no-edit && docker compose up -d --build target_app",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode()[-500:],
            "stderr": stderr.decode()[-500:],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
