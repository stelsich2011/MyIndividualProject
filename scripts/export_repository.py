import argparse
from pathlib import Path
import re
import zipfile


def main():
    root=Path(__file__).resolve().parent.parent
    parser=argparse.ArgumentParser(description='Создать публичный архив исходников без локальных датасетов и истории Git')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    version=re.search(r'^version\s*=\s*"([^"]+)"',(root/'pyproject.toml').read_text(encoding='utf-8'),re.MULTILINE)[1]
    destination=args.output or root/'dist/source'/f'oge-checker-{version}-source.zip'
    destination=destination.resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    files=[root/name for name in ('README.md','THIRD_PARTY.md','pyproject.toml','.gitignore','.gitattributes','.editorconfig','run_windows.bat','run_linux.sh','data/README.md')]
    allowed={'.py','.js','.json','.onnx','.xml','.npz','.md','.toml','.yml','.spec','.iss','.ps1','.txt','.csv','.xlsx','.png'}
    for directory in ('src','tests','scripts','packaging','examples','docs','.github'):
        files.extend(p for p in (root/directory).rglob('*') if p.is_file() and p.suffix in allowed and '__pycache__' not in p.parts and not any(part.endswith('.egg-info') for part in p.parts))
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            archive.write(path,path.relative_to(root).as_posix())
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert not any(name.startswith(('data/raw/','data/processed/','data/external/','.git/','.venv/')) for name in archive.namelist())
    print(destination)


if __name__=='__main__':
    main()
