import httpx
from src.config import settings


class DeployTool:
    def __init__(self):
        self.base_url = settings.DEMO_SERVICE_URL

    async def reload_config(self) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(f"{self.base_url}/admin/reload")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def get_config(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/admin/config")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"error": str(e)}


deploy_tool = DeployTool()
