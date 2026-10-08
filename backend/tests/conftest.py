import os
import sys

# Let tests import `app` and `services` the same way app.py does.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Rate limiters are process-wide; start every test with a clean slate."""
    import app as app_module
    for limiter in app_module.LIMITS.values():
        limiter._hits.clear()
    yield
