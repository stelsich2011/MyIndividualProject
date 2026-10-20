# Сборка выполняется отдельно на каждой целевой ОС.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

project = Path(SPECPATH).parent
datas = [(str(project / 'oge_checker' / 'review.js'), 'oge_checker')]
binaries = []
hiddenimports = []
for package in ['rapidocr', 'onnxruntime', 'pymupdf', 'openpyxl']:
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports

analysis = Analysis([str(project / 'desktop_entry.py')], pathex=[str(project)],
                    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
                    excludes=['pytest', 'matplotlib', 'pandas', 'torch', 'tensorflow'])
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='OGEChecker',
          console=False, debug=False, strip=False, upx=False)
collection = COLLECT(exe, analysis.binaries, analysis.datas, name='OGEChecker', strip=False, upx=False)
