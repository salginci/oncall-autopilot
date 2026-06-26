import asyncio
import time
import random
import threading
import yaml
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

CONFIG_PATH = Path(__file__).parent / "config.yaml"

app = FastAPI(title="Orders Service (Demo)", version="1.0.0")


class SimulatedPool:
    def __init__(self, size: int):
        self.size = size
        self.available = list(range(size))
        self.lock = threading.Lock()

    def acquire(self) -> int | None:
        with self.lock:
            if self.available:
                return self.available.pop()
            return None

    def release(self, slot: int):
        with self.lock:
            self.available.append(slot)

    def resize(self, new_size: int):
        with self.lock:
            self.size = new_size
            self.available = list(range(new_size))


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.total = 0
        self.errors = 0
        self.latencies: list[float] = []

    def record(self, latency: float, is_error: bool):
        with self.lock:
            self.total += 1
            if is_error:
                self.errors += 1
            self.latencies.append(latency)
            if len(self.latencies) > 1000:
                self.latencies = self.latencies[-500:]

    @property
    def snapshot(self) -> dict:
        with self.lock:
            lats = sorted(self.latencies[-100:]) if self.latencies else [0]
            p50 = lats[len(lats) // 2] if lats else 0
            return {
                "total_requests": self.total,
                "error_count": self.errors,
                "latency_p50_ms": round(p50, 2),
                "pool_size": pool.size,
                "pool_available": len(pool.available),
            }


pool = SimulatedPool(20)
metrics = Metrics()


def load_config():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return config


def reload_config():
    config = load_config()
    new_size = config["database"]["pool_size"]
    pool.resize(new_size)
    return config


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_config()
    yield


app.router.lifespan_context = lifespan


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "orders-service",
        "pool": {"size": pool.size, "available": len(pool.available)},
    }


@app.get("/health/{dependency}")
async def health_dependency(dependency: str):
    return {"status": "healthy", "dependency": dependency}


@app.get("/metrics")
async def get_metrics():
    return metrics.snapshot


@app.get("/admin/config")
async def get_config():
    config = load_config()
    return {"config": config}


@app.post("/admin/pool/{size}")
async def admin_set_pool(size: int):
    global metrics
    pool.resize(size)
    metrics = Metrics()
    return {"status": "resized", "pool_size": pool.size, "pool_available": len(pool.available)}


@app.post("/admin/reload")
async def admin_reload():
    global metrics
    config = reload_config()
    metrics = Metrics()
    return {"status": "reloaded", "pool_size": config["database"]["pool_size"]}


@app.get("/api/orders")
async def get_orders():
    start = time.time()
    slot = pool.acquire()

    if slot is None:
        latency = (time.time() - start) * 1000
        metrics.record(latency, True)
        raise HTTPException(status_code=503, detail="Connection pool exhausted")

    try:
        latency_ms = random.uniform(5, 30)
        await asyncio.sleep(latency_ms / 1000)
        total_latency = (time.time() - start) * 1000
        metrics.record(total_latency, False)
        return {"orders": [{"id": i, "status": "processing"} for i in range(3)], "pool_slot": slot}
    finally:
        pool.release(slot)


@app.post("/api/orders")
async def create_order():
    start = time.time()
    slot = pool.acquire()

    if slot is None:
        latency = (time.time() - start) * 1000
        metrics.record(latency, True)
        raise HTTPException(status_code=503, detail="Connection pool exhausted")

    try:
        latency_ms = random.uniform(10, 50)
        await asyncio.sleep(latency_ms / 1000)
        total_latency = (time.time() - start) * 1000
        metrics.record(total_latency, False)
        return {"order": {"id": random.randint(1000, 9999), "status": "created"}, "pool_slot": slot}
    finally:
        pool.release(slot)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("demo.service.main:app", host="0.0.0.0", port=3000, reload=True)
