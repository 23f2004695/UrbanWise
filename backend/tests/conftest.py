import os
import sys

# Let tests import `app` and `services` the same way app.py does.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Rate limiters are process-wide; start every test with a clean slate."""
    import app as app_module
    for limiter in [*app_module.LIMITS.values(), *app_module.TOTAL_LIMITS.values()]:
        limiter._hits.clear()
    yield


@pytest.fixture(autouse=True)
def _reset_last_good():
    """Saved upstream copies are process-wide too; don't let them leak between tests."""
    from services import air, smoke_trail
    for fetch in (air._fetch_air, smoke_trail._fetch_wind_grid, smoke_trail._fetch_fires):
        fetch.__wrapped__.last_good.clear()
    yield
