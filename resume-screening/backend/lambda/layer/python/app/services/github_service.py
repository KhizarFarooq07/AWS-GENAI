"""
GitHub Service — Bedrock Agent + MCP Tools
==========================================
Uses Amazon Bedrock Converse API (us.amazon.nova-lite-v1:0) as the AI orchestrator.
Bedrock decides which MCP tools to call and in what order (agentic loop).

Architecture:
  GitHubService.fetch_github_stats(username)
      └── asyncio.run(_run_bedrock_mcp_agent(username))
              └── stdio_client spawns: python3 github_mcp_server.py
                      └── session.initialize()         ← MCP handshake
                      └── session.list_tools()         ← discover available tools
                      └── _build_tool_config(tools)    ← convert to Bedrock format
                      └── [Agentic Loop]
                              └── bedrock.converse(modelId, messages, toolConfig)
                              └── if stopReason == "tool_use":
                                      └── session.call_tool(name, args)  ← MCP executes
                                      └── feed result back to Bedrock
                              └── if stopReason == "end_turn":
                                      └── parse Bedrock's final JSON response
"""

import asyncio
import json
import logging
import os
import re
import sys

import boto3
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)

# Absolute path to the MCP server script (same directory as this file)
_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "github_mcp_server.py")

# Bedrock model — Nova Lite supports Converse API with tool use
_BEDROCK_MODEL = "us.amazon.nova-lite-v1:0"

_SYSTEM_PROMPT = (
    "You are a GitHub data fetcher. Use the provided tools to fetch GitHub user data. "
    "Always call get_user_profile first, then get_user_repos. "
    "After fetching all data, return ONLY a valid JSON object with these exact fields: "
    "status (set to 'success'), username, name, bio, company, profile_url, "
    "public_repos, followers, following, total_stars, total_forks, "
    "languages (array of strings), top_repos (array of objects with name, stars, forks, "
    "language, url, description). Output only the JSON — no markdown, no explanation."
)


