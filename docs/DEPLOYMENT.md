# Deployment Guide — Alibaba Cloud

## Architecture

| Service | Alibaba Cloud Product | Purpose |
|---------|----------------------|---------|
| Agent API | ECS (Elastic Compute Service) | Incident detection + Qwen reasoning |
| Demo Service | ECS (same instance) | Simulated "production" app |
| State Store | ApsaraDB for Redis | Persistent incident lifecycle |
| AI Reasoning | Qwen Cloud (dashscope-intl) | Triage, Investigate, Remediate |
| Logging | SLS (Simple Log Service) | Structured JSON traces |

## Step 1: Create ECS Instance

1. Go to [Alibaba Cloud ECS Console](https://ecs.console.aliyun.com)
2. Create instance: **Ubuntu 22.04**, 2 vCPU / 4 GB RAM (minimum)
3. In Security Group, add inbound rules:
   - **8080** (Agent dashboard)
   - **3000** (Demo service)
   - **22** (SSH)
4. Note the **Public IP**

## Step 2: Create ApsaraDB Redis Instance

1. Go to [ApsaraDB for Redis Console](https://kvstore.console.aliyun.com)
2. Create instance: Standard, 1 GB (smallest), same VPC as ECS
3. Note the **Connection String** (format: `r-xxx.redis.rds.aliyuncs.com:6379`)

## Step 3: SSH into ECS and install Docker

```bash
ssh root@<ECS_PUBLIC_IP>

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# Install Docker Compose
apt-get update && apt-get install -y docker-compose-plugin
```

## Step 4: Clone and configure

```bash
git clone https://github.com/salginci/oncall-autopilot.git
cd oncall-autopilot

# Create .env
cat > .env << 'EOF'
QWEN_APIKEY=sk-ws-H...your-key...
GITHUB_TOKEN=ghp_...your-token...
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-turbo
REDIS_URL=redis://r-xxx.redis.rds.aliyuncs.com:6379/0
DEMO_SERVICE_URL=http://<ECS_PUBLIC_IP>:3000
AGENT_POLL_INTERVAL=5
ERROR_RATE_THRESHOLD=0.10
LATENCY_THRESHOLD_MS=500
EOF
```

## Step 5: Start services

```bash
# Start agent + demo + Redis (local container, not ApsaraDB for simplicity)
# Or use ApsaraDB Redis by pointing REDIS_URL
docker compose up -d
```

## Step 6: Verify

```bash
curl http://<ECS_PUBLIC_IP>:8080/health
curl http://<ECS_PUBLIC_IP>:3000/health
```

Visit `http://<ECS_PUBLIC_IP>:8080/dashboard`

## Alibaba Cloud Services Proof

The following files demonstrate use of Alibaba Cloud services:

1. **Qwen Cloud API** (`src/config.py:9`): `QWEN_BASE_URL` points to `dashscope-intl.aliyuncs.com`
2. **ApsaraDB Redis** (`src/config.py:15`): `REDIS_URL` supports `r-xxx.redis.rds.aliyuncs.com` format
3. **All agent files** (`src/agents/*.py`): Call Qwen Cloud API via `dashscope-intl.aliyuncs.com`

## Notes

- Unverified Qwen Cloud accounts have "Free quota only" enforced — if quota is exhausted, calls will fail with 403. Verify your account (add payment method) or apply for hackathon credits.
- The dashboard HTML links use `localhost` — update to ECS public IP for remote access.
