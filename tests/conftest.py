import os
import sys
import tempfile

import pytest

# Must patch DB_PATH before ANY app imports happen
import database.db as db_module

_db_fd, _db_path = tempfile.mkstemp(suffix=".spendly.test.db")
db_module.DB_PATH = _db_path

# Now import the real app — init_db() and seed_db() will use the test DB
# We need to re-import app.py cleanly
# Remove any cached app module
for mod in list(sys.modules.keys()):
    if "app" in mod or "database" in mod:
        del sys.modules[mod]

# Re-import database modules fresh
import database.db  # noqa: E402
database.db.init_db()
database.db.seed_db()

import app as _app_module  # noqa: E402
from database.db import get_db  # noqa: E402


@pytest.fixture
def app():
    """Return the real Flask app configured with a temporary database."""
    _app_module.app.config.update({
        "TESTING": True,
    })
    yield _app_module.app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Return a database connection for test setup/teardown."""
    conn = get_db()
    yield conn
    conn.close()


# Cleanup the temp DB at session end
def pytest_sessionfinish(session, exitstatus):
    import os
    os.close(_db_fd)
    os.unlink(_db_path)
