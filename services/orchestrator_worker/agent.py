import os
import httpx
from shared.tracing import trace

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DEMO_REPO = os.getenv("DEMO_REPO", "jamesjacob819i/ANVIL_P3")


@trace("find_or_create_issue")
async def find_or_create_issue(incident_id: str, title: str, body: str) -> int:
    if not GITHUB_TOKEN:
        return None

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Search for existing issue with this incident ID
        resp = await client.get(
            f"https://api.github.com/repos/{DEMO_REPO}/issues?state=open&labels=sentinel",
            headers=headers,
        )
        if resp.status_code == 200:
            for issue in resp.json():
                if incident_id[:8] in issue.get("title", ""):
                    return issue["number"]

        # Create a new issue
        resp = await client.post(
            f"https://api.github.com/repos/{DEMO_REPO}/issues",
            headers=headers,
            json={"title": title, "body": body, "labels": ["sentinel", "incident"]}
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
        resp = await client.post(
            f"https://api.github.com/repos/{DEMO_REPO}/issues/{issue_number}/comments",
            headers=headers,
            json={"body": comment}
        )
        if resp.status_code == 201:
            print(f"[orchestrator] Added comment to issue #{issue_number}")
        else:
            print(f"[orchestrator] Failed to comment on issue #{issue_number}: {resp.status_code}")


@trace("close_issue")
async def close_issue(issue_number: int, comment: str) -> None:
    if not GITHUB_TOKEN or not issue_number:
        return

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Add final comment first
        await client.post(
            f"https://api.github.com/repos/{DEMO_REPO}/issues/{issue_number}/comments",
            headers=headers,
            json={"body": comment}
        )
        # Close the issue
        await client.patch(
            f"https://api.github.com/repos/{DEMO_REPO}/issues/{issue_number}",
            headers=headers,
            json={"state": "closed", "state_reason": "completed"}
        )
        print(f"[orchestrator] Closed issue #{issue_number}")
