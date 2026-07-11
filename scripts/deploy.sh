#!/bin/bash
# Run this on the ECS instance after Terraform provisions it.
# Usage: ssh root@<ECS_IP> 'bash -s' < scripts/deploy.sh
set -e

echo "=== On-Call Autopilot — Deploy to Alibaba Cloud ==="

# ── Clone repo ──
if [ ! -d /opt/oncall-autopilot ]; then
  git clone https://github.com/salginci/oncall-autopilot.git /opt/oncall-autopilot
else
  cd /opt/oncall-autopilot && git pull
fi

cd /opt/oncall-autopilot

# ── Create .env from environment variables ──
cat > .env << EOF
QWEN_APIKE=${QWEN_APIKEY}
GITHUB_TOKEN=${GITHUB_TOKEN}
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-turbo
REDIS_URL=${REDIS_URL:-redis://redis:6379/0}
DEMO_SERVICE_URL=http://localhost:3000
AGENT_POLL_INTERVAL=5
ERROR_RATE_THRESHOLD=0.10
LATENCY_THRESHOLD_MS=500
EOF

# ── Pull and start ──
docker compose -f docker-compose.prod.yml pull 2>/dev/null || true
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

sleep 5

# ── Verify ──
echo ""
echo "=== Health Checks ==="
curl -s http://localhost:8080/health && echo ""
curl -s http://localhost:3000/health && echo ""

echo ""
echo "=== Dashboard ==="
echo "http://$(curl -s ifconfig.me 2>/dev/null):8080/dashboard"
