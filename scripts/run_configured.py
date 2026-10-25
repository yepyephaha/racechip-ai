"""Load a user-selected local CSV source into the server process, never into exports."""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source_config_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".config")
    project_id = hashlib.sha256(str(ROOT.resolve()).casefold().encode()).hexdigest()[:16]
    return base / "RaceChipAI" / project_id / "search-source.json"


def csv_credentials(path: Path) -> dict[str, str]:
    """Accept one complete Tencent Cloud pair; error messages never include input."""
    try:
        raw = path.read_bytes()
        if len(raw) > 65536:
            raise ValueError
        content = None
        for encoding in ("utf-8-sig", "utf-16", "gb18030"):
            try:
                candidate = raw.decode(encoding)
                if "\x00" not in candidate:
                    content = candidate
                    break
            except UnicodeError:
                pass
        if content is None:
            raise ValueError
        rows = list(csv.DictReader(io.StringIO(content)))
        if len(rows) != 1:
            raise ValueError
        values = {str(k).strip().casefold().replace("_", "").replace(" ", ""): str(v or "").strip()
                  for k, v in rows[0].items() if k is not None}
        identifier = values.get("secretid", "")
        secret = values.get("secretkey", "")
        if not identifier or not secret or any(c in identifier + secret for c in "\r\n\x00"):
            raise ValueError
        if max(len(identifier), len(secret)) > 4096:
            raise ValueError
        return {"TENCENTCLOUD_SECRET_ID": identifier,
                "TENCENTCLOUD_SECRET_KEY": secret, "SEARCHPRO_AUTH_MODE": "tc3"}
    except Exception:
        raise ValueError("搜索凭据CSV无法读取，或缺少唯一一组完整的SecretId/SecretKey。输入值未显示。") from None


def register_source(path: Path) -> None:
    csv_credentials(path)  # Validate before saving a reference. No credential values are saved.
    config = source_config_path()
    config.parent.mkdir(parents=True, exist_ok=True)
    temporary = config.with_suffix(".tmp")
    temporary.write_text(json.dumps({"source_path": str(path.resolve())}), encoding="utf-8")
    os.replace(temporary, config)


def load_search_source() -> bool:
    # An explicit invoking-shell credential setting owns the configuration.
    env_names = ("TENCENTCLOUD_WSA_APIKEY", "TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY")
    if any(os.environ.get(name, "").strip() for name in env_names):
        return False
    config = source_config_path()
    if not config.is_file():
        return False
    try:
        source = Path(json.loads(config.read_text(encoding="utf-8"))["source_path"])
        credentials = csv_credentials(source)
    except Exception:
        raise ValueError("已保存的本机搜索凭据来源不可用，请检查原CSV文件是否仍在原位置。密钥未显示。") from None
    os.environ.update(credentials)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--search-credentials-file", type=Path)
    args = parser.parse_args()
    try:
        if args.search_credentials_file:
            register_source(args.search_credentials_file)
        restored = load_search_source()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
    if restored:
        print("SearchPro TC3 credentials loaded from the registered local CSV; values are not displayed.", flush=True)
    sys.path.insert(0, str(ROOT / "backend"))
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
