"""Read public SearchPro-discovered pages without passing search/model credentials."""
import asyncio
import io
import ipaddress
import re
import socket
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from pypdf import PdfReader

from .source_review import plain_text

DNS_CACHE = {}
DNS_LOCKS = {}


async def doh_addresses(host: str):
    lock = DNS_LOCKS.setdefault(host, asyncio.Lock())
    async with lock:
        cached = DNS_CACHE.get(host)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        # Some local TUN proxies return RFC benchmarking addresses for public names.
        # Resolve independently over verified TLS rather than allowing reserved IPs.
        async with httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False) as client:
            for ip, name, path in (("1.1.1.1", "cloudflare-dns.com", "dns-query"), ("8.8.8.8", "dns.google", "resolve")):
                try:
                    response = await client.get(f"https://{ip}/{path}", params={"name": host, "type": "A"},
                                                headers={"Host": name, "Accept": "application/dns-json"}, extensions={"sni_hostname": name})
                    response.raise_for_status()
                    addresses = list(dict.fromkeys(item["data"] for item in response.json().get("Answer", []) if item.get("type") == 1))
                    if addresses and all(ipaddress.ip_address(value).is_global for value in addresses):
                        DNS_CACHE[host] = (time.monotonic()+300, addresses)
                        return addresses
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    continue
        raise ValueError("公共来源无法取得可验证的公网地址")


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def brief_quote(text: str, limit=180) -> str:
    text = normalized(text)[:limit]
    words = list(re.finditer(r"[A-Za-z0-9][A-Za-z0-9'_-]*", text))
    return text[:words[24].end()] if len(words) > 25 else text


async def public_target(url: str):
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.password:
        raise ValueError("不支持的来源地址")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    if port != (443 if parts.scheme == "https" else 80):
        raise ValueError("只读取公开网页端口")
    host = parts.hostname.encode("idna").decode()
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise ValueError("来源不是公开互联网地址")
    addresses = await asyncio.to_thread(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
    ips = list(dict.fromkeys(item[4][0] for item in addresses))
    benchmarks = (ipaddress.ip_network("198.18.0.0/15"), ipaddress.ip_network("2001:2::/48"))
    reserved = [ipaddress.ip_address(ip) for ip in ips if not ipaddress.ip_address(ip).is_global]
    if reserved and all(any(value in network for network in benchmarks if value.version == network.version) for value in reserved):
        ips = await doh_addresses(host)
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("来源不是公开互联网地址")
    # Connect to a checked IP rather than resolving twice; keep the original TLS name.
    ip = sorted(ips, key=lambda value: ":" in value)[0]
    netloc = f"[{ip}]" if ":" in ip else ip
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, "")), host


def extract_document(raw: bytes, content_type: str, url: str) -> list[dict]:
    if "pdf" in content_type or raw.startswith(b"%PDF-"):
        reader = PdfReader(io.BytesIO(raw))
        chunks = []
        remaining = 200_000
        for index, page in enumerate(reader.pages[:80]):
            text = normalized(page.extract_text() or "")[:remaining]
            if text:
                chunks.append({"locator": f"PDF 第{index+1}页", "text": text})
                remaining -= len(text)
            if remaining <= 0:
                break
        return chunks
    if not any(kind in content_type for kind in ("html", "text/", "xml")):
        raise ValueError("来源格式不支持文本核对")
    html = raw.decode("utf-8", errors="replace")
    text = plain_text(html)[:200_000]
    if len(text) < 120:
        raise ValueError("页面只有标题或极少文本，没有可核对的正文")
    if len(text) < 3000 and re.search(r"just a moment|verify (?:that )?you are human|checking your browser|access denied|captcha", text, re.I):
        raise ValueError("来源要求浏览器验证，未把验证页作为原文")
    return [{"locator": "网页正文", "text": text}] if text else []


def page_dates(raw: bytes, content_type: str) -> dict:
    """Read publisher-supplied date metadata without guessing from fetch time."""
    if "html" not in content_type and "xml" not in content_type:
        return {}
    html = raw[:500_000].decode("utf-8", errors="replace")
    values = {}
    patterns = {
        "published_at": r'''(?:article:published_time|datePublished|publish[_-]?date)["'\s:=]+(?:content["'\s:=]+)?([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}(?:[T\s][^"'< ]+)?)''',
        "updated_at": r'''(?:article:modified_time|dateModified|modified[_-]?date|last[_-]?updated)["'\s:=]+(?:content["'\s:=]+)?([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}(?:[T\s][^"'< ]+)?)''',
    }
    for name, pattern in patterns.items():
        match = re.search(pattern, html, re.I)
        if match:
            values[name] = re.sub(r"\s+", " ", match.group(1))[:80]
    return values


def relevant_windows(chunks: list[dict], terms: list[str], budget=6500) -> list[dict]:
    windows = []
    needles = [term.casefold() for term in terms if 1 < len(term) < 100]
    for chunk in chunks:
        text = chunk["text"]
        lower = text.casefold()
        positions = {0}
        for term in needles:
            start = 0
            for _ in range(6):
                found = lower.find(term, start)
                if found < 0:
                    break
                positions.add(max(0, found - 280))
                start = found + len(term)
        for position in positions:
            passage = text[position:position+1600]
            score = sum(min(passage.casefold().count(t), 4) for t in needles)
            windows.append((score, chunk["locator"], position, passage))
    chosen = []
    seen = set()
    for _, locator, position, passage in sorted(windows, key=lambda x: -x[0]):
        if any(loc == locator and abs(pos-position) < 1100 for loc, pos in seen):
            continue
        passage = passage[:budget]
        chosen.append({"locator": locator, "text": passage})
        seen.add((locator, position))
        budget -= len(passage)
        if budget < 200:
            break
    return chosen


async def read_source(source: dict, terms: list[str]) -> dict:
    result = {**source, "read_status": "unavailable", "read_error": None, "_chunks": []}
    original = source["url"]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=6), follow_redirects=False, trust_env=False) as client:
            url = original
            for _ in range(4):
                target, host = await public_target(url)
                headers = {"Host": host, "User-Agent": "RaceChipAI/0.4 evidence-reader", "Accept": "text/html,application/pdf,text/plain"}
                async with client.stream("GET", target, headers=headers, extensions={"sni_hostname": host}) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        if not response.headers.get("location"):
                            raise ValueError("来源跳转缺少地址")
                        url = urljoin(url, response.headers["location"])
                        continue
                    if response.status_code != 200:
                        raise ValueError(f"原文返回HTTP {response.status_code}")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 6_000_000:
                            raise ValueError("原文超过6MB读取上限")
                    content_type = response.headers.get("content-type", "")
                    raw = bytes(data)
                    chunks = await asyncio.to_thread(extract_document, raw, content_type, url)
                    if not chunks:
                        raise ValueError("没有可提取的正文，可能需要登录或只有图片")
                    selected = relevant_windows(chunks, terms)
                    result.update(read_status="read", final_url=url, _chunks=selected,
                                  read_scope="相关正文片段；PDF最多80页、文本最多20万字符，不代表整份文档完整审阅")
                    result.update(page_dates(raw, content_type))
                    return result
            raise ValueError("来源跳转次数超出上限")
    except ValueError as error:
        result["read_error"] = str(error)[:180]
    except Exception:
        result["read_error"] = "原文暂不可读或连接失败；仅保留搜索线索，不当作原文核实"
    return result
