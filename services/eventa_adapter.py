'''
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
'''

# services/eventa_adapter.py
# Adapter to call Eventa-APIwithCatalogue.
# Supports both:
#  - GET  {EVENTA_API_URL}?<query-params>    (typical for /search)
#  - POST {EVENTA_API_URL}  with JSON body   (typical for /chat)
#
# Configure via env:
#   EVENTA_API_URL      = full endpoint (e.g. https://.../search  OR  https://.../chat)
#   EVENTA_API_KEY      = optional Bearer token
#   EVENTA_HTTP_METHOD  = GET (default) | POST_JSON

import os
import httpx
from typing import Dict, Any

EVENTA_API_URL = os.getenv("EVENTA_API_URL")
EVENTA_API_KEY = os.getenv("EVENTA_API_KEY")
EVENTA_HTTP_METHOD = os.getenv("EVENTA_HTTP_METHOD", "GET").upper()

def _headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if EVENTA_API_KEY:
        h["Authorization"] = f"Bearer {EVENTA_API_KEY}"
    if EVENTA_HTTP_METHOD == "POST_JSON":
        h["Content-Type"] = "application/json"
    return h

def run_query_catalogue(args: Dict[str, Any]) -> Dict[str, Any]:
    if not EVENTA_API_URL:
        raise RuntimeError("EVENTA_API_URL is not set")

    timeout = httpx.Timeout(8.0, connect=4.0)
    with httpx.Client(timeout=timeout) as http:
        if EVENTA_HTTP_METHOD == "POST_JSON":
            # POST JSON to /chat
            r = http.post(EVENTA_API_URL, headers=_headers(), json=args)
        else:
            # GET to /search
            r = http.get(EVENTA_API_URL, headers=_headers(), params=args)
        r.raise_for_status()
        return r.json()
