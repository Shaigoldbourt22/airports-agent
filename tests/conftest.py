import os
from pathlib import Path

import pytest
import yaml
from dotenv import load_dotenv

from tests import fixture_db

load_dotenv()

GOLDEN = yaml.safe_load((Path(__file__).parent / "golden.yaml").read_text())


@pytest.fixture(scope="session")
def fixture_data(tmp_path_factory):
    """Point app.db at a small database with known values.

    The scoring tests assert on exact scores, so they need fixed inputs. This
    also lets them run anywhere, including CI, where no ETL output exists.
    """
    from app import db

    path = fixture_db.build(tmp_path_factory.mktemp("db") / "airports.db")
    original_path, original_con = db.DB_PATH, db._con
    db.DB_PATH, db._con, db._mtime = path, None, None
    yield path
    db.DB_PATH, db._con, db._mtime = original_path, original_con, None


@pytest.fixture(scope="session")
def require_db():
    """Skip when the real ETL output is missing."""
    from app import db

    if not db.DB_PATH.exists():
        pytest.skip(f"{db.DB_PATH} not built. Run: python etl/build_db.py")


@pytest.fixture(scope="session")
def require_deployment():
    """Skip when there is no deployment to test, fail when it is unreachable."""
    from tests import deployed

    try:
        deployed.base_url()
    except deployed.NotDeployed:
        pytest.skip("AGENT_URL not set. Point it at the deployment to test.")
    assert deployed.healthy(), f"{deployed.base_url()} is not responding"


@pytest.fixture(scope="session")
def require_model():
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "llm: calls the Gemini API, costs money and is non-deterministic"
    )
