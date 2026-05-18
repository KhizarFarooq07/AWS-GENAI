"""
GitHub MCP Server — Tool Definitions + Executor
================================================
This module does two things:

1. TOOL DEFINITIONS (MCP schema)
   Defines the tool schemas that get sent to Claude (Bedrock) so Claude
   knows what tools are available and what arguments they expect.

2. TOOL EXECUTOR
   Implements execute_tool() which carries out whatever tool call
   Claude requests (get_user_profile, get_user_repos).

MCP Flow (orchestrated by GitHubService via Bedrock):

  GitHubService
      └── sends tool schemas + prompt to Claude (Bedrock Converse API)
              └── Claude decides: "I need to call get_user_profile"
              └── GitHubService calls execute_tool("get_user_profile", {...})
                      └── this file executes the GitHub REST API call
              └── GitHubService feeds result back to Claude
              └── Claude calls get_user_repos next
              └── GitHubService feeds result back
              └── Claude returns final synthesized summary
"""

import json
import logging
import os
import urllib.request
import urllib.error
import urllib.parse

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# ─── Tool Schemas (sent to Claude via Bedrock) ────────────────────────────────
# These follow the Bedrock Converse API tool spec format.

TOOL_DEFINITIONS = [
    {
        "toolSpec": {
            "name": "get_user_profile",
            "description": (
                "Fetch a GitHub user's public profile statistics including "
                "number of public repositories, followers, following count, "
                "bio, company, and profile URL."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "description": "The GitHub username to look up (e.g. 'torvalds')"
                        }
                    },
                    "required": ["username"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_user_repos",
            "description": (
                "Fetch a GitHub user's top public repositories sorted by stars. "
                "Returns repo names, star counts, fork counts, primary language, "
                "and aggregate totals."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "description": "The GitHub username"
                        },
                        "max_repos": {
                            "type": "integer",
                            "description": "Maximum number of repos to return (default 5)",
                            "default": 5
                        }
                    },
                    "required": ["username"]
                }
            }
        }
    }
]


# ─── Tool Executor ────────────────────────────────────────────────────────────

def _github_get(url: str, params: dict = None) -> dict:
    """Make a GitHub API GET request using urllib (no external dependencies)."""
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"status": resp.status, "body": json.loads(resp.read())}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": {}}
    except Exception as e:
        return {"status": 0, "body": {"error": str(e)}}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Execute the tool Claude requested and return the result as a JSON string.
    This is called by GitHubService inside the Bedrock agentic loop.
    """
    logger.info(f"[MCP Tool] Executing: {tool_name}({tool_input})")

    if tool_name == "get_user_profile":
        return _get_user_profile(tool_input["username"])

    if tool_name == "get_user_repos":
        return _get_user_repos(
            tool_input["username"],
            tool_input.get("max_repos", 5)
        )

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def _get_user_profile(username: str) -> str:
    result = _github_get(f"https://api.github.com/users/{username}")
    if result["status"] == 404:
        return json.dumps({"error": f"GitHub user '{username}' not found"})
    if result["status"] != 200:
        return json.dumps({"error": f"GitHub API error {result['status']}"})

    d = result["body"]
    return json.dumps({
        "username": d["login"],
        "name": d.get("name"),
        "bio": d.get("bio"),
        "company": d.get("company"),
        "location": d.get("location"),
        "public_repos": d.get("public_repos", 0),
        "followers": d.get("followers", 0),
        "following": d.get("following", 0),
        "profile_url": d.get("html_url"),
    })


def _get_user_repos(username: str, max_repos: int = 5) -> str:
    result = _github_get(
        f"https://api.github.com/users/{username}/repos",
        params={"sort": "stars", "direction": "desc", "per_page": max_repos, "type": "public"}
    )
    if result["status"] == 404:
        return json.dumps({"error": f"GitHub user '{username}' not found"})
    if result["status"] != 200:
        return json.dumps({"error": f"GitHub API error {result['status']}"})

    repos = result["body"]
    repo_list = [
        {
            "name": r["name"],
            "description": r.get("description"),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "language": r.get("language"),
            "url": r.get("html_url"),
        }
        for r in repos
    ]
    languages = list({r["language"] for r in repo_list if r.get("language")})

    return json.dumps({
        "repos": repo_list,
        "total_stars": sum(r["stars"] for r in repo_list),
        "total_forks": sum(r["forks"] for r in repo_list),
        "languages": languages,
    })
