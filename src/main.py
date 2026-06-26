import uvicorn
from fastapi import FastAPI
from src.api.webhook import router as webhook_router
from src.db.state_store import StateStore

app = FastAPI(
    title="On-Call Autopilot",
    description="AI-powered incident response agent — Global AI Hackathon with Qwen Cloud",
    version="0.1.0",
)

app.include_router(webhook_router)


@app.on_event("startup")
async def startup():
    store = StateStore()
    await store.connect()


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)
