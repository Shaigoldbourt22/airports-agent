import os
from pathlib import Path

import pytest
import yaml
from dotenv import load_dotenv

load_dotenv()

GOLDEN = yaml.safe_load((Path(__file__).parent / "golden.yaml").read_text())


@pytest.fixture(scope="session")
def require_db():
    from app import db

    if not db.DB_PATH.exists():
        pytest.skip(f"{db.DB_PATH} not built. Run: python etl/build_db.py")


@pytest.fixture(scope="session")
def require_model():
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "llm: calls the Gemini API, costs money and is non-deterministic"
    )
