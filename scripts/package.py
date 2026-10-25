"""Build a local reviewable source package from an explicit allowlist. No secrets/runtime."""
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
target = root / "artifacts" / "RaceChip-AI-P0-Windows.zip"
files = []
for name in ("README.md", "PRODUCT.md", "DESIGN.md", ".env.example", ".gitignore", "pytest.ini", "Dockerfile", ".dockerignore"):
    files.append(root / name)
for folder in ("backend", "frontend", "data", "docs", "scripts"):
    for path in (root / folder).rglob("*"):
        relative_parts = path.relative_to(root / folder).parts
        if path.is_file() and not any(part in {"node_modules", "__pycache__", ".pytest_cache", ".git"} for part in relative_parts):
            if path.name.startswith(".env") or path.suffix in {".pyc", ".tsbuildinfo", ".log"}:
                continue
            files.append(path)
for name in ("verification.json", "mock-ui-export.md", "mock-ui-export.json", "mock-workbench.png", "live-missing-key.png", "official-source-index.json"):
    path = root / "artifacts" / name
    if path.is_file():
        files.append(path)
files.extend(p for p in (root / "artifacts").glob("official-*") if p.is_file())
for folder in ("live", "submission", "novice", "continuation", "visual", "evidence", "workflow"):
    files.extend(p for p in (root / "artifacts" / folder).rglob("*") if p.is_file())
with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        archive.write(path, "racechip-ai/" + path.relative_to(root).as_posix())
digest = hashlib.sha256(target.read_bytes()).hexdigest()
live_manifest_path = root / "artifacts" / "live" / "manifest.json"
live_manifest = json.loads(live_manifest_path.read_text(encoding="utf-8")) if live_manifest_path.is_file() else {}
probe_path = root / "artifacts" / "live" / "probe.json"
probe_count = json.loads(probe_path.read_text(encoding="utf-8")).get("request_count", 0) if probe_path.is_file() else 0
manifest = {"file": target.name, "sha256": digest, "file_count": len(set(files)), "bytes": target.stat().st_size,
            "contains": "source, built frontend, docs, offline QA artifacts; no keys or dependencies",
            "historical_v0_2_case_search_calls": live_manifest.get("new_request_count", 0),
            "historical_v0_2_case_and_probe_search_calls": live_manifest.get("new_request_count", 0) + probe_count,
            "historical_v0_2_investigation_cases": live_manifest.get("successful_question_count", 0),
            "submission_status": "not_submitted",
            "count_scope": "Counts describe the included saved records, not account billing or all interrupted test attempts."}
novice_path = root / "artifacts" / "novice" / "session.json"
if novice_path.is_file():
    novice = json.loads(novice_path.read_text(encoding="utf-8"))
    manifest['novice_demo'] = {'user_inputs': 'explicit_synthetic_fixture',
                              'model_turns': len(novice.get('rounds', [])),
                              'sourcing_status': (novice.get('procurement') or {}).get('status'),
                              'saved_procurement_query_requests': (novice.get('procurement') or {}).get('search_request_count', 0),
                              'sku_verified': False, 'hardware_tested': False}
(root / "artifacts" / "package-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False, indent=2))
