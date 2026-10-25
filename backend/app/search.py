"""SearchPro REST Bearer adapter. Never silently replace live failures with mock."""
import json
import os
import re
from .auth import auth_mode, build_request, redact
from urllib.parse import urlparse

import httpx

ENDPOINT = "https://api.wsa.cloud.tencent.com/SearchPro"


class SearchProError(ValueError):
    def __init__(self, code: str, request_id: str | None):
        self.code = re.sub(r"[^A-Za-z0-9_.-]", "", code)[:100] or "UnknownError"
        self.request_id = re.sub(r"[^A-Za-z0-9_.-]", "", str(request_id or ""))[:200]
        super().__init__("SearchPro 返回错误代码：" + self.code)


def safe_url(value: str) -> str | None:
    try:
        parsed = urlparse(value)
        return value if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password else None
    except (ValueError, TypeError):
        return None


def build_queries(problem: dict, constraints: dict, claim: dict | None = None) -> list[str]:
    if claim:
        model = {"openmv-rt1062": "OpenMV Cam RT1062", "openmv-h7-plus": "OpenMV Cam H7 Plus"}.get(claim["hardware_id"], claim["hardware_id"])
        field = {"io_tolerance": "I/O 3.3V tolerant 5V UART input", "algorithm_fps": "AprilTag FPS readout control " + claim.get("sensor", ""),
                 "lifecycle": "no longer producing lifecycle discontinued", "interface": "UART SPI I2C interface pinout"}[claim["field"]]
        return [f"{model} {field} official documentation", f"{model} {field} {claim.get('firmware','')} 适用条件",
                f"{model} {field} forums engineering experience 实测"]
    tasks = " ".join(problem["tasks"]) or "robot vision hardware"
    interfaces = " ".join(constraints.get("required_interfaces", []))
    return [f"{tasks} OpenMV ESP32-S3-EYE Maix Bit 官方文档 接口 引脚",
            f"{tasks} 机器人视觉 {interfaces} datasheet official Raspberry Pi",
            f"{tasks} OpenMV Maix forum GitHub issue 工程经验 光照 调试"]


def configured() -> bool:
    return auth_mode() is not None


def parse_pages(payload: dict, query_index: int) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("SearchPro 响应不是对象")
    response = payload.get("Response")
    if not isinstance(response, dict):
        raise ValueError("SearchPro 响应缺少 Response 对象")
    if response.get("Error"):
        error = response["Error"]
        code = str(error.get("Code", "UnknownError"))[:100] if isinstance(error, dict) else "UnknownError"
        raise SearchProError(code, response.get("RequestId"))
    pages = response.get("Pages", [])
    if not isinstance(pages, list):
        raise ValueError("SearchPro Response.Pages 格式不符")
    results = []
    for i, raw in enumerate(pages[:10]):
        try:
            page = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            continue
        if not isinstance(page, dict):
            continue
        url = safe_url(page.get("url", ""))
        if not url:
            continue
        # Results are discovery leads, not verified hardware claims. No trust score copied from score.
        results.append({"id": f"search-{query_index}-{i}", "title": str(page.get("title") or url)[:300],
                        "url": url, "snippet": str(page.get("passage") or page.get("content") or "")[:4000],
                        "kind": "search_lead", "source": "元宝 SearchPro 实时搜索（网页内容未自动核验）"})
    return results


async def run_search(mode: str, queries: list[str], client: httpx.AsyncClient | None = None, sites: list[str | None] | None = None) -> dict:
    result = {"provider": "tencent-searchpro" if mode == "live" else "mock-fixture", "mode": mode,
              "status": "ok", "queries": queries, "results": [], "warnings": [], "error": None,
              "request_count": 0, "request_ids": [], "query_records": []}
    if mode == "mock":
        result["status"] = "mock"
        result["warnings"] = ["MOCK 测试：本次没有调用元宝搜索，也没有产生真实联网查询证据。硬件库来源为单独人工核验的固定资料。"]
        result["results"] = [{"id": "mock-1", "title": "[MOCK] 官方规格检索结果结构示例", "url": "https://example.invalid/mock-spec",
                              "snippet": "这是用于界面联调的合成检索记录，不能作为硬件规格或比赛真实查询凭据。", "kind": "mock", "source": "MOCK 合成测试数据"},
                             {"id": "mock-2", "title": "[MOCK] 社区工程经验检索结果结构示例", "url": "https://example.invalid/mock-community",
                              "snippet": "合成示例：实际帧率受图像分辨率和光照影响。此记录不来自真实用户或网络搜索。", "kind": "mock", "source": "MOCK 合成测试数据"}]
        return result
    result["auth_mode"] = auth_mode()
    if not configured():
        result.update(status="error", error="未配置 SearchPro 凭据；未发起联网请求。请设置 TENCENTCLOUD_WSA_APIKEY，或 TENCENTCLOUD_SECRET_ID 与 TENCENTCLOUD_SECRET_KEY，并重启后端。")
        return result
    own_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=httpx.Timeout(25, connect=10), follow_redirects=False)
    try:
        for index, query in enumerate(queries[:3]):
            result["request_count"] += 1
            record = {"query": query, "status": "error", "request_id": None, "result_count": 0}
            result["query_records"].append(record)
            try:
                site=sites[index] if sites and index<len(sites) else None
                endpoint, headers, payload_bytes = build_request(query,site=site)
                record["site_filter"]=site
                response = await client.post(endpoint, headers=headers, content=payload_bytes)
                response.raise_for_status()
                payload = response.json()
                pages = parse_pages(payload, index)
                for page in pages:
                    page["query"] = query
                result["results"].extend(pages)
                request_id = payload.get("Response", {}).get("RequestId")
                if request_id:
                    result["request_ids"].append(str(request_id)[:200])
                record.update(status="ok", request_id=request_id, result_count=len(pages))
                record["version"] = payload.get("Response", {}).get("Version")
                record["message"] = str(payload.get("Response", {}).get("Msg") or "")[:300]
            except SearchProError as error:
                result["error"] = str(error)
                record["error_code"] = error.code
                if error.request_id:
                    result["request_ids"].append(error.request_id)
                    record["request_id"] = error.request_id
                break
            except httpx.HTTPStatusError as error:
                result["error"] = f"SearchPro HTTP {error.response.status_code}；请核对鉴权、额度及官方服务状态。"
                break
            except (httpx.RequestError, ValueError, TypeError, KeyError):
                result["error"] = "SearchPro 请求失败或响应结构异常；未使用 mock 替代。请检查网络及官方服务。"
                break
        result["status"] = "partial" if result["error"] and result["results"] else "error" if result["error"] else "ok"
        if not result["results"] and not result["error"]:
            result["warnings"].append("真实请求已完成，但未得到带可用链接的结果；不能据此证明不存在相关资料。")
        result["warnings"].append("实时搜索结果是待核验线索，P0 不用网页摘要覆盖已核验的硬件参数；社区经验不构成规格保证。")
        return json.loads(redact(json.dumps(result, ensure_ascii=False)))
    finally:
        if own_client:
            await client.aclose()
