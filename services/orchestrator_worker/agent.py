import os
import httpx
from shared.tracing import trace

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DEMO_REPO = os.getenv("DEMO_REPO", "jamesjacobi/sentinel-demo")

@trace("find_or_create_issue")
async def find_or_create_issue(incident_id: str, title: str, body: str) -> int:
    if not GITHUB_TOKEN:
        return None

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Search for existing issue
        search_query = f"Incident {incident_id} in:title repo:{DEMO_REPO} type:issue"
        resp = await client.get(f"https://api.github.com/search/issues?q={search_query}", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("total_count", 0) > 0:
                return data["items"][0]["number"]

        # Create new issue
        resp = await client.post(
            f"https://api.github.com/repos/{DEMO_REPO}/issues",
            headers=headers,
            json={"title": title, "body": body}
        )
        if resp.status_code == 201:
            return resp.json()["number"]
    return None

@trace("add_issue_comment")
async def add_issue_comment(issue_number: int, comment: str) -> None:
    if not GITHUB_TOKEN or not issue_number:
        return

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(
            f"https://api.github.com/repos/{DEMO_REPO}/issues/{issue_number}/comments",
            headers=headers,
            json={"body": comment}
        )
