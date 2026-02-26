"""github_issue tool — manage GitHub issues via the GitHub API.

Actions: create, list, view, comment, close, list_comments.
Uses httpx (async) instead of the legacy sync requests.
"""

import json
from typing import Any, Dict

import httpx

from app.tools.base import tool, ToolResponse
from shared.log_config import get_logger

logger = get_logger(f"brain.{__name__}")


def _load_github_config() -> Dict[str, Any]:
    """Load GitHub config (repo, token, timeout) from config.json."""
    with open("/app/config/config.json") as f:
        config = json.load(f)
    return {
        "repo": config["github"]["repo"],
        "token": config["github"]["token"],
        "timeout": config.get("timeout", 120),
    }


@tool(
    name="github_issue",
    description="Manage GitHub issues - create, view, comment, close, list issues and comments",
    persistent=True,
    always=False,
    clients=["internal", "copilot"],
    service="github",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "view", "comment", "close", "list_comments"],
                "description": "The action to perform on GitHub issues",
            },
            "issue_id": {"type": "string", "description": "Issue ID for view, comment, close, list_comments actions"},
            "title": {"type": "string", "description": "Issue title for create action"},
            "body": {"type": "string", "description": "Issue body content for create action"},
            "assignees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of usernames to assign",
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of labels to apply",
            },
            "options": {"type": "object", "description": "Additional GitHub API options"},
            "comment_body": {"type": "string", "description": "Comment content for comment action"},
        },
        "required": ["action"],
    },
)
async def github_issue(parameters: dict) -> ToolResponse:
    """Dispatch to the appropriate GitHub issue action."""
    action = parameters.get("action", "create")

    try:
        cfg = _load_github_config()
    except Exception as e:
        return ToolResponse(error=f"Failed to load GitHub config: {e}")

    api_url = f"https://api.github.com/repos/{cfg['repo']}"
    headers = {
        "Authorization": f"token {cfg['token']}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "kirishima-app",
    }
    timeout = cfg["timeout"]

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if action == "create":
                return await _create(client, api_url, headers, parameters)
            elif action == "list":
                return await _list(client, api_url, headers, parameters)
            elif action == "view":
                return await _view(client, api_url, headers, parameters)
            elif action == "comment":
                return await _comment(client, api_url, headers, parameters)
            elif action == "close":
                return await _close(client, api_url, headers, parameters)
            elif action == "list_comments":
                return await _list_comments(client, api_url, headers, parameters)
            else:
                return ToolResponse(error=f"Unknown action: {action}")

    except httpx.HTTPStatusError as e:
        error_msg = f"GitHub API error: {e.response.status_code} — {e.response.text}"
        logger.error(error_msg)
        return ToolResponse(error=error_msg)
    except Exception as e:
        logger.error("github_issue error: %s", e, exc_info=True)
        return ToolResponse(error=str(e))


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

async def _create(client: httpx.AsyncClient, api_url: str, headers: dict, params: dict) -> ToolResponse:
    data: Dict[str, Any] = {"title": params.get("title", ""), "body": params.get("body", "")}

    assignees = params.get("assignees")
    if assignees and isinstance(assignees, list):
        clean = [a for a in assignees if isinstance(a, str) and a.strip()]
        if clean:
            data["assignees"] = clean

    labels = params.get("labels")
    if labels:
        data["labels"] = labels

    options = params.get("options")
    if options:
        data.update(options)

    resp = await client.post(f"{api_url}/issues", json=data, headers=headers)
    resp.raise_for_status()
    issue = resp.json()

    return ToolResponse(result={
        "number": issue.get("number"),
        "title": issue.get("title"),
        "html_url": issue.get("html_url"),
    })


async def _list(client: httpx.AsyncClient, api_url: str, headers: dict, params: dict) -> ToolResponse:
    query_params: Dict[str, Any] = {}

    assignees = params.get("assignees")
    if assignees and isinstance(assignees, list) and len(assignees) == 1:
        query_params["assignee"] = assignees[0]

    labels = params.get("labels")
    if labels:
        query_params["labels"] = ",".join(labels)

    options = params.get("options")
    if options:
        query_params.update(options)

    resp = await client.get(f"{api_url}/issues", params=query_params, headers=headers)
    resp.raise_for_status()
    issues = resp.json()

    result = [
        {
            "number": issue.get("number"),
            "title": issue.get("title"),
            "state": issue.get("state"),
            "assignees": [a.get("login") for a in issue.get("assignees", [])],
            "labels": [lbl.get("name") for lbl in issue.get("labels", [])],
            "html_url": issue.get("html_url"),
            "body": (issue.get("body") or "")[:200],
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
        }
        for issue in issues
    ]
    return ToolResponse(result=result)


async def _view(client: httpx.AsyncClient, api_url: str, headers: dict, params: dict) -> ToolResponse:
    issue_id = params.get("issue_id")
    if not issue_id:
        return ToolResponse(error="Missing issue_id for view action")

    resp = await client.get(f"{api_url}/issues/{issue_id}", headers=headers)
    resp.raise_for_status()
    issue = resp.json()

    return ToolResponse(result={
        "number": issue.get("number"),
        "title": issue.get("title"),
        "body": issue.get("body"),
        "html_url": issue.get("html_url"),
    })


async def _comment(client: httpx.AsyncClient, api_url: str, headers: dict, params: dict) -> ToolResponse:
    issue_id = params.get("issue_id")
    comment_body = params.get("comment_body")
    if not issue_id or not comment_body:
        return ToolResponse(error="Missing issue_id or comment_body for comment action")

    resp = await client.post(
        f"{api_url}/issues/{issue_id}/comments",
        json={"body": comment_body},
        headers=headers,
    )
    resp.raise_for_status()
    comment = resp.json()

    return ToolResponse(result={
        "id": comment.get("id"),
        "body": comment.get("body"),
        "user": comment.get("user", {}).get("login"),
        "html_url": comment.get("html_url"),
    })


async def _close(client: httpx.AsyncClient, api_url: str, headers: dict, params: dict) -> ToolResponse:
    issue_id = params.get("issue_id")
    if not issue_id:
        return ToolResponse(error="Missing issue_id for close action")

    resp = await client.patch(
        f"{api_url}/issues/{issue_id}",
        json={"state": "closed"},
        headers=headers,
    )
    resp.raise_for_status()
    issue = resp.json()

    return ToolResponse(result={
        "number": issue.get("number"),
        "title": issue.get("title"),
        "html_url": issue.get("html_url"),
    })


async def _list_comments(client: httpx.AsyncClient, api_url: str, headers: dict, params: dict) -> ToolResponse:
    issue_id = params.get("issue_id")
    if not issue_id:
        return ToolResponse(error="Missing issue_id for list_comments action")

    resp = await client.get(f"{api_url}/issues/{issue_id}/comments", headers=headers)
    resp.raise_for_status()
    comments = resp.json()

    result = [
        {
            "id": c.get("id"),
            "body": c.get("body"),
            "user": c.get("user", {}).get("login"),
            "html_url": c.get("html_url"),
        }
        for c in comments
    ]
    return ToolResponse(result=result)
