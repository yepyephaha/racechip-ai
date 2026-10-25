"""Fetch only exact catalog URLs and match bounded source passages. No arbitrary fetcher."""
import hashlib
import re
from datetime import datetime
from html import unescape
from zoneinfo import ZoneInfo

import httpx

# Matching phrases are maintained from the corresponding vendor/author originals.
ANCHORS = {
    "rt1062-official-hardware": ("All I/O pins output 3.3V and are 3.3V tolerant", ["interfaces", "logic_voltage_v", "io_input_max_v"]),
    "rt1062-official-availability": ("Available for Backorder", ["caveats"]),
    "openmv-official-hardware": ("All I/O pins output 3.3V and are 5V tolerant", ["interfaces", "logic_voltage_v", "io_input_max_v"]),
    "openmv-official-lifecycle": ("We are no longer producing this version", ["caveats"]),
    "openmv-community-apriltag-pipeline": ("The higher fps example only works for the MT9V034", ["engineering_experience"]),
}


def plain_text(html: str) -> str:
    html = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


async def review_sources(catalog: list[dict], target_id: str | None):
    entries = []
    for hw in catalog:
        if target_id and hw["id"] != target_id:
            continue
        for e in hw["evidence"]:
            if e["id"] in ANCHORS:
                entries.append((hw, e))
    if not target_id:
        entries = entries[:2]
    # At most three distinct original URLs. Never send search credentials to these hosts.
    urls = list(dict.fromkeys(e["url"] for _, e in entries))[:3]
    fetched = {}
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, headers={"User-Agent": "RaceChipAI/0.2 source-verification"}) as client:
        for url in urls:
            try:
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        fetched[url] = (None, None, "HTTP " + str(response.status_code))
                        continue
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > 2_000_000:
                            raise ValueError("oversized")
                    raw = bytes(chunks)
                    fetched[url] = (plain_text(raw.decode("utf-8", errors="replace")), hashlib.sha256(raw).hexdigest(), None)
            except (httpx.HTTPError, ValueError):
                fetched[url] = (None, None, "原文请求失败或超出读取上限")
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    for hw, e in entries:
        if e["url"] not in fetched:
            continue
        content, digest, error = fetched[e["url"]]
        phrase, fields = ANCHORS[e["id"]]
        matches = content is not None and phrase.casefold() in content.casefold()
        # A single matching passage is a scoped source review, never an independent replication.
        yield_record = {"evidence_id": e["id"], "hardware_id": hw["id"], "exact_model": hw["name"],
                        "url": e["url"], "kind": e["kind"], "fields": fields, "status": "matched" if matches else "insufficient",
                        "excerpt": phrase if matches else "", "locator": "产品页 Features / 生命周期段落" if e["kind"] == "official" else "论坛完整讨论末尾，2021-06-15回复",
                        "retrieved_at": now, "sha256": digest, "review_method": "exact_catalog_url_and_bounded_phrase_match",
                        "reviewer": "RaceChip deterministic source checker v1", "hardware_reproduced": False,
                        "error": error if error else None if matches else "原文未匹配预期摘句；保持证据不足"}
        yield yield_record


async def collect_reviews(catalog: list[dict], target_id: str | None) -> list[dict]:
    return [item async for item in review_sources(catalog, target_id)]
