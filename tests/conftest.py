# tests/conftest.py
import os
import pytest

pytest_plugins = ("pytest_asyncio",)


# Ensure auth is disabled and no DB for unit tests
@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "1")
    if "DATABASE_URL" not in os.environ:
        monkeypatch.delenv("DATABASE_URL", raising=False)
