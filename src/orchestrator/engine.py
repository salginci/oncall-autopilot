import asyncio
import json
import uuid
import httpx
from datetime import datetime, timezone
from typing import Optional
from src.config import settings
from src.orchestrator.models import Incident, IncidentState, Alert, Severity, RootCause, RemediationPlan, CommitInfo
from src.orchestrator.state_machine import IncidentStateMachine
from src.agents.triage import run_triage
from src.agents.investigate import run_investigation
from src.agents.remediate import run_remediation
from src.tools.metrics import metrics_tool
from src.tools.github import github_tool
from src.tools.deploy import deploy_tool
from src.tools.watcher import commit_watcher
from src.db.state_store import StateStore
from src.observability import logger

PENDING_APPROVALS: dict[str, Incident] = {}

# Set to True from the moment an incident is created until it is resolved/denied/suppressed.
# Guards monitor_loop against creating a duplicate incident (and firing duplicate Qwen calls)
# on every 5s poll while the error rate stays high.
_incident_in_flight: bool = False

# SHA of the "breaking" commit pushed by the dashboard trigger — used as a fallback target
# for the real revert on approval if investigation didn't pin down a commit.
_last_trigger_sha: Optional[str] = None


def set_trigger_commit(sha: Optional[str]) -> None:
    global _last_trigger_sha
    _last_trigger_sha = sha


async def process_incident(incident: Incident):
    global _incident_in_flight
    store = StateStore()
    await store.connect()
    fsm = IncidentStateMachine(incident)

    try:
        logger.info(incident.trace_id, incident.incident_id, event="incident_processing_started")

        fsm.transition_to(IncidentState.RECEIVED, "Alert received")
        await store.save(incident)

        fsm.transition_to(IncidentState.TRIAGING, "Starting triage assessment")
        await store.save(incident)

        triage_result = await run_triage(incident)
        incident.severity = Severity(triage_result["severity"])
        incident.triage_summary = triage_result["summary"]
        await store.save(incident)

        if not triage_result.get("should_investigate", True):
            fsm.transition_to(IncidentState.SUPPRESSED, "Low severity — suppressed")
            await store.save(incident)
            _incident_in_flight = False
            logger.info(incident.trace_id, incident.incident_id, event="incident_suppressed")
            return incident

        fsm.transition_to(IncidentState.INVESTIGATING, "Escalated to investigation")
        await store.save(incident)

        investigation_result = await run_investigation(incident)
        incident.root_cause = RootCause(
            summary=investigation_result.get("root_cause", ""),
            commit_sha=investigation_result.get("commit_sha"),
            confidence=investigation_result.get("confidence", 0.0),
            evidence=investigation_result.get("evidence", []),
            suggested_fix=investigation_result.get("suggested_fix", ""),
        )
        await store.save(incident)

        fsm.transition_to(IncidentState.REMEDIATING, "Generating remediation plan")
        await store.save(incident)

        remediation_result = await run_remediation(incident)
        incident.remediation = RemediationPlan(
            action=remediation_result["action"],
            commands=remediation_result["commands"],
            rollback_plan=remediation_result["rollback_plan"],
            risk=remediation_result["risk"],
            requires_approval=remediation_result["requires_approval"],
        )
        await store.save(incident)

        fsm.transition_to(IncidentState.WAITING_APPROVAL, "Awaiting human approval")
        await store.save(incident)

        PENDING_APPROVALS[incident.incident_id] = incident
        logger.info(incident.trace_id, incident.incident_id, event="awaiting_approval",
                    action=incident.remediation.action)

        return incident

    except Exception as e:
        _incident_in_flight = False
        logger.error(incident.trace_id, incident.incident_id, event="processing_error", error=str(e))
        return incident
    finally:
        await store.disconnect()


