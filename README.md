# On-Call Autopilot

> Track 4: Autopilot Agent — Global AI Hackathon Series with Qwen Cloud

An AI-powered incident response agent that detects production outages, investigates root cause using Qwen Cloud, and executes fixes with human approval gates.

## Architecture

- **Agent**: FastAPI server on Alibaba Cloud ECS — state machine, webhook ingestion, Qwen reasoning
- **Demo Service**: Simulated microservice with configurable DB pool — the "production" target
- **State Store**: ApsaraDB Redis — persistent incident lifecycle
- **Logging**: SLS (Simple Log Service) — structured JSON traces

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Fill in your QWEN_API, GITHUB_TOKEN, and REDIS_URL

# Start agent
python -m src.main
```

## Demo

See the live demo video for a walkthrough of a real GitHub-triggered incident → automated recovery pipeline.

## License

MIT — see [LICENSE](LICENSE)
