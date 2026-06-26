import json
from openai import OpenAI
from src.config import settings
from src.orchestrator.models import Incident
from src.observability import logger


SYSTEM_PROMPT = """You are a remediation SRE agent. Given a root cause analysis, generate a concrete fix plan.

Output as JSON:
{
  "action": "short description of the fix",
  "commands": ["specific command 1", "specific command 2"],
  "rollback_plan": "how to undo if something goes wrong",
  "risk": "LOW/MEDIUM/HIGH",
  "requires_approval": true/false
}

CRITICAL RULES:
- If the root cause involves a commit that changed a config file (e.g., pool_size was reduced), the ONLY fix command should be: "revert commit <commit_sha_or_any_similar>"
- Always include exactly one "revert commit <sha>" command if a commit caused the issue
- DO NOT suggest generic commands like sed, git, or make. Only use "revert commit <sha>".
- Always set requires_approval to true
- Risk assessment: LOW=trivial change, MEDIUM=config change, HIGH=code change/revert

Respond ONLY as JSON."""


async def run_remediation(incident: Incident) -> dict:
    trace_id = incident.trace_id

    if not incident.root_cause:
        return {
            "action": "No root cause available",
            "commands": [],
            "rollback_plan": "N/A",
            "risk": "MEDIUM",
            "requires_approval": True,
        }

    client = OpenAI(
        base_url=settings.QWEN_BASE_URL,
        api_key=settings.QWEN_API,
    )

    user_prompt = f"""Incident #{incident.incident_id}

Root Cause: {incident.root_cause.summary}
Confidence: {incident.root_cause.confidence}
Evidence: {json.dumps(incident.root_cause.evidence)}
Suggested Fix (from investigation): {incident.root_cause.suggested_fix}

Generate a concrete remediation plan."""

    logger.info(trace_id, incident.incident_id, event="remediation_calling_qwen")

    try:
        response = client.chat.completions.create(
            model=settings.QWEN_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        logger.info(trace_id, incident.incident_id, event="remediation_result", **result)

        return {
            "action": result.get("action", "Unknown action"),
            "commands": result.get("commands", []),
            "rollback_plan": result.get("rollback_plan", ""),
            "risk": result.get("risk", "MEDIUM"),
            "requires_approval": result.get("requires_approval", True),
        }

    except Exception as e:
        logger.error(trace_id, incident.incident_id, event="remediation_error", error=str(e))
        return {
            "action": f"Remediation failed: {str(e)}",
            "commands": [],
            "rollback_plan": "Manual intervention required",
            "risk": "HIGH",
            "requires_approval": True,
        }
