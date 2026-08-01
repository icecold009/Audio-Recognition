from __future__ import annotations

import pytest

from web import app as web_app


@pytest.fixture(autouse=True)
def isolate_local_api_secret(monkeypatch):
    """Keep an ignored developer .env from changing route-test contracts."""
    monkeypatch.setattr(web_app, "INTERNAL_API_SECRET", "")
