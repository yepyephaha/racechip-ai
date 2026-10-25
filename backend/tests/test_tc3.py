import json
import re

import httpx
import pytest

from app.auth import auth_mode, build_request
from app.search import run_search


@pytest.fixture
def tc3_env(monkeypatch):
    monkeypatch.delenv("TENCENTCLOUD_WSA_APIKEY", raising=False)
    monkeypatch.setenv("SEARCHPRO_AUTH_MODE", "tc3")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_ID", "fixture-secret-id")
    monkeypatch.setenv("TENCENTCLOUD_SECRET_KEY", "fixture-secret-key")


def test_tc3_headers_and_utc_date(tc3_env):
    endpoint, headers, body = build_request("颜色检测", timestamp=1551113065)
    assert endpoint == "https://wsa.tencentcloudapi.com/"
    assert headers["X-TC-Version"] == "2025-05-08" and headers["X-TC-Action"] == "SearchPro"
    assert headers["Host"] == "wsa.tencentcloudapi.com" and "X-TC-Region" not in headers
    assert "/2019-02-25/wsa/tc3_request" in headers["Authorization"]
    assert re.search(r"Signature=[0-9a-f]{64}$", headers["Authorization"])
    assert "fixture-secret-key" not in json.dumps(headers)
    assert json.loads(body) == {"Query": "颜色检测"}
    assert build_request("颜色检测", timestamp=1551113065)[1] == headers
    assert build_request("不同请求", timestamp=1551113065)[1]["Authorization"] != headers["Authorization"]


def test_incomplete_pair_is_not_configured(tc3_env, monkeypatch):
    monkeypatch.delenv("TENCENTCLOUD_SECRET_KEY")
    assert auth_mode() is None


@pytest.mark.asyncio
async def test_tc3_transport_uses_cloud_endpoint_and_redacts_echo(tc3_env):
    def respond(req):
        assert str(req.url) == "https://wsa.tencentcloudapi.com/"
        assert req.headers["Authorization"].startswith("TC3-HMAC-SHA256 ")
        assert req.headers["X-TC-Action"] == "SearchPro"
        assert json.loads(req.content) == {"Query": "fixture"}
        return httpx.Response(200, json={"Response": {"Pages": [json.dumps({"title": "fixture-secret-key", "url": "https://example.org"})], "RequestId": "fixture-request", "Version": "standard"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await run_search("live", ["fixture"], client)
    assert result["status"] == "ok" and result["auth_mode"] == "tc3"
    assert "fixture-secret-key" not in json.dumps(result)
