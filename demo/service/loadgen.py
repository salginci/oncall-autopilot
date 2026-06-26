import time
import random
import httpx

import os
SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:3000")


def format_latency(ms):
    if ms < 50:
        return f"\033[32m{ms:.0f}ms\033[0m"
    elif ms < 200:
        return f"\033[33m{ms:.0f}ms\033[0m"
    else:
        return f"\033[31m{ms:.0f}ms\033[0m"


def main():
    endpoints = ["/api/orders", "/api/orders"]
    post = [False, True]

    while True:
        idx = random.randint(0, len(endpoints) - 1)
        endpoint = endpoints[idx]
        is_post = post[idx]

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

        time.sleep(random.uniform(0.05, 0.15))


if __name__ == "__main__":
    main()
