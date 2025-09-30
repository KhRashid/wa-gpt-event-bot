# services/db.py
import os, json
from google.cloud import firestore

def _from_inline_json():
    data = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if not data:
        raise RuntimeError("Missing GOOGLE_APPLICATION_CREDENTIALS_JSON")
    creds_path = "/tmp/gcp-creds.json"
    with open(creds_path, "w") as f:
        f.write(data)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

_from_inline_json()
db = firestore.Client()
