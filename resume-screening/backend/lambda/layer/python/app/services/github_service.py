"""
GitHub Service — Bedrock-Orchestrated MCP Client
=================================================
Uses Claude (via AWS Bedrock Converse API) as the orchestrator.
Claude receives the MCP tool schemas and decides which tools to call.
We execute each tool call Claude requests, feed results back, and
Claude synthesizes the final GitHub profile.

Architecture:
  GitHubService.fetch_github_stats(username)
      │
      ├─ 1. Load tool schemas from github_mcp_server.TOOL_DEFINITIONS
      │
      ├─ 2. Send prompt + tool schemas to Claude via Bedrock Converse API
      │         "Here are your tools. Fetch GitHub stats for username X"
      │
      ├─ 3. Claude responds with tool_use blocks (e.g. get_user_profile)
      │
      ├─ 4. We call github_mcp_server.execute_tool() for each requested tool
      │
      ├─ 5. Feed tool results back to Claude
      │
      ├─ 6. Claude may call more tools (e.g. get_user_repos)
      │
      └─ 7. Claude returns final text summary → we parse into structured dict
"""

import json
import logging
import os
import re

import boto3

from .github_mcp_server import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
CLAUDE_MODEL_ID = "us.amazon.nova-lite-v1:0"
MAX_AGENT_ITERATIONS = 6  # Safety limit on tool-call rounds


class GitHubService:
    """
    Fetches GitHub stats using Claude (Bedrock) as the MCP orchestrator.
    Claude decides which MCP tools to call; we execute them and feed results back.
    """

    def __init__(self):
        self._bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    def extract_github_username(self, text: str) -> str | None:
        """
        Extract GitHub username from resume text.
        Matches patterns like github.com/username or 'GitHub: username'.
        """
        ignore = {"features", "about", "enterprise", "pricing", "marketplace",
                  "explore", "topics", "trending", "collections", "sponsors"}
        patterns = [
            r'github\.com/([a-zA-Z0-9][a-zA-Z0-9\-]{0,38})',
            r'(?i)github[:\s]+([a-zA-Z0-9][a-zA-Z0-9\-]{0,38})',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                candidate = match.group(1).rstrip("/")
                if candidate.lower() not in ignore:
                    return candidate
        return None

    def fetch_github_stats(self, username: str) -> dict:
        """
        Ask Claude (Bedrock) to fetch GitHub stats using MCP tools.

        Claude receives the tool schemas and orchestrates which tools to call.
        This method runs the agentic tool-use loop until Claude is done.
        """
        logger.info(f"🐙 Asking Claude to fetch GitHub stats for '{username}' via MCP tools")

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "text": (
                            f"Use the available tools to fetch the public GitHub profile "
                            f"and top repositories for the username: '{username}'. "
                            f"Retrieve their profile stats and top repos, then provide "
                            f"a structured summary."
                        )
                    }
                ]
            }
        ]

        # Agentic loop: Claude calls tools until it returns a final text response
        for iteration in range(MAX_AGENT_ITERATIONS):
            logger.info(f"[MCP Agent] Iteration {iteration + 1} — calling Bedrock Converse")

            response = self._bedrock.converse(
                modelId=CLAUDE_MODEL_ID,
                messages=messages,
                toolConfig={"tools": TOOL_DEFINITIONS},
                inferenceConfig={"maxTokens": 1024, "temperature": 0}
            )

            stop_reason = response["stopReason"]
            assistant_content = response["output"]["message"]["content"]

            # Append Claude's response to conversation
            messages.append({"role": "assistant", "content": assistant_content})

            if stop_reason == "end_turn":
                # Claude finished — extract text from final response
                final_text = next(
                    (block["text"] for block in assistant_content if "text" in block), ""
                )
                logger.info(f"[MCP Agent] Claude finished. Summary:\n{final_text[:300]}")
                return self._parse_claude_summary(final_text, username)

            if stop_reason == "tool_use":
                # Execute every tool Claude requested in this turn
                tool_results = []
                for block in assistant_content:
                    if "toolUse" not in block:
                        continue
                    tool_use = block["toolUse"]
                    tool_id = tool_use["toolUseId"]
                    tool_name = tool_use["name"]
                    tool_input = tool_use["input"]

                    logger.info(f"[MCP Tool] Claude requested: {tool_name}({tool_input})")
                    result_content = execute_tool(tool_name, tool_input)
                    logger.info(f"[MCP Tool] Result: {result_content[:200]}")

                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_id,
                            "content": [{"text": result_content}]
                        }
                    })

                # Feed all tool results back to Claude
                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason
            logger.warning(f"[MCP Agent] Unexpected stop_reason: {stop_reason}")
            break

        return {"status": "error", "error": "Agent loop exceeded max iterations", "username": username}

    def _parse_claude_summary(self, text: str, username: str) -> dict:
        """
        Parse Claude's final text summary back into a structured dict.
        We also re-read the raw tool results that were already stored in the
        messages list by looking at the last known tool_results. For simplicity
        we fetch the raw data by calling execute_tool directly one more time so
        the structured fields are always populated correctly regardless of how
        Claude words its summary.
        """
        try:
            raw_profile = json.loads(execute_tool("get_user_profile", {"username": username}))
            raw_repos = json.loads(execute_tool("get_user_repos", {"username": username, "max_repos": 5}))

            if "error" in raw_profile:
                return {"status": "error", "error": raw_profile["error"], "username": username}

            return {
                "status": "success",
                "username": raw_profile.get("username", username),
                "name": raw_profile.get("name"),
                "bio": raw_profile.get("bio"),
                "company": raw_profile.get("company"),
                "profile_url": raw_profile.get("profile_url"),
                "public_repos": raw_profile.get("public_repos", 0),
                "followers": raw_profile.get("followers", 0),
                "following": raw_profile.get("following", 0),
                "total_stars": raw_repos.get("total_stars", 0),
                "total_forks": raw_repos.get("total_forks", 0),
                "languages": raw_repos.get("languages", []),
                "top_repos": raw_repos.get("repos", []),
                "claude_summary": text,
            }
        except Exception as e:
            logger.error(f"Failed to parse Claude summary: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "username": username}
