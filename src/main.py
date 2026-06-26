import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.api.webhook import router as webhook_router
from src.orchestrator.engine import PENDING_APPROVALS, approve_incident, deny_incident, monitor_loop
from src.db.state_store import StateStore

monitor_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global monitor_task
    store = StateStore()
    await store.connect()
    monitor_task = asyncio.create_task(monitor_loop())
    yield
    if monitor_task:
        monitor_task.cancel()
    await store.disconnect()


app = FastAPI(
    title="On-Call Autopilot",
    description="AI-powered incident response agent — Track 4: Autopilot Agent — Global AI Hackathon with Qwen Cloud",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "oncall-autopilot"}


@app.get("/api/incidents")
async def list_incidents():
    store = StateStore()
    await store.connect()
    try:
        active = await store.list_active()
        return {"active_incidents": active, "pending_approvals": list(PENDING_APPROVALS.keys())}
    finally:
        await store.disconnect()


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    store = StateStore()
    await store.connect()
    try:
        incident = await store.get(incident_id)
        if incident:
            return incident.model_dump()
        return {"error": "not found"}
    finally:
        await store.disconnect()


@app.post("/api/incidents/{incident_id}/approve")
async def api_approve(incident_id: str):
    return await approve_incident(incident_id)


@app.post("/api/incidents/{incident_id}/deny")
async def api_deny(incident_id: str, override: str = ""):
    return await deny_incident(incident_id, override)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)
