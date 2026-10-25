"""Package Git-tracked source and the built UI, without local credentials or dependencies."""
import json
import re
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'artifacts' / 'releases' / 'RaceChip-AI-Windows.zip'


def main():
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    files = {ROOT / name for name in tracked if name}
    built = ROOT / 'frontend' / 'dist'
    if not (built / 'index.html').is_file():
        raise SystemExit('Build the frontend before packaging.')
    files.update(path for path in built.rglob('*') if path.is_file())
    prohibited_parts = {'.git', '.venv', 'node_modules', 'runtime', '__pycache__', '.pytest_cache'}
    secret_pattern = re.compile(
        rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'
        rb'|\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b'
        rb'|\b(?:AKID[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{20,})\b'
    )
    for path in sorted(files):
        relative = path.relative_to(ROOT)
        filename = path.name.casefold()
        if (any(part in prohibited_parts for part in relative.parts)
                or (filename.startswith('.env') and filename != '.env.example')
                or filename.startswith(('secretkey', 'credentials'))
                or path.suffix.casefold() in {'.pem', '.p12', '.pfx', '.key', '.log'}):
            raise SystemExit(f'Private file blocked: {relative.as_posix()}')
        if secret_pattern.search(path.read_bytes()):
            raise SystemExit(f'Potential credential blocked: {relative.as_posix()}')
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(TARGET, 'w', compression=ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, 'racechip-ai/' + path.relative_to(ROOT).as_posix())
    print(json.dumps({'file': str(TARGET), 'files': len(files), 'bytes': TARGET.stat().st_size}))


if __name__ == '__main__':
    main()
