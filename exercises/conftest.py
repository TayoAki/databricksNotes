"""Shared pytest fixtures: one SparkSession per test session (JVM start-up is expensive)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.spark_session import get_spark  # noqa: E402


@pytest.fixture(scope="session")
def spark():
    session = get_spark("exercises-tests")
    yield session
    session.stop()
