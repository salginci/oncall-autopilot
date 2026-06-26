import json
from openai import OpenAI
from src.config import settings
from src.orchestrator.models import Incident
from src.tools.github import github_tool
from src.tools.metrics import metrics_tool
from src.tools.health import health_tool
from src.tools.deploy import deploy_tool
from src.observability import logger


SYSTEM_PROMPT = """You are a root-cause analysis SRE agent. You have access to these tools:
- get_recent_commits(): Returns recent commits to the repository. Call this first.
- get_commit_diff(sha): Returns the full diff for a specific commit.
- get_error_rate(): Returns current error rate and latency metrics.
- get_health(): Returns service health status.
- get_config(): Returns current service configuration.

Investigation protocol:
1. Check recent commits for config changes or code changes
2. Check error rate and latency to understand the symptom
3. If a suspicious commit is found, get its diff
4. Form a root cause hypothesis
5. If config-related, check current config

Respond as JSON with:
{
  "root_cause": "concise root cause description",
  "confidence": 0.0-1.0,
  "evidence": ["evidence point 1", "evidence point 2"],
  "suggested_fix": "what should be done to fix this",
  "status": "success" or "inconclusive"
}"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_commits",
            "description": "Get recent commits to the repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "since_minutes": {"type": "integer", "description": "Minutes to look back"},
                    "limit": {"type": "integer", "description": "Max number of commits"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_commit_diff",
            "description": "Get the diff for a specific commit by SHA",
            "parameters": {
                "type": "object",
                "properties": {
                    "commit_sha": {"type": "string"},
                },
                "required": ["commit_sha"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_error_rate",
            "description": "Get current error rate and latency metrics from the service",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_health",
            "description": "Get service health status including pool state",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_config",
            "description": "Get current service configuration",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

TOOL_MAP = {
    "get_recent_commits": lambda **kw: github_tool.get_recent_commits(**kw),
    "get_commit_diff": lambda **kw: github_tool.get_commit_diff(kw["commit_sha"]),
    "get_error_rate": lambda **kw: metrics_tool.get_error_rate(),
    "get_health": lambda **kw: health_tool.check(),
    "get_config": lambda **kw: deploy_tool.get_config(),
}


async def run_investigation(incident: Incident) -> dict:
    trace_id = incident.trace_id

    client = OpenAI(
        base_url=settings.QWEN_BASE_URL,
        api_key=settings.QWEN_API,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Incident #{incident.incident_id}

Service: {incident.alert.service}
Alert: {incident.alert.title}
Description: {incident.alert.description}
Triage severity: {incident.severity.value if incident.severity else 'UNKNOWN'}
Triage summary: {incident.triage_summary or 'N/A'}

Investigate the root cause. Start by checking recent commits and service health.""",
        },
    ]

    logger.info(trace_id, incident.incident_id, event="investigation_started")

    max_turns = 5
    for turn in range(max_turns):
        logger.info(trace_id, incident.incident_id, event="investigation_qwen_call", turn=turn + 1)

        try:
            response = client.chat.completions.create(
                model=settings.QWEN_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                temperature=0.1,
            )
        except Exception as e:
            logger.error(trace_id, incident.incident_id, event="investigation_error", error=str(e))
            return {
                "root_cause": f"Investigation failed: {str(e)}",
                "confidence": 0.0,
                "evidence": [],
                "suggested_fix": "Manual investigation required",
                "status": "error",
            }

        choice = response.choices[0]
        assistant_msg = choice.message

        if assistant_msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in assistant_msg.tool_calls
                ],
            })

            for tc in assistant_msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                logger.info(trace_id, incident.incident_id, event="tool_call", tool=tool_name, args=tool_args)

                handler = TOOL_MAP.get(tool_name)
                if handler:
                    result = await handler(**tool_args)
                    if hasattr(result, '__await__'):
                        result = await result
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}

                if hasattr(result, '__iter__') and not isinstance(result, (str, dict)):
                    result = [r.model_dump() if hasattr(r, 'model_dump') else str(r) for r in result]

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })
        else:
            content = assistant_msg.content or ""
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                result = {
                    "root_cause": content,
                    "confidence": 0.5,
                    "evidence": [],
                    "suggested_fix": "See analysis above",
                    "status": "success",
                }

            logger.info(trace_id, incident.incident_id, event="investigation_complete", **result)
            return result

    return {
        "root_cause": "Investigation reached max turns without conclusion",
        "confidence": 0.3,
        "evidence": [],
        "suggested_fix": "Manual investigation required",
        "status": "inconclusive",
    }