async def approve_incident(incident_id: str) -> dict:
    global _incident_in_flight
    incident = PENDING_APPROVALS.pop(incident_id, None)
    if not incident:
        return {"success": False, "error": f"No pending incident {incident_id}"}

    fsm = IncidentStateMachine(incident)
    fsm.transition_to(IncidentState.APPROVED, "Human approved")
    result = {"success": True, "details": []}

    store = StateStore()
    try:
        await store.connect()
        fsm.transition_to(IncidentState.EXECUTING, "Executing remediation")
        await store.save(incident)
    except Exception:
        pass

    # 1. Execute the real fix: revert the breaking commit on GitHub. Prefer the commit the
    # investigation pinned, fall back to the trigger's recorded SHA, then the latest main commit.
    revert_sha = (incident.root_cause.commit_sha if incident.root_cause else None) or _last_trigger_sha
    if not revert_sha:
        try:
            commits = await github_tool.get_recent_commits(since_minutes=60, limit=1)
            revert_sha = commits[0].sha if commits else None
        except Exception:
            revert_sha = None

    if revert_sha:
        reason = f"Auto-remediation for incident {incident.incident_id}: restore connection pool"
        revert_result = await github_tool.push_revert(revert_sha, reason)
        result["details"].append({"github_revert": revert_result})
        logger.info(incident.trace_id, incident.incident_id, event="github_revert",
                    target=revert_sha[:7], success=revert_result.get("success"))
    else:
        result["details"].append({"github_revert": {"success": False, "error": "no commit to revert"}})

    # 2. Restore the running service immediately so recovery is instant on camera (the watcher
    # will also converge to the reverted config on its next poll).
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{settings.DEMO_SERVICE_URL}/admin/pool/20")
            result["details"].append({"pool_restored": r.status_code == 200})
    except Exception as e:
        result["details"].append({"pool_restore_error": str(e)})

    try:
        fsm.transition_to(IncidentState.RESOLVED, "Fix applied successfully")
        incident.resolved_at = datetime.now(timezone.utc)
        await store.save(incident)
    except Exception:
        pass

    try:
        await store.disconnect()
    except Exception:
        pass

    _incident_in_flight = False
    logger.info(incident.trace_id, incident.incident_id, event="incident_resolved")
    return result


async def deny_incident(incident_id: str, override_action: str = "") -> dict:
    global _incident_in_flight
    incident = PENDING_APPROVALS.pop(incident_id, None)
    if not incident:
        return {"success": False, "error": f"No pending incident {incident_id}"}

    _incident_in_flight = False
    fsm = IncidentStateMachine(incident)

    if override_action:
        fsm.transition_to(IncidentState.OVERRIDE, f"Manual override: {override_action}")
        fsm.transition_to(IncidentState.RESOLVED, "Override applied")
    else:
        fsm.transition_to(IncidentState.DENIED, "Human denied — no action taken")

    store = StateStore()
    await store.connect()
    try:
        incident.resolved_at = datetime.now(timezone.utc)
        await store.save(incident)
        logger.info(incident.trace_id, incident.incident_id, event="incident_denied", override=override_action)
    finally:
        await store.disconnect()

    return {"success": True, "action": "denied", "override": override_action or None}


async def monitor_loop(interval: Optional[int] = None):
    global _incident_in_flight
    poll_interval = interval if interval is not None else settings.AGENT_POLL_INTERVAL

    logger.info("monitor", event="monitor_loop_started", interval=poll_interval)

    try:
        await commit_watcher.init()
    except Exception as e:
        logger.error("monitor", event="commit_watcher_init_error", error=str(e))

    while True:
        try:
            await commit_watcher.check_and_reload()

            metrics = await metrics_tool.get_error_rate()
            error_rate = metrics.get("error_rate", 0)
            latency = metrics.get("latency_p50_ms", 0)

            trace_id = str(uuid.uuid4())
            logger.info(trace_id, event="monitor_poll",
                        error_rate=error_rate, latency_p50_ms=latency)

            threshold_breached = (
                error_rate > settings.ERROR_RATE_THRESHOLD
                or latency > settings.LATENCY_THRESHOLD_MS
            )
            # Dedup: only one incident in flight at a time. Without this the loop would spawn a
            # brand-new incident (and 3+ Qwen calls) on every poll while the outage persists.
            if threshold_breached and not _incident_in_flight and not PENDING_APPROVALS:
                _incident_in_flight = True
                alert = Alert(
                    service="demo-service",
                    title="Service Degradation Detected",
                    description=f"Error rate {error_rate:.1%} exceeds threshold {settings.ERROR_RATE_THRESHOLD:.1%} | P50 latency {latency}ms",
                    error_rate=error_rate,
                    latency_p50_ms=latency,
                )
                incident = Incident(trace_id=trace_id, alert=alert)
                logger.info(trace_id, incident.incident_id, event="incident_created", error_rate=error_rate)
                asyncio.create_task(process_incident(incident))

        except Exception as e:
            trace_id = str(uuid.uuid4())
            logger.error(trace_id, event="monitor_error", error=str(e))

        await asyncio.sleep(poll_interval)
