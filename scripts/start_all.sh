#!/bin/bash
cd /Users/salginci/Source/qwen_hackathon

python3 -m uvicorn demo.service.main:app --host 0.0.0.0 --port 3000 > /tmp/demo.log 2>&1 &
echo $! > /tmp/demo.pid

python3 demo/service/loadgen.py > /tmp/loadgen.log 2>&1 &
echo $! > /tmp/loadgen.pid

python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8080 > /tmp/agent.log 2>&1 &
echo $! > /tmp/agent.pid

sleep 3

curl -s http://localhost:3000/health && echo ""
curl -s http://localhost:8080/health && echo ""

echo "All services started"
