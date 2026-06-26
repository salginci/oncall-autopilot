from enum import Enum
from typing import Callable, Optional
from src.orchestrator.models import Incident, IncidentState


class TransitionStatus(Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


TRANSITIONS: dict[IncidentState, list[IncidentState]] = {
    IncidentState.IDLE: [IncidentState.RECEIVED],
    IncidentState.RECEIVED: [IncidentState.TRIAGING, IncidentState.TIMED_OUT],
    IncidentState.TRIAGING: [IncidentState.SUPPRESSED, IncidentState.INVESTIGATING],
    IncidentState.SUPPRESSED: [],
    IncidentState.INVESTIGATING: [IncidentState.REMEDIATING, IncidentState.TIMED_OUT],
    IncidentState.REMEDIATING: [IncidentState.WAITING_APPROVAL],
    IncidentState.WAITING_APPROVAL: [IncidentState.APPROVED, IncidentState.DENIED, IncidentState.TIMED_OUT],
    IncidentState.APPROVED: [IncidentState.EXECUTING],
    IncidentState.DENIED: [IncidentState.OVERRIDE],
    IncidentState.EXECUTING: [IncidentState.RESOLVED],
    IncidentState.OVERRIDE: [IncidentState.RESOLVED],
    IncidentState.RESOLVED: [],
    IncidentState.TIMED_OUT: [IncidentState.TRIAGING],
}


class IncidentStateMachine:
    def __init__(self, incident: Incident):
        self.incident = incident
        self._handlers: dict[IncidentState, Optional[Callable]] = {}

    def can_transition_to(self, target: IncidentState) -> bool:
        return target in TRANSITIONS.get(self.incident.state, [])

    def transition_to(self, target: IncidentState, detail: str = "") -> TransitionStatus:
        if not self.can_transition_to(target):
            return TransitionStatus.BLOCKED
        self.incident.add_state(target, detail)
        return TransitionStatus.ALLOWED

    def on_enter(self, state: IncidentState, handler: Callable):
        self._handlers[state] = handler

    async def handle(self, state: IncidentState, *args, **kwargs):
        handler = self._handlers.get(state)
        if handler:
            await handler(self.incident, *args, **kwargs)

    @property
    def current_state(self) -> IncidentState:
        return self.incident.state

    @property
    def is_terminal(self) -> bool:
        return self.incident.state in {IncidentState.RESOLVED, IncidentState.SUPPRESSED}
