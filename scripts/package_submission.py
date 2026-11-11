"""Package the reviewable project without local secrets, caches, or dependencies."""
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'output/MedConnect_Final_Project.zip'


def main():
    required = [ROOT / 'output/pdf/MedConnect_Final_Submission.pdf', ROOT / 'docs/overleaf/main.tex',
                ROOT / 'schema.sql', ROOT / 'frontend/package-lock.json', ROOT / 'docs/verification.md']
    for path in required:
        if not path.is_file():
            raise SystemExit(f'Required submission artifact missing: {path.relative_to(ROOT)}')
    files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    paths = sorted(set(files.decode('utf-8').split('\0')) - {''})
    excluded = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'tmp', '.local', 'dist'}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(TARGET, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in paths:
            path = ROOT / name
            if (not path.is_file() or path == TARGET or any(part in excluded for part in path.parts)
                    or path.name == '.env' or path.suffix in {'.pyc', '.log'}):
                continue
            archive.write(path, 'MedConnect/' + name)
    with zipfile.ZipFile(TARGET) as archive:
        assert not any(name.endswith('/.env') or '/node_modules/' in name or '/__pycache__/' in name
                       for name in archive.namelist())
        print(f'Packaged {len(archive.namelist())} files into {TARGET.name}')


if __name__ == '__main__':
    main()
