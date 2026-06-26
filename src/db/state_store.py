import json
from typing import Optional
import redis.asyncio as redis
from src.config import settings
from src.orchestrator.models import Incident


class StateStore:
    PREFIX = "incident:"

    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    async def connect(self):
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def disconnect(self):
        if self._redis:
            await self._redis.close()

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
