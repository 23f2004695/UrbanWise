#!/bin/sh
# AWS Lambda entry point. The Lambda Web Adapter layer starts this and forwards
# each request to gunicorn, so the Flask app runs unchanged.
exec python3 -m gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 8 --timeout 60 app:app
