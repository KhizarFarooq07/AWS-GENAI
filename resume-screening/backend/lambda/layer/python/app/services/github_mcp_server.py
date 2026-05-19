"""
GitHub MCP Server
=================
A real MCP server using the official MCP Python SDK.
Exposes GitHub data as tools via the @mcp.tool() decorator.

This server is spawned as a subprocess by GitHubService (the MCP client).
Communication happens over stdio using the MCP JSON-RPC protocol.

MCP Flow:
  GitHubService (MCP Client)
      └── spawns subprocess: python3 github_mcp_server.py
              └── MCP handshake (initialize)
              └── ClientSession.call_tool("get_user_profile", {username})
              └── ClientSession.call_tool("get_user_repos", {username})
              └── Returns results via MCP protocol over stdio
"""

import json
import logging
import os
import ssl
import urllib.request
import urllib.error
import urllib.parse

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Use certifi CA bundle if available (needed on macOS dev); Lambda has system certs
try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

# Create the MCP server — name identifies this server to clients
mcp = FastMCP("github-mcp-server")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _github_get(url: str, params: dict = None) -> dict:
    """HTTP GET to GitHub API using stdlib urllib (no external deps)."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            return {"status": resp.status, "body": json.loads(resp.read())}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": {}}
    except Exception as e:
        logger.error(f"[github_mcp_server] _github_get error: {type(e).__name__}: {e}")
        return {"status": 0, "body": {"error": str(e)}}


# ─── MCP Tools ────────────────────────────────────────────────────────────────
# The @mcp.tool() decorator registers each function as an MCP tool.
# The docstring becomes the tool description sent to the client.
# Type annotations become the input schema.

@mcp.tool()
def get_user_profile(username: str) -> str:
    """
    Fetch a GitHub user's public profile statistics including
    public_repos, followers, following, bio, company, and profile URL.
    """
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


@mcp.tool()
def get_user_repos(username: str, max_repos: int = 5) -> str:
    """
    Fetch a GitHub user's top public repositories sorted by stars.
    Returns repo list with stars, forks, language, and aggregate totals.
    """
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


if __name__ == "__main__":
    # Run as MCP server over stdio when spawned as a subprocess
    mcp.run(transport="stdio")
