"""Tencent Cloud TC3 request signing. Credentials are read only from process env."""
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone

API_KEY_ENDPOINT = "https://api.wsa.cloud.tencent.com/SearchPro"
TC3_ENDPOINT = "https://wsa.tencentcloudapi.com/"


def auth_mode() -> str | None:
    selected = os.environ.get("SEARCHPRO_AUTH_MODE", "auto").strip().lower()
    has_api_key = bool(os.environ.get("TENCENTCLOUD_WSA_APIKEY", "").strip())
    has_tc3 = all(os.environ.get(k, "").strip() for k in ("TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY"))
    if selected == "api_key":
        return "api_key" if has_api_key else None
    if selected == "tc3":
        return "tc3" if has_tc3 else None
    return "api_key" if has_api_key else "tc3" if has_tc3 else None


def build_request(query: str, timestamp: int | None = None, site: str | None = None) -> tuple[str, dict, bytes]:
    mode = auth_mode()
    if mode is None:
        raise ValueError("SearchPro credentials missing")
    params={"Query":query}
    if site: params["Site"]=site
    payload = json.dumps(params, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if mode == "api_key":
        return API_KEY_ENDPOINT, {"Authorization": "Bearer " + os.environ["TENCENTCLOUD_WSA_APIKEY"].strip(),
                                  "Content-Type": "application/json; charset=UTF-8"}, payload
    timestamp = int(time.time()) if timestamp is None else timestamp
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    content_type = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{content_type}\nhost:wsa.tencentcloudapi.com\nx-tc-action:searchpro\n"
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = "\n".join(["POST", "/", "", canonical_headers, signed_headers, hashlib.sha256(payload).hexdigest()])
    scope = date + "/wsa/tc3_request"
    string_to_sign = "\n".join(["TC3-HMAC-SHA256", str(timestamp), scope, hashlib.sha256(canonical_request.encode()).hexdigest()])
    def sign(key: bytes, value: str) -> bytes:
        return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()
    signing_key = sign(sign(sign(("TC3" + os.environ["TENCENTCLOUD_SECRET_KEY"].strip()).encode(), date), "wsa"), "tc3_request")
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = f"TC3-HMAC-SHA256 Credential={os.environ['TENCENTCLOUD_SECRET_ID'].strip()}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
    headers = {"Authorization": authorization, "Content-Type": content_type, "Host": "wsa.tencentcloudapi.com",
               "X-TC-Action": "SearchPro", "X-TC-Version": "2025-05-08", "X-TC-Timestamp": str(timestamp)}
    token = os.environ.get("TENCENTCLOUD_TOKEN", "").strip()
    if token:
        headers["X-TC-Token"] = token
    return TC3_ENDPOINT, headers, payload


def redact(value: str) -> str:
    for name in ("TENCENTCLOUD_WSA_APIKEY", "TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY", "TENCENTCLOUD_TOKEN", "HUNYUAN_API_KEY", "TOKENHUB_API_KEY"):
        secret = os.environ.get(name, "")
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value


def signed_cloud_request(host: str, service: str, action: str, version: str, body: dict, timestamp: int | None = None):
    """TC3 for a fixed caller-selected Tencent service; never chooses a host from model output."""
    if not all(os.environ.get(k, "").strip() for k in ("TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY")):
        raise ValueError("Cloud credentials missing")
    timestamp=int(time.time()) if timestamp is None else timestamp
    date=datetime.fromtimestamp(timestamp,timezone.utc).strftime("%Y-%m-%d")
    payload=json.dumps(body,ensure_ascii=False,separators=(",", ":")).encode("utf-8")
    content_type="application/json; charset=utf-8"
    signed="content-type;host;x-tc-action"
    canonical_headers=f"content-type:{content_type}\nhost:{host.lower()}\nx-tc-action:{action.lower()}\n"
    canonical="\n".join(["POST","/","",canonical_headers,signed,hashlib.sha256(payload).hexdigest()])
    scope=f"{date}/{service}/tc3_request"
    message="\n".join(["TC3-HMAC-SHA256",str(timestamp),scope,hashlib.sha256(canonical.encode()).hexdigest()])
    def sign(key,data): return hmac.new(key,data.encode(),hashlib.sha256).digest()
    key=sign(sign(sign(("TC3"+os.environ["TENCENTCLOUD_SECRET_KEY"].strip()).encode(),date),service),"tc3_request")
    signature=hmac.new(key,message.encode(),hashlib.sha256).hexdigest()
    headers={"Authorization":f"TC3-HMAC-SHA256 Credential={os.environ['TENCENTCLOUD_SECRET_ID'].strip()}/{scope}, SignedHeaders={signed}, Signature={signature}",
             "Content-Type":content_type,"Host":host,"X-TC-Action":action,"X-TC-Version":version,"X-TC-Timestamp":str(timestamp)}
    if os.environ.get("TENCENTCLOUD_TOKEN"): headers["X-TC-Token"]=os.environ["TENCENTCLOUD_TOKEN"]
    return "https://"+host+"/",headers,payload
