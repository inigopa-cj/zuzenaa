"""Test configuration.

Environment must be set before importing the app (settings and the DB engine
are built at import time).
"""

import os
import tempfile

_fd, _db_path = tempfile.mkstemp(prefix="zuzenaa-test-", suffix=".db")
os.close(_fd)

_data_dir = tempfile.mkdtemp(prefix="zuzenaa-data-")

os.environ["ZUZENAA_DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_path}"
os.environ["ZUZENAA_SECRET_KEY"] = "test-secret"
os.environ["ZUZENAA_GITHUB_OAUTH_CLIENT_ID"] = "test-client"
os.environ["ZUZENAA_GITHUB_OAUTH_CLIENT_SECRET"] = "test-secret"
os.environ["ZUZENAA_ALLOW_ENV_TOKEN"] = "false"
os.environ["ZUZENAA_DATA_ROOT"] = _data_dir
