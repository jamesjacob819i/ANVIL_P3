import os
import httpx
from shared.tracing import trace

TARGET_APP_URL = os.getenv("TARGET_APP_URL", "http://target_app:5000")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DEMO_REPO = os.getenv("DEMO_REPO", "jamesjacobi/sentinel-demo")


@trace("fetch_logs")
async def fetch_logs(service: str = "target-app") -> list[dict]:
    logs = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for line_num in range(1, 50):
                try:
                    resp = await client.get(
                        f"{TARGET_APP_URL}/health"
                    )
                    if resp.status_code == 200:
                        break
                except Exception:
                    pass
            resp = await client.get(f"{TARGET_APP_URL}/metrics")
            if resp.status_code == 200:
                logs.append({"source": "metrics_endpoint", "data": resp.json()})
    except Exception as e:
        logs.append({"source": "error", "message": str(e)})

    logs.append({
        "source": "note",
        "message": f"Diagnostics running for service: {service}. Check app container logs for details."
    })

    return logs


@trace("query_metrics")
async def query_metrics(service: str = "target-app") -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{TARGET_APP_URL}/metrics")
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}", "service": service}
    except Exception as e:
        return {"error": str(e), "service": service}


@trace("get_recent_commits")
async def get_recent_commits(repo: str = "") -> list[dict]:
    if not GITHUB_TOKEN:
        return [{"error": "No GITHUB_TOKEN configured"}]

    repo_name = repo or DEMO_REPO
    try:
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo_name}/commits",
                headers=headers,
                params={"per_page": 5},
            )
            if resp.status_code == 200:
                commits = resp.json()
                return [
                    {
                        "sha": c["sha"][:8],
                        "message": c["commit"]["message"].split("\n")[0],
                        "author": c["commit"]["author"]["name"],
                        "date": c["commit"]["author"]["date"],
                    }
                    for c in commits
                ]
            return [{"error": f"GitHub API: HTTP {resp.status_code}"}]
    except Exception as e:
        return [{"error": str(e)}]


@trace("check_dependencies")
async def check_dependencies(service: str = "target-app") -> dict:
    results = {}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{TARGET_APP_URL}/health")
            results["app_health"] = "ok" if resp.status_code == 200 else "degraded"
    except Exception as e:
        results["app_health"] = f"unreachable: {e}"

    results["database"] = "skipped (checked by app health)"
    return results
