# services/eventa_adapter.py
# Thin adapter that calls your Eventa-APIwithCatalogue /search endpoint

import os
import httpx

EVENTA_API_URL = os.getenv("EVENTA_API_URL")  # e.g. https://<cloud-run>/search
EVENTA_API_KEY = os.getenv("EVENTA_API_KEY")  # optional

def run_query_catalogue(args: dict) -> dict:
    if not EVENTA_API_URL:
        raise RuntimeError("EVENTA_API_URL is not set")

    headers = {}
    if EVENTA_API_KEY:
        headers["Authorization"] = f"Bearer {EVENTA_API_KEY}"

    # Conservative timeouts
    timeout = httpx.Timeout(5.0, connect=3.0)
    with httpx.Client(timeout=timeout) as http:
        r = http.get(EVENTA_API_URL, params=args, headers=headers)
        r.raise_for_status()
        return r.json()
