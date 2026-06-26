# DESIGN.md — On-Call Autopilot Architecture & Implementation Plan

> **Track**: 4 — Autopilot Agent
> **Hackathon**: Global AI Hackathon Series with Qwen Cloud (Devpost)
> **Deadline**: July 9, 2026

---

## 1. System Architecture

```
                           ┌─────────────────────────┐
                           │     Qwen Cloud API       │
                           │  (reasoning / decisions) │
                           └──────────▲──────────────┘
                                      │
┌─────────────┐    ┌──────────────────┴───────────────────┐    ┌──────────────┐
│  GitHub     │    │       Alibaba Cloud ECS               │    │  Human       │
│  (public)   │    │                                       │    │  Approval    │
│             │    │  ┌────────────┐   ┌────────────────┐  │    │  CLI         │
│ config.yaml ◄────┼──┤  Agent     │   │  Demo Service  │  │    │              │
│ bad commit  │    │  │  (FastAPI) │   │  (FastAPI)     │  │    │  approve/    │
│ revert PR   │    │  │            │   │                │  │    │  deny/       │
│             │    │  │ monitors ──┼──▶│  /health       │  │    │  override    │
│             │    │  │ polls      │   │  /metrics      │  │    │              │
│             │    │  │            │   │  /api/*        │  │    └──────────────┘
│             │    │  │ GitHub API │   │  /admin/reload │◄─┼── POST reload
│             │    │  │ git push ▲ │   │                │  │
│             │    │  └─────┬──────┘   └────────────────┘  │
│             │    │        │                               │
│             │    │  ┌─────┴──────┐   ┌────────────────┐  │
│             │    │  │   Redis    │   │  SLS Logging   │  │
│             │    │  │  (state)   │   │  (traces)      │  │
│             │    │  └────────────┘   └────────────────┘  │
└─────────────┘    └───────────────────────────────────────┘
```

### Component Summary

| Component | Technology | Role |
|-----------|-----------|------|
| **Agent (Orchestrator)** | Python/FastAPI | Main server: state machine, webhook ingestion, Qwen calls, tool dispatch |
| **Demo Service** | Python/FastAPI | Simulated microservice with configurable DB pool — the "production" target we break and fix |
| **State Store** | Redis (ApsaraDB) | Persistent FSM state, incident history, alert buffer |
| **Logging** | SLS (Simple Log Service) | Structured JSON logs with trace context across components |
| **AI Reasoning** | Qwen Cloud API | Triage severity, investigate root cause, generate remediation |
| **Tools** | Python (MCP-style) | GitHub API, health checks, metric queries, config reload |
| **Human Interface** | CLI (Click/Typer) | Approval gates: approve, deny, override |

---

## 2. Data Flow: Incident Lifecycle

### State Machine

```
                    ┌──────────┐
                    │  IDLE    │
                    └────┬─────┘
                         │ alert received (webhook or poll)
                    ┌────▼─────┐
                    │ RECEIVED │──── timeout ────▶ TIMED_OUT
                    └────┬─────┘
                         │ start triage
                    ┌────▼─────┐
                    │ TRIAGING │── low severity ──▶ SUPPRESSED
                    └────┬─────┘
                         │ severity ≥ MEDIUM
                    ┌────▼─────────┐
                    │ INVESTIGATING │
                    └────┬──────────┘
                         │ root cause found
                    ┌────▼──────────┐
                    │  REMEDIATING  │
                    └────┬──────────┘
                         │ fix proposed
                    ┌────▼──────────────┐
                    │ WAITING_APPROVAL  │
                    └────┬──────────────┘
                         │            └── timeout → auto-escalate
                    ┌────▼───────┐ ┌────▼────────┐
                    │  APPROVED  │ │   DENIED     │
                    └────┬───────┘ └────┬────────┘
                         │              │
                    ┌────▼──────┐  ┌────▼─────────┐
                    │ EXECUTING │  │ OVERRIDE     │
                    └────┬──────┘  │ (manual fix) │
                         │         └────┬─────────┘
                    ┌────▼──────┐       │
                    │ RESOLVED  │◄──────┘
                    └───────────┘
```

### Transition Table

| From → To | Trigger | Action |
|-----------|---------|--------|
| IDLE → RECEIVED | Alert webhook / poll threshold breach | Create incident record, assign trace ID |
| RECEIVED → TRIAGING | Auto (immediate) | Qwen: assess severity, context, blast radius |
| RECEIVED → TIMED_OUT | No action within 30s | Mark stale, log |
| TRIAGING → SUPPRESSED | Qwen: severity = LOW | Log, close silently |
| TRIAGING → INVESTIGATING | Qwen: severity ≥ MEDIUM | Begin root cause analysis |
| INVESTIGATING → REMEDIATING | Root cause identified | Qwen: generate fix proposal |
| REMEDIATING → WAITING_APPROVAL | Fix proposal ready | Display diff + action plan to human |
| WAITING_APPROVAL → APPROVED | Human: approve | Execute fix |
| WAITING_APPROVAL → DENIED | Human: deny | Allow manual override path |
| WAITING_APPROVAL → TIMED_OUT | No response in 120s | Auto-escalate (log, exit to manual) |
| APPROVED → EXECUTING | Auto | Run fix: git revert + push + reload |
| EXECUTING → RESOLVED | Health check passing | Close incident, generate postmortem |
| DENIED → OVERRIDE | Human provides manual fix | Execute manual fix, verify, close |

---

## 3. Demo Scenario: Connection Pool Exhaustion

### Setup

1. Demo Service running with `config.yaml: pool_size = 20`
2. Load generator hitting service at ~100 req/s
3. Agent monitoring service health + recent commits

