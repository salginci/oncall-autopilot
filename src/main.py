import asyncio
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from src.api.webhook import router as webhook_router
from src.orchestrator.engine import PENDING_APPROVALS, approve_incident, deny_incident, monitor_loop
from src.db.state_store import StateStore
from src.tools.metrics import metrics_tool
from src.tools.deploy import deploy_tool
from src.config import settings
from src.observability import logger

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


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")


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
            for aid in active_ids:
                inc = await store.get(aid)
                if inc and inc.state.value not in ('WAITING_APPROVAL', 'SUPPRESSED', 'RESOLVED', 'REMEDIATING', 'INVESTIGATING', 'TRIAGING'):
                    active = inc.state.value
                    break
        finally:
            await store.disconnect()

    return {
        "service": service,
        "incident": active if pending else None,
        "pending_approval": pending[0] if pending else None,
        "incident_detail": incident_detail if pending else None,
    }


@app.post("/api/dashboard/trigger")
async def dashboard_trigger():
    import httpx
    import base64
    import yaml
    from src.tools.github import github_tool

    result = {"status": "triggered"}

    # 1. Push a real commit to GitHub changing pool_size 20→0
    try:
        repo = github_tool.repo
        file_path = "demo/service/config.yaml"
        contents = repo.get_contents(file_path, ref="main")
        config = yaml.safe_load(base64.b64decode(contents.content))
        config["database"]["pool_size"] = 0
        new_content = yaml.dump(config, default_flow_style=False)
        commit_msg = f"BREAKING: reduce connection pool to 0 (simulated outage {datetime.now(timezone.utc).strftime('%H:%M:%S')})"
        update = repo.update_file(
            path=file_path,
            message=commit_msg,
            content=new_content,
            sha=contents.sha,
            branch="main",
        )
        commit_sha = update["commit"].sha
        result["commit_sha"] = commit_sha
        result["commit_url"] = f"https://github.com/salginci/oncall-autopilot/commit/{commit_sha}"
        result["commit_message"] = commit_msg
    except Exception as e:
        result["commit_error"] = str(e)

    # 2. Restore pool to 20 immediately (so the demo keeps working after the demo)
    try:
        repo = github_tool.repo
        contents = repo.get_contents(file_path, ref="main")
        config = yaml.safe_load(base64.b64decode(contents.content))
        config["database"]["pool_size"] = 20
        new_content = yaml.dump(config, default_flow_style=False)
        repo.update_file(
            path=file_path,
            message="fix: restore connection pool to 20",
            content=new_content,
            sha=contents.sha,
            branch="main",
        )
    except Exception:
        pass

    # 3. Trigger the outage on the demo service
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{settings.DEMO_SERVICE_URL}/admin/pool/0")
            data = resp.json()
            result["pool_size"] = data.get("pool_size", 0)
    except Exception as e:
        result["pool_error"] = str(e)

    return result


@app.post("/api/dashboard/reset")
async def dashboard_reset():
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{settings.DEMO_SERVICE_URL}/admin/pool/20")
    except Exception:
        pass
    PENDING_APPROVALS.clear()
    store = StateStore()
    await store.connect()
    try:
        active_ids = await store.list_active()
        for aid in active_ids:
            await store.delete(aid)
    finally:
        await store.disconnect()
    return {"status": "reset"}


@app.get("/api/dashboard/logs")
async def dashboard_logs(limit: int = Query(default=50, le=200)):
    return {"logs": logger.recent(limit)}


@app.get("/api/dashboard/latest-commit")
async def latest_commit():
    from src.tools.github import github_tool
    commits = await github_tool.get_recent_commits(since_minutes=60, limit=5)
    if commits:
        c = commits[0]
        return {
            "sha": c.sha,
            "short_sha": c.sha[:7],
            "message": c.message,
            "author": c.author,
            "files_changed": c.files_changed,
            "url": f"https://github.com/salginci/oncall-autopilot/commit/{c.sha}",
        }
    return {"sha": None, "message": "No recent commits"}


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
