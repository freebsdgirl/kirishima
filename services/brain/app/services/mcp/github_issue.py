"""
GitHub issue management service for MCP.
Direct implementation (not wrapper) of GitHub issue functionality.
"""

from shared.models.mcp import ToolCallResponse
from typing import Dict, Any
import json
import requests


async def github_issue(parameters: Dict[str, Any]) -> ToolCallResponse:
    """
    Manage GitHub issues - create, view, comment, close, list.
    Direct implementation for MCP server.
    """
    try:
        # Load config
        with open('/app/config/config.json') as f:
            config = json.load(f)
        
        # Extract parameters
        action = parameters.get("action", "create")
        issue_id = parameters.get("issue_id")
        title = parameters.get("title")
        body = parameters.get("body")
        assignees = parameters.get("assignees")
        labels = parameters.get("labels")
        options = parameters.get("options")
        comment_body = parameters.get("comment_body")
        
        # GitHub API setup
        repo = config["github"]["repo"]
        token = config["github"]["token"]
        timeout = config["timeout"]
        api_url = f"https://api.github.com/repos/{repo}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "kirishima-app"
        }

        if action == "create":
            data = {"title": title, "body": body or ""}
            if assignees and isinstance(assignees, list) and any(a.strip() for a in assignees if isinstance(a, str)):
                data["assignees"] = [a for a in assignees if isinstance(a, str) and a.strip()]
            if labels:
                data["labels"] = labels
            if options:
                data.update(options)
            
            resp = requests.post(f"{api_url}/issues", json=data, headers=headers, timeout=timeout)
            resp.raise_for_status()
            issue = resp.json()
            
            result = {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "html_url": issue.get("html_url")
            }
            return ToolCallResponse(result={"success": True, "data": result})

        elif action == "list":
            params = {}
            if assignees and isinstance(assignees, list) and len(assignees) == 1:
                params["assignee"] = assignees[0]
            if labels:
                params["labels"] = ",".join(labels)
            if options:
                params.update(options)
            
            resp = requests.get(f"{api_url}/issues", params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            issues = resp.json()
            
            result = []
            for issue in issues:
                result.append({
                    "number": issue.get("number"),
                    "title": issue.get("title"),
                    "state": issue.get("state"),
                    "assignees": [a.get("login") for a in issue.get("assignees", [])],
                    "labels": [l.get("name") for l in issue.get("labels", [])],
                    "html_url": issue.get("html_url"),
                    "body": (issue.get("body") or "")[:200],
                    "created_at": issue.get("created_at"),
                    "updated_at": issue.get("updated_at")
                })
            return ToolCallResponse(result={"success": True, "data": result})

        elif action == "view":
            if not issue_id:
                return ToolCallResponse(result={"success": False, "error": "Missing issue_id for view action"})
            
            resp = requests.get(f"{api_url}/issues/{issue_id}", headers=headers, timeout=timeout)
            resp.raise_for_status()
            issue = resp.json()
            
            result = {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "body": issue.get("body"),
                "html_url": issue.get("html_url")
            }
            return ToolCallResponse(result={"success": True, "data": result})

        elif action == "comment":
            if not issue_id or not comment_body:
                return ToolCallResponse(result={"success": False, "error": "Missing issue_id or comment_body for comment action"})
            
            data = {"body": comment_body}
            resp = requests.post(f"{api_url}/issues/{issue_id}/comments", json=data, headers=headers, timeout=timeout)
            resp.raise_for_status()
            comment = resp.json()
            
            result = {
                "id": comment.get("id"),
                "body": comment.get("body"),
                "user": comment.get("user", {}).get("login"),
                "html_url": comment.get("html_url")
            }
            return ToolCallResponse(result={"success": True, "data": result})

        elif action == "close":
            if not issue_id:
                return ToolCallResponse(result={"success": False, "error": "Missing issue_id for close action"})
            
            data = {"state": "closed"}
            resp = requests.patch(f"{api_url}/issues/{issue_id}", json=data, headers=headers, timeout=timeout)
            resp.raise_for_status()
            issue = resp.json()
            
            result = {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "body": issue.get("body"),
                "html_url": issue.get("html_url")
            }
            return ToolCallResponse(result={"success": True, "data": result})

        elif action == "list_comments":
            if not issue_id:
                return ToolCallResponse(result={"success": False, "error": "Missing issue_id for list_comments action"})
            
            resp = requests.get(f"{api_url}/issues/{issue_id}/comments", headers=headers, timeout=timeout)
            resp.raise_for_status()
            comments = resp.json()
            
            result = [
                {
                    "id": c.get("id"),
                    "body": c.get("body"),
                    "user": c.get("user", {}).get("login"),
                    "html_url": c.get("html_url")
                }
                for c in comments
            ]
            return ToolCallResponse(result={"success": True, "data": result})

        else:
            return ToolCallResponse(result={"success": False, "error": f"Unknown action: {action}"})

    except requests.HTTPError as e:
        error_msg = f"HTTP error: {e.response.status_code} - {e.response.text}"
        return ToolCallResponse(result={"success": False, "error": error_msg})
    except Exception as e:
        return ToolCallResponse(result={"success": False, "error": str(e)})
