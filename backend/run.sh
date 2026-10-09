#!/bin/sh
# AWS Lambda entry point. The Lambda Web Adapter layer starts this and forwards
# each request to gunicorn, so the Flask app runs unchanged.
# --keep-alive is long because Lambda freezes the instance between requests: with
# gunicorn's 2 s default it drops the adapter's connection while frozen, and the
# next request fails with "connection reset". --timeout 0 for the same reason:
# gunicorn's watchdog counts frozen time and kills the worker; Lambda has its own timeout.
exec python3 -m gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 8 --timeout 0 \
  --keep-alive 86400 --access-logfile - --access-logformat '"%(r)s" %(s)s %(M)sms' app:app
