
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_all

project = Path(SPECPATH).parent
model = Path(os.environ['OGE_RELEASE_MODEL'])
if not model.is_file():
    raise RuntimeError('Не найдена модель для автономной поставки')
datas = [(str(project / 'src' / 'oge_checker' / 'review.js'), 'oge_checker'),
         (str(project / 'src' / 'oge_checker' / 'ocr_profile.json'), 'oge_checker'),
         (str(model), 'oge_checker/models')]
for filename in ('digits_svm.xml','digits_neighbors.npz','numeric_model.json','form_anchors.npz','form_anchors.json'):
    numeric_path = project / 'src/oge_checker/models' / filename
    if not numeric_path.is_file():
        raise RuntimeError(f'Не найдена клеточная модель: {numeric_path}')
    datas.append((str(numeric_path),'oge_checker/models'))
binaries = []
hiddenimports = []
for package in ['rapidocr', 'onnxruntime', 'pymupdf', 'openpyxl']:
    package_data, package_binaries, package_imports = collect_all(package)


    datas += [item for item in package_data if package != 'rapidocr' or not item[0].endswith('.onnx')]
    binaries += package_binaries
    hiddenimports += package_imports

analysis = Analysis([str(project / 'scripts' / 'desktop_entry.py')], pathex=[str(project / "src")],
                    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
                    excludes=['pytest', 'matplotlib', 'pandas', 'torch', 'tensorflow'])
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='OGEChecker',
          console=False, debug=False, strip=False, upx=False)
collection = COLLECT(exe, analysis.binaries, analysis.datas, name='OGEChecker', strip=False, upx=False)
