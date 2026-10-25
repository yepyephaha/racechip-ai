"""One-line JSON stdin -> process environment. Never persist or echo credentials."""
import asyncio
import json
import os
import sys
import getpass
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
def main():
    print("Ready for credential JSON on stdin (input hidden).", flush=True)
    try:
        if not sys.stdin.isatty():
            raise ValueError("Interactive terminal required")
        incoming = json.loads(getpass.getpass("Credential input: "))
        for name in ("TENCENTCLOUD_WSA_APIKEY", "TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY", "TENCENTCLOUD_TOKEN", "SEARCHPRO_AUTH_MODE", "TOKENHUB_API_KEY", "TOKENHUB_MODEL", "TOKENHUB_REGION", "DECISION_PROVIDER"):
            if incoming.get(name):
                os.environ[name] = str(incoming[name]).strip()
        action = incoming.get("action", "probe")
        development_reload = bool(incoming.get("development_reload", False))
        incoming.clear()
    except Exception:
        print("Credential input could not be loaded; no values have been printed.", flush=True)
        raise SystemExit(1)
    from app.search import run_search
    from app.auth import auth_mode, redact
    if action == "probe":
        result = asyncio.run(run_search("live", ["OpenMV Cam RT1062 official I/O pins 3.3V tolerant"]))
        output = root / "artifacts" / "live"
        output.mkdir(exist_ok=True)
        (output / "probe.json").write_text(redact(json.dumps(result, ensure_ascii=False, indent=2)), encoding="utf-8")
        print(json.dumps({"status": result["status"], "auth_mode": auth_mode(), "request_count": result["request_count"],
                          "result_count": len(result["results"]), "request_ids": result["request_ids"], "error": result["error"]}, ensure_ascii=False), flush=True)
    elif action == "serve":
        import uvicorn
        print("Search credentials loaded into server process environment; no credential file written.", flush=True)
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning", reload=development_reload, reload_dirs=[str(root / "backend")] if development_reload else None)
    else:
        print("Unsupported runtime action.", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
