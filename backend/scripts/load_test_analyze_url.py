import json
import time
import statistics
import urllib.request
import urllib.error
import os

BASE_URL = "http://127.0.0.1:8000"
ENDPOINT = "/api/analyze-url"
N = 100
API_KEY = os.getenv("LINKGUARD_API_KEY", "DEV_ONLY_PLACEHOLDER")

PAYLOADS = [
    {"url": "https://example.com"},
    {"url": "https://github.com"},
    {"url": "https://google.com"},
    {"url": "http://login-verify-account.net/reset"},
    {"url": "https://secure-reset-password.com"},
]

def percentile(values, p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = int(round((p / 100.0) * (len(s) - 1)))
    return s[k]

def main():
    times_ms = []
    errors = 0

    for i in range(N):
        payload = PAYLOADS[i % len(PAYLOADS)]
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            BASE_URL + ENDPOINT,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": API_KEY,
            },
            method="POST",
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()  # consume body
                if resp.status >= 400:
                    errors += 1
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            errors += 1
        finally:
            t1 = time.perf_counter()

        times_ms.append((t1 - t0) * 1000.0)

    avg = statistics.mean(times_ms)
    p95 = percentile(times_ms, 95)
    mx = max(times_ms)

    print(f"Requests: {N}")
    print(f"Avg ms:  {avg:.2f}")
    print(f"p95 ms:  {p95:.2f}")
    print(f"Max ms:  {mx:.2f}")
    print(f"Errors:  {errors}")

if __name__ == "__main__":
    main()
