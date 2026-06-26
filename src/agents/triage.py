import json
from openai import OpenAI
from src.config import settings
from src.orchestrator.models import Alert, Incident, Severity
from src.observability import logger


SYSTEM_PROMPT = """You are an on-call SRE triage agent. Given a production alert, assess:
1. Severity (LOW/MEDIUM/HIGH/CRITICAL) based on error rate, affected service, and potential blast radius
2. Whether to escalate to investigation (only escalate if severity >= MEDIUM)
3. A short summary of the situation

Guidelines:
- CRITICAL: customer-facing outage, high error rate (>50%), revenue impact
- HIGH: significant degradation, error rate 20-50%, latency spike >5x
- MEDIUM: moderate impact, error rate 5-20%, isolated errors
- LOW: transient blip, single error, no pattern

Respond ONLY as JSON with no other text."""


async def run_triage(incident: Incident) -> dict:
    trace_id = incident.trace_id
    alert = incident.alert

    client = OpenAI(
        base_url=settings.QWEN_BASE_URL,
        api_key=settings.QWEN_API,
    )

    user_prompt = f"""
Alert:
  Service: {alert.service}
  Title: {alert.title}
  Description: {alert.description}
  Error Rate: {alert.error_rate or 'unknown'}
  Latency p50: {alert.latency_p50_ms or 'unknown'}ms
  Time: {alert.timestamp.isoformat()}
"""

    logger.info(trace_id, incident.incident_id, event="triage_calling_qwen", model=settings.QWEN_MODEL)

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

        logger.info(trace_id, incident.incident_id, event="triage_result", **result)

        return {
            "severity": result.get("severity", "MEDIUM"),
            "summary": result.get("summary", ""),
            "should_investigate": result.get("should_investigate", True),
            "reasoning": result.get("reasoning", ""),
        }

    except Exception as e:
        logger.error(trace_id, incident.incident_id, event="triage_error", error=str(e))
        return {
            "severity": "MEDIUM",
            "summary": f"Triage failed: {str(e)}",
            "should_investigate": True,
            "reasoning": "Fallback due to API error",
        }
