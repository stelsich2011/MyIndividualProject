import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description='Воспроизводимая сборка: python packaging/build_windows.py --iscc PATH.')
    parser.add_argument('--iscc', type=Path, default=Path('build_tools/InnoSetup/ISCC.exe'))
    args = parser.parse_args()
    if sys.platform != 'win32' or sys.maxsize < 2**32:
        parser.error('Для сборки нужен Windows и 64-битный Python')
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    sys.path.insert(0, str(root / "src"))
    from oge_checker.recognize import LocalOCR
    import rapidocr
    profile = json.loads((root / 'src/oge_checker/ocr_profile.json').read_text(encoding='utf-8'))
    if profile['profile'] != 'v5':
        parser.error('Список моделей поставки нужно обновить для выбранного профиля')
    LocalOCR('v5')  
    filename = 'cyrillic_PP-OCRv5_rec_mobile.onnx'
    cache = Path(os.environ.get('OGE_MODEL_DIR') or Path(os.environ['LOCALAPPDATA']) / 'OGEChecker/models')
    choices = [root / 'src/oge_checker/models' / filename, Path(rapidocr.__file__).parent / 'models' / filename, cache / filename]
    model = next((p for p in choices if p.is_file()), None)
    if model is None:
        raise RuntimeError('Модель не найдена; автономная сборка невозможна')
    compiler = args.iscc.resolve()
    if not compiler.is_file():
        raise RuntimeError(f'Установите Inno Setup и передайте --iscc: {compiler}')
    numeric_metadata = json.loads((root/'src/oge_checker/models/numeric_model.json').read_text(encoding='utf-8'))
    alignment_metadata=json.loads((root/'src/oge_checker/models/form_anchors.json').read_text(encoding='utf-8'))
    if hashlib.sha256((root/'src/oge_checker/models/form_anchors.npz').read_bytes()).hexdigest()!=alignment_metadata['sha256']:
        raise RuntimeError('Контрольная сумма печатного шаблона не совпадает')
    for numeric_name, expected in numeric_metadata['files'].items():
        if hashlib.sha256((root/'src/oge_checker/models'/numeric_name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Контрольная сумма клеточной модели не совпадает: {numeric_name}')
    environment = dict(os.environ, OGE_RELEASE_MODEL=str(model))
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', 'dist/windows',
                    '--workpath', 'build/windows', 'packaging/OGEChecker.spec'], env=environment, check=True)
    subprocess.run([str(compiler), 'packaging/OGEChecker.iss'], check=True)
    import importlib.metadata
    manifest = {'version': '0.6.0', 'python': sys.version, 'platform': platform.platform(), 'numeric_model':numeric_metadata,
        'alignment_reference':alignment_metadata,
        'model': filename, 'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(), 'ocr_profile': profile,
        'dependencies': {p: importlib.metadata.version(p) for p in ['rapidocr', 'onnxruntime', 'opencv-python-headless', 'PyMuPDF', 'numpy', 'Pillow', 'openpyxl', 'pyinstaller']}}
    (root / 'dist/installer/build_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (root / 'packaging/requirements-windows.lock.txt').write_text('\n'.join(f'{p}=={v}' for p, v in manifest['dependencies'].items()) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
