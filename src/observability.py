import json
import logging
from datetime import datetime, timezone
from typing import Optional


class TraceLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

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

    def info(self, trace_id: str, incident_id: Optional[str] = None, **kwargs):
        self._emit("info", trace_id, incident_id, **kwargs)

    def warn(self, trace_id: str, incident_id: Optional[str] = None, **kwargs):
        self._emit("warning", trace_id, incident_id, **kwargs)

    def error(self, trace_id: str, incident_id: Optional[str] = None, **kwargs):
        self._emit("error", trace_id, incident_id, **kwargs)


# Global instance
logger = TraceLogger("oncall-autopilot")
