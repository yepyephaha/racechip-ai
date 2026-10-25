import json

import httpx
import pytest

from app.search import run_search


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, [], "not-an-object", {"Response": None}, {"Response": {"Pages": "wrong"}}])
async def test_malformed_remote_response_is_visible_error(monkeypatch, payload):
    monkeypatch.setenv("TENCENTCLOUD_WSA_APIKEY", "synthetic-key")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=json.dumps(payload), headers={"content-type": "application/json"}))) as client:
        result = await run_search("live", ["fixture"], client)
    assert result["status"] == "error" and result["mode"] == "live"
    assert result["results"] == []


@pytest.mark.asyncio
async def test_business_error_preserves_code_and_request_id(monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_WSA_APIKEY", "synthetic-key")
    body = {"Response": {"Error": {"Code": "UnauthorizedOperation", "Message": "synthetic-key must not leak"}, "RequestId": "fixture-request-id"}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=body))) as client:
        result = await run_search("live", ["fixture"], client)
    assert "UnauthorizedOperation" in result["error"]
    assert result["request_ids"] == ["fixture-request-id"]
    assert result["query_records"][0]["error_code"] == "UnauthorizedOperation"
    assert "synthetic-key" not in json.dumps(result)


@pytest.mark.asyncio
async def test_partial_search_retains_actual_leads_and_failure(monkeypatch):
    monkeypatch.setenv("TENCENTCLOUD_WSA_APIKEY", "synthetic-key")
    counter = 0
    def respond(request):
        nonlocal counter
        counter += 1
        if counter == 1:
            return httpx.Response(200, json={"Response": {"Pages": [json.dumps({"title": "Fixture", "url": "https://example.org/doc"})]}})
        return httpx.Response(503)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await run_search("live", ["fixture1", "fixture2", "fixture3"], client)
    assert result["status"] == "partial" and len(result["results"]) == 1
    assert result["request_count"] == 2 and "503" in result["error"]
