import httpx
from src.config import settings


class MetricsTool:
    def __init__(self):
        self.base_url = settings.DEMO_SERVICE_URL

    async def get_metrics(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/metrics")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def get_error_rate(self) -> dict:
        metrics = await self.get_metrics()
        if "error" in metrics:
            return metrics
        total = metrics.get("total_requests", 0)
        errors = metrics.get("error_count", 0)
        rate = errors / total if total > 0 else 0
        return {
            "total_requests": total,
            "error_count": errors,
            "error_rate": round(rate, 4),
            "latency_p50_ms": metrics.get("latency_p50_ms", 0),
        }

    async def get_health(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/health")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def trigger_reload(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.post(f"{self.base_url}/admin/reload")
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                return {"error": str(e)}


metrics_tool = MetricsTool()
