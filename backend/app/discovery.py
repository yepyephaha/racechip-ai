"""Expose source-backed exact model matches without pretending a small local catalog is the web."""
import re


def normalized(value):
    return re.sub(r"[^\w]", "", value.casefold())


def aliases(query):
    result = [query.strip()]
    compact = re.sub(r"[\s_-]", "", query).upper()
    match = re.fullmatch(r"(ESP32)([SCPH][A-Z0-9]+)", compact)
    if match:
        variant = match[1]+"-"+match[2]
        if variant.casefold() != query.strip().casefold():
            result.append(variant)
    return result


def candidates(query, hits):
    compact = re.sub(r"[\s_-]", "", query)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{2,50}", compact) or not re.search(r"\d", compact):
        return []
    # Separators may differ; digits and letters may not. S31 is not silently changed to S3.
    pattern = re.compile(r"(?<![A-Za-z0-9])"+r"[\s_-]*".join(map(re.escape, compact))+r"(?![A-Za-z0-9])", re.I)
    found = {}
    for hit in hits:
        match = pattern.search(hit.get("title", "")) or pattern.search(hit.get("snippet", ""))
        if not match:
            continue
        name = match.group().strip()
        key = normalized(name)
        if key not in found:
            found[key] = {"name": name, "kind": "unconfirmed", "category": "custom", "source_url": hit["url"], "sources": [], "status": "source_text_match_not_spec_verified"}
        found[key]["sources"].append({"title": hit["title"], "url": hit["url"], "product_url": hit.get("product_url"), "platform": hit.get("platform")})
    return list(found.values())
