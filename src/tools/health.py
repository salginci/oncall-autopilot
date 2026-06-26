import httpx
from src.config import settings


class HealthTool:
    def __init__(self):
        self.base_url = settings.DEMO_SERVICE_URL

    async def check(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/health")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"status": "unhealthy", "error": str(e)}

    async def check_dependency(self, dependency: str) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/health/{dependency}")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"status": "unknown", "dependency": dependency, "error": str(e)}


health_tool = HealthTool()
