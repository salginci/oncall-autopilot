from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class IncidentState(str, Enum):
    IDLE = "IDLE"
    RECEIVED = "RECEIVED"
    TRIAGING = "TRIAGING"
    SUPPRESSED = "SUPPRESSED"
    INVESTIGATING = "INVESTIGATING"
    REMEDIATING = "REMEDIATING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXECUTING = "EXECUTING"
    RESOLVED = "RESOLVED"
    TIMED_OUT = "TIMED_OUT"
    OVERRIDE = "OVERRIDE"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: f"alert_{datetime.utcnow().timestamp()}")
    service: str
    title: str
    description: str
    error_rate: Optional[float] = None
    latency_p50_ms: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CommitInfo(BaseModel):
    sha: str
    message: str
    author: str
    timestamp: datetime
    files_changed: list[str]
    diff: str = ""


class RootCause(BaseModel):
    summary: str
    commit_sha: Optional[str] = None
    confidence: float
    evidence: list[str]
    suggested_fix: str


class RemediationPlan(BaseModel):
    action: str
    commands: list[str]
    rollback_plan: str
    risk: str  # LOW, MEDIUM, HIGH
    requires_approval: bool = True


class ApprovalAction(str, Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"
    OVERRIDE = "OVERRIDE"


class Incident(BaseModel):
    incident_id: str = Field(default_factory=lambda: f"inc_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
    trace_id: str
    state: IncidentState = IncidentState.IDLE
    alert: Optional[Alert] = None
    severity: Optional[Severity] = None
    triage_summary: Optional[str] = None
    commits: list[CommitInfo] = []
    root_cause: Optional[RootCause] = None
    remediation: Optional[RemediationPlan] = None
    approval_action: Optional[ApprovalAction] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    state_history: list[dict] = []

    def add_state(self, state: IncidentState, detail: str = ""):
        self.state = state
        self.state_history.append({
            "state": state.value,
            "timestamp": datetime.utcnow().isoformat(),
            "detail": detail,
        })
