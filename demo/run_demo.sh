#!/bin/bash
# On-Call Autopilot Demo Runner
# Starts all services and the load generator for the live demo

set -e

echo "=== On-Call Autopilot Demo ==="
echo ""

# Check .env
if [ ! -f .env ]; then
    echo "[ERROR] .env file not found. Copy .env.example to .env and fill in your keys."
    exit 1
fi

# Start services
echo "[1/3] Starting agent, demo service, and Redis..."
docker compose up -d agent demo-service redis

echo "[2/3] Waiting for services to be ready..."
sleep 5

echo "[3/3] Starting load generator..."
docker compose up loadgen &

echo ""
echo "=== Demo is running ==="
echo ""
echo "  Demo Service:  http://localhost:3000"
echo "  Agent:         http://localhost:8080"
echo ""
echo "  To trigger an incident, edit demo/service/config.yaml,"
echo "  change pool_size: 20 to pool_size: 2, then:"
echo ""
echo "    git add demo/service/config.yaml"
echo "    git commit -m 'reduce pool size'"
echo "    git push origin main"
echo ""
echo "  Then watch the agent detect and respond:"
echo ""
echo "    docker compose up cli"
echo ""
echo "  Press Ctrl+C to stop the load generator."
echo ""

wait
