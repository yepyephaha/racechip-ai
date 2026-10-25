"""Package Git-tracked source and the built UI, without local credentials or dependencies."""
import argparse
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'artifacts' / 'releases' / 'RaceChip-AI-Windows.zip'

LOCAL_DOCUMENTS = {
    'docs/submission-kit.md', 'docs/codex-prompt-v2.md',
    'docs/competition-p0-plan-v2.md', 'docs/competitive-audit-2026-10-24.md',
    'docs/competitive-research-2026-10-24.md', 'docs/development-plan.md',
    'docs/official-verification.md', 'docs/delivery.md', 'docs/continuation-qa.md',
}
PROHIBITED_PARTS = {'.git', '.venv', 'node_modules', 'runtime', '__pycache__', '.pytest_cache', '.taste-skill', '.workbuddy'}
SECRET_PATTERN = re.compile(
    rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'
    rb'|\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b'
    rb'|\b(?:AKID[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{20,})\b'
)


def local_only(name):
    return name in LOCAL_DOCUMENTS or name.startswith('social/')


def inspect_payload(name, data, depth=0):
    relative = PurePosixPath(name)
    filename = relative.name.casefold()
    if (any(part.casefold() in PROHIBITED_PARTS for part in relative.parts)
            or (filename.startswith('.env') and filename != '.env.example')
            or filename.startswith(('secretkey', 'credentials'))
            or relative.suffix.casefold() in {'.pem', '.p12', '.pfx', '.key', '.log'}):
        raise SystemExit(f'Private file blocked: {name}')
    if SECRET_PATTERN.search(data):
        raise SystemExit(f'Potential credential blocked: {name}')
    if filename == '.env.example':
        for line in data.decode('utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                field, value = line.split('=', 1)
                if re.search(r'API_?KEY|SECRET|TOKEN$', field, re.I) and value.strip():
                    raise SystemExit('Secret template fields must be blank.')
    if relative.suffix.casefold() == '.zip':
        if depth >= 3:
            raise SystemExit(f'Nested archive depth exceeded: {name}')
        with ZipFile(io.BytesIO(data)) as nested:
            for entry in nested.infolist():
                if not entry.is_dir():
                    inspect_payload(entry.filename, nested.read(entry), depth + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', help='Package this committed Git snapshot instead of the working tree.')
    args = parser.parse_args()
    if args.ref:
        snapshot = subprocess.check_output(['git', 'archive', '--format=zip', args.ref], cwd=ROOT)
        with ZipFile(io.BytesIO(snapshot)) as archive:
            payloads = {entry.filename: archive.read(entry) for entry in archive.infolist() if not entry.is_dir()}
    else:
        names = subprocess.check_output(
            ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT
        ).decode('utf-8').split('\0')
        payloads = {name: (ROOT / name).read_bytes() for name in names if name and (ROOT / name).is_file()}
    built = ROOT / 'frontend' / 'dist'
    if not (built / 'index.html').is_file():
        raise SystemExit('Build the frontend before packaging.')
    payloads.update({path.relative_to(ROOT).as_posix(): path.read_bytes() for path in built.rglob('*') if path.is_file()})
    payloads = {name: data for name, data in payloads.items() if not local_only(name)}
    for name, data in sorted(payloads.items()):
        inspect_payload(name, data)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(TARGET, 'w', compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(payloads.items()):
            archive.writestr('racechip-ai/' + name, data)
    print(json.dumps({'file': str(TARGET), 'files': len(payloads), 'bytes': TARGET.stat().st_size,
                      'source_ref': args.ref or 'worktree', 'sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
