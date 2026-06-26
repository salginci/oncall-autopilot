import uuid
import asyncio
from typing import Optional
from fastapi import APIRouter
from src.orchestrator.models import Alert, Incident
from src.orchestrator.engine import process_incident
from src.observability import logger

router = APIRouter(prefix="/api", tags=["webhook"])


class AlertPayload:
    def __init__(self, service: str, title: str, description: str, error_rate: Optional[float] = None, latency_p50_ms: Optional[float] = None):
        self.service = service
        self.title = title
        self.description = description
        self.error_rate = error_rate
        self.latency_p50_ms = latency_p50_ms


@router.post("/alert")
async def receive_alert(payload: dict):
    trace_id = str(uuid.uuid4())
    logger.info(trace_id, event="alert_received", **payload)

    alert = Alert(
        service=payload.get("service", "unknown"),
        title=payload.get("title", "Unknown alert"),
        description=payload.get("description", ""),
        error_rate=payload.get("error_rate"),
        latency_p50_ms=payload.get("latency_p50_ms"),
    )

    incident = Incident(trace_id=trace_id, alert=alert)
    asyncio.create_task(process_incident(incident))

    return {"incident_id": incident.incident_id, "trace_id": trace_id, "state": incident.state.value}
