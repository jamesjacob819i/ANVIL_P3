import os
import tempfile
import subprocess
import httpx
from pydantic import BaseModel, Field

from shared.llm import llm_call
from shared.tracing import trace

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DEMO_REPO = os.getenv("DEMO_REPO", "jamesjacobi/sentinel-demo")


class PatchOutput(BaseModel):
    patch: str = Field(description="Unified diff format patch")
    explanation: str = Field(description="Explanation of the fix")
    files_changed: list[str] = Field(description="List of files to modify")
    change_lines: int = Field(description="Total lines changed")


SYSTEM_PROMPT = """You are a remediation engineer. Generate a minimal, correct code patch to fix the root cause.

Rules:
1. Generate ONLY the exact diff/patch needed
2. Keep changes minimal (< 20 lines preferred)
3. The patch must be in unified diff format
4. Include file paths relative to repo root
5. Explain what the fix does

Target app is a Flask app with a /checkout endpoint that has a buggy coupon code handler."""


@trace("generate_patch")
async def generate_patch(root_cause: str, suspect_file: str, suspect_lines: str, source_code: str | None = None) -> dict:
    user_prompt = f"""Root cause: {root_cause}
Suspect file: {suspect_file}
Suspect lines: {suspect_lines}

Current source code:
{source_code or "Not available - generate fix based on root cause description"}

Generate a minimal patch to fix this issue."""

    result = await llm_call(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=PatchOutput,
    )

    return result


@trace("clone_repo")
async def clone_repo(incident_id: str) -> str:
    repo_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{DEMO_REPO}.git"
    clone_dir = f"/tmp/sentinel/{incident_id}"
    os.makedirs("/tmp/sentinel", exist_ok=True)

    if os.path.exists(clone_dir):
        subprocess.run(["rm", "-rf", clone_dir], check=True)

    result = subprocess.run(
        ["git", "clone", "--depth=1", repo_url, clone_dir],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Clone failed: {result.stderr}")

    return clone_dir


@trace("create_branch")
async def create_branch(repo_dir: str, incident_id: str) -> str:
    branch = f"sentinel/fix-{incident_id[:8]}"
    subprocess.run(
        ["git", "checkout", "-b", branch],
        cwd=repo_dir, capture_output=True, text=True, timeout=30,
    )
    return branch


@trace("apply_patch")
async def apply_patch(repo_dir: str, patch_content: str) -> bool:
    patch_file = os.path.join(repo_dir, "fix.patch")
    with open(patch_file, "w") as f:
        f.write(patch_content)

    result = subprocess.run(
        ["git", "apply", "fix.patch"],
        cwd=repo_dir, capture_output=True, text=True, timeout=30,
    )
    os.unlink(patch_file)
    return result.returncode == 0


@trace("run_tests_sandbox")
async def run_tests_sandbox(repo_dir: str) -> dict:
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "-q", "tests/" if os.path.exists(os.path.join(repo_dir, "tests")) else "."],
            cwd=repo_dir, capture_output=True, text=True, timeout=60,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
            "returncode": result.returncode,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@trace("commit_and_push")
async def commit_and_push(repo_dir: str, incident_id: str, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, capture_output=True, timeout=30)
    subprocess.run(
        ["git", "commit", "-m", f"sentinel: fix incident {incident_id[:8]} - {message}"],
        cwd=repo_dir, capture_output=True, timeout=30,
    )
    result = subprocess.run(
        ["git", "push", "origin", "HEAD"],
        cwd=repo_dir, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Push failed: {result.stderr}")
    return result.stdout


@trace("create_pr")
async def create_pr(incident_id: str, branch: str, title: str, body: str, auto_merge: bool = False) -> dict:
    if not GITHUB_TOKEN:
        return {"error": "No GITHUB_TOKEN configured"}

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    pr_data = {
        "title": title,
        "head": branch,
        "base": "main",
        "body": body,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{DEMO_REPO}/pulls",
            headers=headers,
            json=pr_data,
        )
        if resp.status_code not in (201, 200):
            return {"error": f"GitHub API: HTTP {resp.status_code}", "detail": resp.text}

        pr = resp.json()
        pr_number = pr["number"]
        pr_url = pr["html_url"]

        if auto_merge:
            await client.put(
                f"https://api.github.com/repos/{DEMO_REPO}/pulls/{pr_number}/merge",
                headers=headers,
                json={"merge_method": "squash"},
            )

        return {"pr_number": pr_number, "pr_url": pr_url, "auto_merged": auto_merge}
