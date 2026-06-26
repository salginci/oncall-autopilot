import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from src.api.webhook import router as webhook_router
from src.orchestrator.engine import PENDING_APPROVALS, approve_incident, deny_incident, monitor_loop
from src.db.state_store import StateStore
from src.tools.metrics import metrics_tool
from src.tools.deploy import deploy_tool

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


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    html_path = Path(__file__).parent / "dashboard.html"
    return HTMLResponse(html_path.read_text())


@app.get("/api/dashboard/state")
async def dashboard_state():
    try:
        svc_metrics = await metrics_tool.get_error_rate()
        svc_health = await metrics_tool.get_health()
    except Exception:
        svc_metrics = {"error_rate": 0, "total_requests": 0, "latency_p50_ms": 0}
        svc_health = {"status": "unknown"}

    service = {
        "status": svc_health.get("status", "unknown"),
        "pool_size": svc_metrics.get("pool_size", 20),
        "pool_available": svc_metrics.get("pool_available", 20),
        "error_rate": svc_metrics.get("error_rate", 0),
        "total_requests": svc_metrics.get("total_requests", 0),
        "latency_p50_ms": svc_metrics.get("latency_p50_ms", 0),
    }

    pending = list(PENDING_APPROVALS.keys())
    active = None
    incident_detail = None

    if pending:
        incident_id = pending[0]
        store = StateStore()
        await store.connect()
        try:
            inc = await store.get(incident_id)
            if inc:
                active = inc.state.value
                incident_detail = inc.model_dump()
        finally:
            await store.disconnect()
    else:
        store = StateStore()
        await store.connect()
        try:
            active_ids = await store.list_active()
            if active_ids:
                inc = await store.get(active_ids[0])
                if inc:
                    active = inc.state.value
        finally:
            await store.disconnect()

    return {
        "service": service,
        "incident": active,
        "pending_approval": pending[0] if pending else None,
        "incident_detail": incident_detail,
    }


@app.post("/api/dashboard/trigger")
async def dashboard_trigger():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post("http://demo-service:3000/admin/pool/1")
            data = resp.json()
            return {"status": "triggered", "pool_size": data.get("pool_size", 1)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/dashboard/reset")
async def dashboard_reset():
    try:
        await deploy_tool.reload_config()
    except Exception:
        pass
    PENDING_APPROVALS.clear()
    return {"status": "reset"}


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
