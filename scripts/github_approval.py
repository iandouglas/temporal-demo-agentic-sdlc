"""Approve a run's promotion on GitHub the way a reviewer does, for the scripts that drive the demo.

The run dispatches the storefront's Release workflow and its job waits on an Environment with
required reviewers. This finds the waiting run (named ``release <gate> <issue:N|pr:N> #<ask>``) and
approves its pending deployment through the API, as your `gh` login: the same "Review deployments"
decision, so your login must be one of the Environment's reviewers.
"""

import json
import subprocess
import time

from agentic_sdlc import config


def _gh(*args: str, body: dict | None = None) -> object:
    command = ["gh", "api", *args] + (["--input", "-"] if body is not None else [])
    out = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out) if out.strip() else None


def approve(gate: str, subject: str, comment: str = "Approved by the demo's driver script", timeout: float = 120) -> None:
    repo = config.GITHUB_SANDBOX_REPO
    prefix = f"release {gate} {subject} #"
    deadline = time.time() + timeout
    while time.time() < deadline:
        runs = _gh(f"repos/{repo}/actions/workflows/release.yml/runs?status=waiting&per_page=50")["workflow_runs"]
        run = next((r for r in runs if (r.get("display_title") or "").startswith(prefix)), None)
        if run:
            pending = _gh(f"repos/{repo}/actions/runs/{run['id']}/pending_deployments")
            ids = [p["environment"]["id"] for p in pending if p["current_user_can_approve"]]
            if not ids:
                raise SystemExit(f"{run['html_url']} is waiting, but your gh login can't approve it: "
                                 "add it with scripts/setup-github.sh --reviewers")
            _gh("-X", "POST", f"repos/{repo}/actions/runs/{run['id']}/pending_deployments",
                body={"environment_ids": ids, "state": "approved", "comment": comment})
            return
        time.sleep(3)
    raise SystemExit(f"No waiting release run named '{prefix}…' after {timeout:.0f}s")
