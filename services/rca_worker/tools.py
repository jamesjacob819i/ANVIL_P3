import os
import httpx
from pydantic import BaseModel, Field

from shared.llm import llm_call
from shared.tracing import trace

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


@trace("web_search")
async def web_search(query: str) -> list[dict]:
    if not TAVILY_API_KEY:
        return [{"error": "No TAVILY_API_KEY configured", "query": query}]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "max_results": 5,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")[:500]}
                    for r in data.get("results", [])
                ]
            return [{"error": f"Tavily API: HTTP {resp.status_code}"}]
    except Exception as e:
        return [{"error": str(e)}]


@trace("read_source_code")
async def read_source_code(repo: str, file_path: str, ref: str = "main") -> dict:
    if not GITHUB_TOKEN:
        return {"error": "No GITHUB_TOKEN configured", "file": file_path}

    try:
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.raw",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"https://api.github.com/repos/{repo}/contents/{file_path}?ref={ref}"
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                content = resp.text
                lines = content.split("\n")
                return {
                    "file": file_path,
                    "repo": repo,
                    "ref": ref,
                    "total_lines": len(lines),
                    "content_preview": "\n".join(lines[:100]),
                    "truncated": len(lines) > 100,
                }
            return {"error": f"GitHub API: HTTP {resp.status_code}", "file": file_path}
    except Exception as e:
        return {"error": str(e), "file": file_path}
