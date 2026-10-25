"""All automated tests are offline, including when the invoking shell has credentials."""
import pytest


@pytest.fixture(autouse=True)
def isolated_search_credentials(monkeypatch):
    for name in ("TENCENTCLOUD_WSA_APIKEY", "TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY", "TENCENTCLOUD_TOKEN", "SEARCHPRO_AUTH_MODE", "HUNYUAN_API_KEY", "HUNYUAN_MODEL", "TOKENHUB_API_KEY", "TOKENHUB_MODEL", "TOKENHUB_REGION", "DECISION_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
