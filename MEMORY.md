# MEMORY.md — Project State Tracker

> **Purpose**: This file preserves project context across sessions. Read this first when resuming work.
> **Last Updated**: 2026-06-26

---

## Project Overview

| Field | Value |
|-------|-------|
| **Project Name** | On-Call Autopilot |
| **Hackathon** | Global AI Hackathon Series with Qwen Cloud |
| **URL** | https://qwencloud-hackathon.devpost.com/ |
| **Deadline** | July 9, 2026 @ 2:00 PM PDT |
| **Track** | Track 4: Autopilot Agent |
| **Team** | Solo (Sal) |
| **Background** | Backend / Infra / DevOps |
| **Status** | Architecture & Documentation phase |

## What We're Building

An **event-driven on-call autopilot** that:
1. Detects production incidents (real GitHub-triggered outages)
2. Triages severity using Qwen Cloud
3. Investigates root cause (queries recent commits, metrics, logs)
4. Proposes remediation with **human-in-the-loop approval gates**
5. Executes fixes and verifies recovery
6. Generates postmortems

**Differentiator**: The demo uses a REAL GitHub commit that triggers a REAL outage on a running service, and the agent recovers it LIVE. No mock data.

## Hackathon Infrastructure

| Component | Provider | Purpose |
|-----------|----------|---------|
| Qwen Cloud API | Alibaba Cloud | Agent reasoning (triage, investigate, remediate) |
| ECS | Alibaba Cloud | Runs agent + demo service (Docker Compose) |
| ApsaraDB Redis | Alibaba Cloud | Incident state store & job queue |
| SLS | Alibaba Cloud | Structured logging & tracing |
| GitHub | Public | Code repo + demo trigger (config change commit) |

## Post-Hackathon Plan

After submission, migrate from Alibaba/Qwen to Google Cloud/Gemini for business use. Migration details in `docs/POST_HACKATHON.md` (NOT pushed to public repo — in .gitignore).

## User Preferences & Constraints

- **Documentation-first**: Always document before coding
- **No mock data**: Real triggers, real recovery in demo
- **Public repo**: All code open-source with license
- **Post-hackathon**: Migrate to GCP + Gemini for business use
- **API keys**: User will provide when needed — ask before creating config files that need them
- **No commits unless explicitly asked**
- **Keep this MEMORY.md updated** with decisions, progress, and next steps

## Key Decisions Made

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-26 | Track 4: Autopilot Agent | Best fit for backend/infra background, no UI needed |
| 2026-06-26 | Real GitHub-triggered demo | Stands out from mock-data submissions |
| 2026-06-26 | Python/FastAPI + Docker Compose | Natural fit, deployable on ECS |
| 2026-06-26 | Redis for state store | Production-grade persistence vs in-memory |
| 2026-06-26 | Human-in-the-loop via CLI | Clear demo interaction, no Slack/API dependency |
| 2026-06-26 | Post-hackathon: GCP + Gemini | Business plan, kept in separate doc |

## Current Phase

- [x] Architecture & Design documentation
- [x] Project scaffolding (directory structure, base files)
- [x] License (MIT)
- [x] GitHub repo created: https://github.com/salginci/oncall-autopilot
- [x] Core source modules: config, models, state machine, state store, observability
- [x] Agent tools: github.py, metrics.py, health.py, deploy.py, watcher.py
- [x] Qwen agents: triage.py, investigate.py, remediate.py
- [x] Orchestrator engine: full incident lifecycle + monitor loop
- [x] Demo service: FastAPI with configurable pool + load generator
- [x] Human-in-the-loop CLI: typer CLI with status/approve/deny/watch commands
- [x] Docker Compose: agent + demo-service + redis + loadgen + cli
- [ ] Docker test run (verify locally)
- [x] Architecture diagram (architecture.png) — two-view: topology + incident lifecycle
- [ ] Alibaba Cloud deployment (ECS + Redis + SLS)
- [ ] Demo video recording
- [ ] Hackathon submission
- [ ] Project scaffolding
- [ ] Demo service (the "production" app we break)
- [ ] Agent state machine
- [ ] Qwen Cloud integration
- [ ] GitHub integration (commit detection, diff analysis, revert push)
- [ ] Redis state store
- [ ] SLS logging
- [ ] Human-in-the-loop CLI
- [ ] Docker Compose setup
- [ ] Architecture diagram
- [ ] Demo video recording
- [ ] Alibaba Cloud deployment
- [ ] Submission

## Files Structure (planned)

```
qwen_hackathon/
├── MEMORY.md                     # This file
├── docs/
│   ├── DESIGN.md                 # Hackathon architecture & implementation
│   └── POST_HACKATHON.md         # GCP/Gemini migration plan (NOT PUBLIC)
├── src/
│   ├── api/webhook.py
│   ├── orchestrator/
│   │   ├── state_machine.py
│   │   └── models.py
│   ├── agents/
│   │   ├── triage.py
│   │   ├── investigate.py
│   │   └── remediate.py
│   ├── tools/
│   │   ├── github.py
│   │   ├── metrics.py
│   │   ├── health.py
│   │   └── deploy.py
│   ├── db/state_store.py
│   ├── observability.py
│   └── config.py
├── demo/
│   ├── service/
│   │   ├── main.py
│   │   ├── config.yaml
│   │   └── loadgen.py
│   └── agent/
│       └── cli.py
├── docker-compose.yml
├── Dockerfile
├── architecture.png
├── alibaba_cloud_proof.md
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

## Required API Keys / Credentials

| Key | Provided? | Notes |
|-----|-----------|-------|
| Qwen Cloud API Key | ❌ Not yet | Sign up at qwencloud.com + request hackathon credits |
| Alibaba Cloud credentials | ❌ Not yet | ECS + Redis + SLS |
| GitHub Personal Access Token | ❌ Not yet | For commit detection, diff, and revert push (classic token with repo scope) |

## Next Actions

1. Complete DESIGN.md (architecture doc)
2. Complete POST_HACKATHON.md (migration doc — local only)
3. Create .gitignore
4. Scaffold project directory structure
5. Create LICENSE (MIT or Apache 2.0 — decision needed)
6. Ask user for API keys before writing config files
