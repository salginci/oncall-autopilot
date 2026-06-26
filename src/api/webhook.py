import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.orchestrator.models import Alert, Incident, IncidentState
from src.orchestrator.state_machine import IncidentStateMachine
from src.db.state_store import StateStore
from src.observability import logger

router = APIRouter(prefix="/api", tags=["webhook"])


class AlertPayload(BaseModel):
    service: str
    title: str
    description: str
    error_rate: float | None = None
    latency_p50_ms: float | None = None


async def process_incident(incident: Incident, store: StateStore):
    trace_id = incident.trace_id
    fsm = IncidentStateMachine(incident)

    if fsm.transition_to(IncidentState.RECEIVED, "Alert received via webhook") == "BLOCKED":
        logger.error(trace_id, incident.incident_id, msg="Invalid state transition from IDLE")
        return

    await store.save(incident)
    logger.info(trace_id, incident.incident_id, event="incident_created", alert=incident.alert.model_dump())

    if fsm.transition_to(IncidentState.TRIAGING, "Starting triage") == "BLOCKED":
        logger.error(trace_id, incident.incident_id, msg="Cannot transition to TRIAGING")
        return

    await store.save(incident)
    logger.info(trace_id, incident.incident_id, event="triage_started")


@router.post("/alert")
async def receive_alert(payload: AlertPayload):
    trace_id = str(uuid.uuid4())
    logger.info(trace_id, event="alert_received", **payload.model_dump())

    alert = Alert(
        service=payload.service,
        title=payload.title,
        description=payload.description,
        error_rate=payload.error_rate,
        latency_p50_ms=payload.latency_p50_ms,
    )

    incident = Incident(trace_id=trace_id, alert=alert)

    store = StateStore()
    await store.connect()
    try:
        await process_incident(incident, store)
    finally:
        await store.disconnect()

    return {"incident_id": incident.incident_id, "trace_id": trace_id, "state": incident.state.value}
