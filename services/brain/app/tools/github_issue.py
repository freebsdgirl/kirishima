import json
import requests

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]

def github_issue(
    action: str,
    issue_id: str = None,
    title: str = None,
    body: str = None,
    assignees: list = None,
    labels: list = None,
    options: dict = None,
    comment_body: str = None
):
    """
    Manage GitHub issues: create, list, view, comment, or close an issue.
    Args:
        action (str): The action to perform.
        issue_id (str): The ID of the issue (for view, close, comment).
        title (str): The title of the issue (for create).
        body (str): The body content of the issue (for create).
        assignees (list): List of usernames to assign to the issue (optional).
        labels (list): List of labels (optional).
        options (dict): Additional GitHub API options (optional).
        comment_body (str): The body of the comment (for comment).
    Returns:
        dict: API response or error message.
    """
    repo = _config["github"]["repo"]
    token = _config["github"]["token"]
    api_url = f"https://api.github.com/repos/{repo}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "kirishima-app"
    }

    try:
        if action == "create":
            data = {"title": title, "body": body or ""}
            if assignees and isinstance(assignees, list) and any(a.strip() for a in assignees if isinstance(a, str)):
                data["assignees"] = [a for a in assignees if isinstance(a, str) and a.strip()]
            if labels:
                data["labels"] = labels
            if options:
                data.update(options)
            resp = requests.post(f"{api_url}/issues", json=data, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            issue = resp.json()
            # Return only the minimal useful fields
            return {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "html_url": issue.get("html_url")
            }

        elif action == "list":
            params = {}
            if assignees and isinstance(assignees, list) and len(assignees) == 1:
                params["assignee"] = assignees[0]
            if labels:
                params["labels"] = ",".join(labels)
            if options:
                params.update(options)
            resp = requests.get(f"{api_url}/issues", params=params, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            issues = resp.json()
            trimmed = []
            for issue in issues:
                trimmed.append({
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
            return trimmed

        elif action == "view":
            if not issue_id:
                return {"error": "Missing issue_id for view action."}
            resp = requests.get(f"{api_url}/issues/{issue_id}", headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            issue = resp.json()
            # Return only the minimal useful fields
            return {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "body": issue.get("body"),
                "html_url": issue.get("html_url")
            }

        elif action == "comment":
            if not issue_id or not comment_body:
                return {"error": "Missing issue_id or comment_body for comment action."}
            data = {"body": comment_body}
            resp = requests.post(f"{api_url}/issues/{issue_id}/comments", json=data, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            comment = resp.json()
            # Return only the minimal useful fields
            return {
                "id": comment.get("id"),
                "body": comment.get("body"),
                "user": comment.get("user", {}).get("login"),
                "html_url": comment.get("html_url")
            }

        elif action == "close":
            if not issue_id:
                return {"error": "Missing issue_id for close action."}
            data = {"state": "closed"}
            resp = requests.patch(f"{api_url}/issues/{issue_id}", json=data, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            issue = resp.json()
            # Return only the minimal useful fields
            return {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "body": issue.get("body"),
                "html_url": issue.get("html_url")
            }

        elif action == "list_comments":
            if not issue_id:
                return {"error": "Missing issue_id for list_comments action."}
            resp = requests.get(f"{api_url}/issues/{issue_id}/comments", headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            comments = resp.json()
            # Return a list of minimal comment fields
            return [
                {
                    "id": c.get("id"),
                    "body": c.get("body"),
                    "user": c.get("user", {}).get("login"),
                    "html_url": c.get("html_url")
                }
                for c in comments
            ]

        else:
            return {"error": f"Unknown action: {action}"}

    except requests.HTTPError as e:
        return {"error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
    except Exception as e:
        return {"error": str(e)}