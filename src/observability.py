import json
import sys
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional


class TraceLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

        self._buffer: deque = deque(maxlen=200)

    def _emit(self, level: str, trace_id: str, incident_id: Optional[str], **kwargs):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "incident_id": incident_id,
            "level": level,
            **kwargs,
        }
        msg = json.dumps(entry)
        if level == "error":
            self.logger.error(msg)
        elif level == "warning":
            self.logger.warning(msg)
        else:
            self.logger.info(msg)
        sys.stdout.flush()
        self._buffer.append(entry)

    def info(self, trace_id: str, incident_id: Optional[str] = None, **kwargs):
        self._emit("info", trace_id, incident_id, **kwargs)

    def warn(self, trace_id: str, incident_id: Optional[str] = None, **kwargs):
        self._emit("warning", trace_id, incident_id, **kwargs)

    def error(self, trace_id: str, incident_id: Optional[str] = None, **kwargs):
        self._emit("error", trace_id, incident_id, **kwargs)

    def recent(self, limit: int = 50) -> list[dict]:
        return list(self._buffer)[-limit:]


# Global instance
logger = TraceLogger("oncall-autopilot")
