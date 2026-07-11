import json
from typing import Optional
import redis.asyncio as redis
from src.config import settings
from src.orchestrator.models import Incident


# Single shared client (connection pool) for the whole app. Previously every call did
# from_url()+close(), and that churn intermittently raised "Timeout connecting to server"
# — which could abort an incident mid-flow. A pooled client with a connect timeout and
# retry-on-timeout is both faster and far more reliable.
_shared_redis: Optional[redis.Redis] = None


def _get_client() -> redis.Redis:
    global _shared_redis
    if _shared_redis is None:
        _shared_redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            socket_keepalive=True,
            retry_on_timeout=True,
            health_check_interval=30,
        )
    return _shared_redis


class StateStore:
    PREFIX = "incident:"

    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    async def connect(self):
        # Reuse the shared pooled client instead of opening a new connection each call.
        self._redis = _get_client()

    async def disconnect(self):
        # No-op: the shared client is long-lived and pooled; don't tear it down per request.
        pass

    def _key(self, incident_id: str) -> str:
        return f"{self.PREFIX}{incident_id}"

    async def save(self, incident: Incident):
        key = self._key(incident.incident_id)
        await self._redis.set(key, incident.model_dump_json())

    async def get(self, incident_id: str) -> Optional[Incident]:
        key = self._key(incident_id)
        data = await self._redis.get(key)
        if data:
            return Incident.model_validate_json(data)
        return None

    async def delete(self, incident_id: str):
        key = self._key(incident_id)
        await self._redis.delete(key)

    async def list_active(self) -> list[str]:
        keys = await self._redis.keys(f"{self.PREFIX}*")
        incident_ids = []
        for key in keys:
            data = await self._redis.get(key)
            if data:
                inc = Incident.model_validate_json(data)
                if inc.state.value not in ("RESOLVED", "SUPPRESSED"):
                    incident_ids.append(inc.incident_id)
        return incident_ids
