"""Shared JSON store in S3, used only when deployed (RESULTS_BUCKET is set).

The scheduled pipeline writes wind grids and results here, so every API
instance can reuse them instead of calling Open-Meteo again. Locally (no
bucket) every function is a no-op and the app fetches live as before.
"""

import json
import logging
import os
import threading

log = logging.getLogger(__name__)

_client = None
_client_lock = threading.Lock()


def bucket():
    return os.getenv("RESULTS_BUCKET") or None


def _s3():
    global _client
    with _client_lock:
        if _client is None:
            import boto3  # only needed on AWS, where the Lambda runtime provides it
            _client = boto3.client("s3")
        return _client


def get_json(key):
    """The stored object, or None if it's missing, unreadable or storage is off."""
    if not bucket():
        return None
    try:
        body = _s3().get_object(Bucket=bucket(), Key=key)["Body"].read()
        return json.loads(body)
    except Exception as exc:  # a missing or broken copy just means "fetch live"
        if getattr(exc, "response", {}).get("Error", {}).get("Code") != "NoSuchKey":
            log.warning("S3 read %s failed: %s", key, exc)
        return None


def put_json(key, data):
    """Store `data`; returns False instead of raising, since storage is a bonus."""
    if not bucket():
        return False
    try:
        _s3().put_object(Bucket=bucket(), Key=key, ContentType="application/json",
                         Body=json.dumps(data, separators=(",", ":")).encode())
        return True
    except Exception as exc:
        log.warning("S3 write %s failed: %s", key, exc)
        return False