class GitHubService:
    """
    Bedrock-orchestrated MCP client.
    Bedrock Converse API (Nova Lite) acts as the agent deciding which tools to call.
    The MCP server (github_mcp_server.py) executes the actual tools via stdio transport.
    """

    def __init__(self):
        self.bedrock = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )

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
        Fetch GitHub stats via Bedrock-orchestrated MCP tool calls.
        Bedrock decides which tools to call; MCP server executes them.
        """
        logger.info(f"🐙 [Bedrock+MCP] Fetching GitHub stats for '{username}' via Nova Lite")
        try:
            return asyncio.run(self._run_bedrock_mcp_agent(username))
        except Exception as e:
            logger.error(f"[Bedrock+MCP] Failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "username": username}

    async def _run_bedrock_mcp_agent(self, username: str) -> dict:
        """
        Agentic loop using Bedrock Converse + MCP stdio tools:
        1. Spawn MCP server subprocess, perform handshake
        2. Discover tools via session.list_tools()
        3. Convert MCP tool schemas → Bedrock toolConfig format
        4. Send initial task to Bedrock (Nova Lite)
        5. Loop: Bedrock returns tool_use → call via MCP → feed result back
        6. When Bedrock returns end_turn → parse JSON response and return
        """
        # Lambda layers are at /opt/python but child processes don't inherit it
        env = {**os.environ}
        layer_path = "/opt/python"
        existing = env.get("PYTHONPATH", "")
        if layer_path not in existing.split(os.pathsep):
            env["PYTHONPATH"] = f"{layer_path}{os.pathsep}{existing}".rstrip(os.pathsep)

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[_SERVER_SCRIPT],
            env=env,
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                logger.info("[Bedrock+MCP] MCP session initialized")

                # Discover tools from MCP server and convert to Bedrock format
                tools_response = await session.list_tools()
                tool_config = self._build_tool_config(tools_response.tools)
                logger.info(f"[Bedrock+MCP] Discovered {len(tools_response.tools)} MCP tools: "
                            f"{[t.name for t in tools_response.tools]}")

                # Initial prompt to Bedrock
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": (
                                    f"Fetch the GitHub profile stats and top repositories for "
                                    f"the user '{username}'. Use the available tools to get all data, "
                                    f"then return a JSON object with status, username, name, bio, "
                                    f"company, profile_url, public_repos, followers, following, "
                                    f"total_stars, total_forks, languages, and top_repos."
                                )
                            }
                        ],
                    }
                ]

                # Accumulated raw tool results — used as fallback if JSON parse fails
                accumulated_tool_results: dict = {}

                # Agentic loop — Bedrock orchestrates tool calls until end_turn
                for iteration in range(10):  # max 10 iterations (safety limit)
                    logger.info(f"[Bedrock+MCP] Converse call #{iteration + 1}, "
                                f"messages={len(messages)}")

                    response = self.bedrock.converse(
                        modelId=_BEDROCK_MODEL,
                        system=[{"text": _SYSTEM_PROMPT}],
                        messages=messages,
                        toolConfig=tool_config,
                    )

                    stop_reason = response["stopReason"]
                    assistant_msg = response["output"]["message"]
                    messages.append(assistant_msg)
                    logger.info(f"[Bedrock+MCP] stopReason={stop_reason}")

                    if stop_reason == "tool_use":
                        # Bedrock wants to call one or more tools — execute via MCP
                        tool_results = []
                        for block in assistant_msg["content"]:
                            if not block.get("toolUse"):
                                continue
                            tool_use = block["toolUse"]
                            tool_name = tool_use["name"]
                            tool_input = tool_use["input"]
                            tool_use_id = tool_use["toolUseId"]

                            logger.info(f"[Bedrock+MCP] Bedrock requested tool: "
                                        f"{tool_name}({tool_input})")
                            try:
                                mcp_result = await session.call_tool(tool_name, tool_input)
                                result_text = mcp_result.content[0].text
                                logger.info(f"[Bedrock+MCP] MCP result: {result_text[:200]}")
                                accumulated_tool_results[tool_name] = json.loads(result_text)
                                tool_results.append({
                                    "toolResult": {
                                        "toolUseId": tool_use_id,
                                        "content": [{"text": result_text}],
                                        "status": "success",
                                    }
                                })
                            except Exception as e:
                                logger.error(f"[Bedrock+MCP] MCP tool call failed: {e}")
                                tool_results.append({
                                    "toolResult": {
                                        "toolUseId": tool_use_id,
                                        "content": [{"text": json.dumps({"error": str(e)})}],
                                        "status": "error",
                                    }
                                })

                        # Feed all tool results back to Bedrock as a user message
                        messages.append({"role": "user", "content": tool_results})

                    elif stop_reason == "end_turn":
                        # Bedrock finished — extract its final text response
                        final_text = "".join(
                            block.get("text", "")
                            for block in assistant_msg["content"]
                            if isinstance(block, dict) and block.get("text")
                        )
                        logger.info(f"[Bedrock+MCP] Final response: {final_text[:300]}")

                        # Try to parse Bedrock's JSON output
                        try:
                            clean = re.sub(r"```(?:json)?\s*", "", final_text)
                            clean = clean.strip().rstrip("`").strip()
                            result = json.loads(clean)
                            result["status"] = "success"
                            return result
                        except json.JSONDecodeError:
                            logger.warning("[Bedrock+MCP] JSON parse failed, "
                                           "falling back to accumulated tool results")
                            return self._build_from_tool_results(username, accumulated_tool_results)
                    else:
                        logger.warning(f"[Bedrock+MCP] Unexpected stopReason: {stop_reason}")
                        break

        return self._build_from_tool_results(username, accumulated_tool_results)

    def _build_tool_config(self, tools) -> dict:
        """Convert MCP tool list → Bedrock Converse toolConfig format."""
        bedrock_tools = []
        for tool in tools:
            if hasattr(tool, "inputSchema") and tool.inputSchema:
                schema = (
                    tool.inputSchema.model_dump(exclude_none=True)
                    if hasattr(tool.inputSchema, "model_dump")
                    else tool.inputSchema
                    if isinstance(tool.inputSchema, dict)
                    else {"type": "object", "properties": {}}
                )
            else:
                schema = {"type": "object", "properties": {}}

            bedrock_tools.append({
                "toolSpec": {
                    "name": tool.name,
                    "description": tool.description or f"Tool: {tool.name}",
                    "inputSchema": {"json": schema},
                }
            })

        return {"tools": bedrock_tools}

    def _build_from_tool_results(self, username: str, results: dict) -> dict:
        """Fallback: build stats dict directly from accumulated MCP tool results."""
        profile = results.get("get_user_profile", {})
        repos_data = results.get("get_user_repos", {})
        return {
            "status": "success" if profile and "error" not in profile else "error",
            "username": profile.get("username", username),
            "name": profile.get("name"),
            "bio": profile.get("bio"),
            "company": profile.get("company"),
            "profile_url": profile.get("profile_url"),
            "public_repos": profile.get("public_repos", 0),
            "followers": profile.get("followers", 0),
            "following": profile.get("following", 0),
            "total_stars": repos_data.get("total_stars", 0),
            "total_forks": repos_data.get("total_forks", 0),
            "languages": repos_data.get("languages", []),
            "top_repos": repos_data.get("repos", []),
        }