### Trigger (Live in Video)

```bash
# In demo/service/config.yaml
# Change: pool_size: 20 → pool_size: 2

git add config.yaml
git commit -m "reduce pool size"
git push origin main
```

### Step-by-Step Flow

| Time | State | System Action | Visible In Demo |
|------|-------|---------------|-----------------|
| T+0s | — | Config push to GitHub | Terminal: `git push` output |
| T+2s | — | Agent detects push → POST /admin/reload | Service log: `[RELOAD]` |
| T+4s | — | Service reloads with pool_size=2 | Service log: `pool: 2 slots` |
| T+6s | — | Error rate spikes to ~80% | Loadgen: `503 503 503 200 503` |
| T+10s | RECEIVED | Agent poll: error rate > threshold | Agent log: `[ALERT] INCIDENT #847` |
| T+12s | TRIAGING | Qwen: "CRITICAL — orders-service error rate 80%. Revenue impact." | Agent log: Qwen response |
| T+15s | INVESTIGATING | Tool call: `get_recent_commits(orders-service)` | Agent log: `[TOOL] github.get_commits()` |
| T+18s | INVESTIGATING | Tool call: `get_diff(commit_sha)` | Agent log: diff output |
| T+22s | REMEDIATING | Qwen: "Root cause: pool_size reduced from 20 to 2. Fix: revert to 20." | Agent log: Qwen with diff |
| T+25s | WAITING_APPROVAL | Agent displays proposed fix | CLI menu: `[APPROVE] [DENY] [OVERRIDE]` |
| T+30s | APPROVED | Human types `approve` | CLI: `> approve` |
| T+32s | EXECUTING | Agent runs `git revert`, pushes, calls `/admin/reload` | Agent log: git output |
| T+35s | RESOLVED | Service recovers. Health check green. | Service log: `pool: 20 slots`. Loadgen: `200 200 200` |
| T+37s | RESOLVED | Postmortem generated | Agent log: `[POSTMORTEM] Incident #847 closed` |

---

## 4. Tool Definitions (MCP-Style Interface)

```python
TOOLS = {
    "get_recent_commits": {
        "service": str,          # Which service to check
        "since": Optional[str],  # ISO timestamp or "5m"
        "limit": int = 10,
    },
    "get_commit_diff": {
        "commit_sha": str,
    },
    "revert_commit": {
        "commit_sha": str,
        "reason": str,
    },
    "get_health": {
        "service": str,
    },
    "get_metrics": {
        "service": str,
        "window": str = "5m",    # e.g., "5m", "1h"
    },
    "trigger_reload": {
        "service": str,
    },
    "get_incident_status": {
        "incident_id": str,
    },
}
```

---

## 5. Qwen Cloud Integration

### Model Selection
- Use Qwen function-calling models (`qwen-plus` or `qwen-max`) for triage and investigation
- Provide function definitions matching the tool interface above
- Use structured JSON output for reliability

### Prompt Architecture

**Triage Agent**:
```
System: You are an on-call SRE triage agent. Given an alert, assess severity (LOW/MEDIUM/HIGH/CRITICAL),
estimate blast radius, and decide whether to escalate to investigation.
Output: JSON with {severity, summary, should_investigate, reasoning}
```

**Investigation Agent**:
```
System: You are a root-cause analysis agent. You have access to tools:
- get_recent_commits(service)
- get_commit_diff(sha)
- get_metrics(service)
- get_health(service)

Given an incident context, call tools to gather evidence, then identify the root cause.
Output: JSON with {root_cause, confidence, evidence_chain, suggested_fix}
```

**Remediation Agent**:
```
System: You are a remediation agent. Given a root cause analysis, generate a concrete fix plan.
Output: JSON with {action, commands, rollback_plan, risk_assessment, requires_approval}
```

---

## 6. Observability

### Structured Logging (SLS)

Every event logs as JSON with shared fields:

```python
{
    "trace_id": "inc_847_20260626_abc123",
    "incident_id": "847",
    "state": "INVESTIGATING",
    "component": "agent.investigate",
    "action": "tool_call",
    "tool": "get_commit_diff",
    "duration_ms": 234,
    "status": "success",
    "timestamp": "2026-06-26T14:30:22Z"
}
```

---

## 7. Deployment on Alibaba Cloud

### Docker Compose (on ECS)

```yaml
services:
  agent:
    build: .
    ports: ["8080:8080"]
    environment:
      - REDIS_URL=redis://alibaba-redis-instance:6379
      - QWEN_API_KEY=${QWEN_API_KEY}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - SLS_ENDPOINT=${SLS_ENDPOINT}

  demo-service:
    build: ./demo/service
    ports: ["3000:3000"]
    volumes:
      - ./demo/service/config.yaml:/app/config.yaml

  loadgen:
    build: ./demo/service
    command: python loadgen.py
```

### Proof of Alibaba Cloud (for submission)

- Screenshot of ECS instance dashboard showing running instance
- Screenshot of Redis instance in ApsaraDB console
- Code file `alibaba_cloud_proof.md` documenting deployment steps with instance IDs
- Video segment showing Alibaba Cloud console

---

## 8. Submission Checklist

- [ ] Public GitHub repo with open-source license (MIT or Apache 2.0)
- [ ] Architecture diagram (`architecture.png`)
- [ ] ~3 min demo video (YouTube/Vimeo/Facebook, public)
- [ ] Text description of features
- [ ] Track identified (Track 4: Autopilot Agent)
- [ ] Proof of Alibaba Cloud deployment (`alibaba_cloud_proof.md`)
- [ ] Optional: Blog post for Blog Post Award ($500)
