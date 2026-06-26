import os
import time
import random
import threading
import httpx

SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:3000")


def format_latency(ms):
    if ms < 50:
        return f"\033[32m{ms:.0f}ms\033[0m"
    elif ms < 200:
        return f"\033[33m{ms:.0f}ms\033[0m"
    else:
        return f"\033[31m{ms:.0f}ms\033[0m"


def worker():
    while True:
        endpoint = "/api/orders"
        is_post = random.choice([True, False, False])

        try:
            start = time.time()
            if is_post:
                resp = httpx.post(f"{SERVICE_URL}{endpoint}", timeout=5.0)
            else:
                resp = httpx.get(f"{SERVICE_URL}{endpoint}", timeout=5.0)

            latency = (time.time() - start) * 1000

            if resp.status_code == 200:
                print(f"[OK]   {resp.status_code} {endpoint} {format_latency(latency)}")
            else:
                print(f"[FAIL] \033[1;31m{resp.status_code}\033[0m {endpoint} {format_latency(latency)}")
        except Exception as e:
            print(f"[ERR]  {endpoint} {e}")

        time.sleep(random.uniform(0.005, 0.01))


def main():
    num_workers = 15
    print(f"Starting {num_workers} concurrent load generators...")
    for i in range(num_workers):
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    while True:
        time.sleep(10)


if __name__ == "__main__":
    main()
