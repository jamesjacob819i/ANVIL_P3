import os
import httpx
from datetime import datetime, timezone

from shared.db import get_session, get_incident_events
from shared.llm import llm_call_freeform
from shared.tracing import trace

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY", "")
DEMO_REPO = os.getenv("DEMO_REPO", "jamesjacobi/sentinel-demo")


@trace("generate_postmortem")
async def generate_postmortem(incident_id: str, timeline: list[dict]) -> str:
    timeline_text = "\n".join(
        f"- [{e.get('topic', 'unknown')}] {e.get('payload_json', {})}"
        for e in timeline
    )

    prompt = f"""Generate a postmortem document for production incident {incident_id}.

Timeline of events:
{timeline_text}

Format the postmortem with sections:
- Incident ID
- Date
- Summary
- Timeline
- Root Cause
- Resolution
- Action Items
- Lessons Learned

Use markdown formatting."""

    return await llm_call_freeform(
        system_prompt="You are a Site Reliability Engineer writing postmortems.",
        user_prompt=prompt,
    )


@trace("commit_postmortem")
async def commit_postmortem(incident_id: str, content: str) -> dict:
    if not GITHUB_TOKEN:
        return {"error": "No GITHUB_TOKEN configured"}

    filename = f"POSTMORTEM-{incident_id[:8]}.md"
    commit_message = f"postmortem: {incident_id[:8]}"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{DEMO_REPO}/contents/{filename}",
            headers=headers,
        )

        if resp.status_code == 200:
            existing = resp.json()
            sha = existing.get("sha", "")
        else:
            sha = None

        put_data = {
            "message": commit_message,
            "content": __import__("base64").b64encode(content.encode()).decode(),
        }
        if sha:
            put_data["sha"] = sha

        resp = await client.put(
            f"https://api.github.com/repos/{DEMO_REPO}/contents/{filename}",
            headers=headers,
            json=put_data,
        )

        if resp.status_code in (200, 201):
            data = resp.json()
            return {
                "filename": filename,
                "url": data["content"]["html_url"],
                "commit_sha": data["commit"]["sha"],
            }
        return {"error": f"GitHub API: HTTP {resp.status_code}", "detail": resp.text}


@trace("create_linear_ticket")
async def create_linear_ticket(title: str, description: str) -> dict:
    if not LINEAR_API_KEY:
        return {"error": "No LINEAR_API_KEY configured"}

    query = """
    mutation CreateIssue($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        issue {
          id
          url
          title
        }
      }
    }
    """

    variables = {
        "input": {
            "title": title,
            "description": description,
            "teamId": os.getenv("LINEAR_TEAM_ID", ""),
        }
    }

    headers = {
        "Authorization": LINEAR_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.linear.app/graphql",
                headers=headers,
                json={"query": query, "variables": variables},
            )
            if resp.status_code == 200:
                data = resp.json()
                issue = data.get("data", {}).get("issueCreate", {}).get("issue", {})
                return {
                    "linear_id": issue.get("id"),
                    "linear_url": issue.get("url"),
                }
            return {"error": f"Linear API: HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}
