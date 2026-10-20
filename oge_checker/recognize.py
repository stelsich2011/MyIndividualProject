"""Локальное пробное OCR. Ни один результат автоматически не подтверждается."""

import argparse
import hashlib
import html
import json
import os
from pathlib import Path

import cv2
import numpy as np

from .corrections import apply_corrections
from .decimal_mark import restore_decimal


def normalize(text):
    # Сохраняем запятые, знаки и порядок. Не подменяем буквы похожими цифрами.
    return ''.join(text.split()).replace('−', '-')


def preprocess(image):
    """Убирает мелкие точки пунктира; сохраняет отдельный результат для контроля.

    Порог рассчитан на нормализованный холст 2000×2800 из этапа подготовки.
    Крупные запятые и минусы остаются. Мелкие знаки тоже могут пострадать,
    поэтому даже пустой результат требует проверки по оригиналу.
    """
    if image is None or image.size == 0:
        raise ValueError('Пустое изображение поля')
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    keep = np.ones(count, dtype=np.uint8)
    keep[0] = 0
    for index, (_, _, width, height, _) in enumerate(stats[1:], 1):
        if width <= 4 and height <= 5:
            keep[index] = 0
    cleaned = keep[labels] * 255
    points = cv2.findNonZero(cleaned)
    if points is None:
        return np.full((48, 48), 255, dtype=np.uint8), True
    x, y, width, height = cv2.boundingRect(points)
    cropped = 255 - cleaned[y:y + height, x:x + width]
    return cv2.copyMakeBorder(cropped, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255), False


class LocalOCR:
    def __init__(self):
        try:
            import rapidocr
            from rapidocr import RapidOCR, LangRec, OCRVersion, ModelType
        except ImportError:
            raise ValueError('Установите OCR: .venv/bin/python -m pip install -e ".[ocr]"') from None
        cache_base = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')
        model_root = Path(os.environ.get('OGE_MODEL_DIR') or cache_base / 'OGEChecker' / 'models')
        parameters = {
            'Rec.lang_type': LangRec.CYRILLIC,
            'Rec.ocr_version': OCRVersion.PPOCRV5,
            'Rec.model_type': ModelType.MOBILE,
            'Global.use_det': False, 'Global.use_cls': False,
            'Global.text_score': 0.0,
            'EngineConfig.onnxruntime.intra_op_num_threads': 2,
            'Global.model_root_dir': str(model_root),
        }
        bundled = Path(rapidocr.__file__).parent / 'models' / 'cyrillic_PP-OCRv5_rec_mobile.onnx'
        if bundled.is_file():
            parameters['Rec.model_path'] = str(bundled)
        self.engine = RapidOCR(params=parameters)

    def read(self, image):
        result = self.engine(image, use_det=False, use_cls=False)
        texts = result.txts or ()
        scores = result.scores or ()
        return ' '.join(texts), min(map(float, scores)) if scores else None


def relative(path, root):
    return Path(os.path.relpath(path, root)).as_posix()


def write_review(output, data):
    sections = []
    for page in data['pages']:
        number = page['page']
        if page['status'] != 'prepared':
            sections.append(f'<section><h2>Страница {number}</h2><p>Нужно проверить подготовку скана.</p></section>')
            continue
        rows = []
        for field in page['fields']:
            original = html.escape(field['original'], quote=True)
            cleaned = html.escape(field['cleaned'], quote=True)
            rows.append(f'<tr data-id="{field["id"]}"><th>{html.escape(field["label"])}</th>'
                        f'<td><a href="{original}"><img loading="lazy" src="{original}"></a>'
                        f'<details><summary>После удаления точек</summary><img loading="lazy" src="{cleaned}"></details></td>'
                        f'<td class="ocr"></td><td><input class="value" aria-label="Исправленный текст">'
                        f'<label><input type="checkbox" class="verified">Проверено</label></td></tr>')
        replacement = html.escape(page['replacements'], quote=True)
        sections.append(f'<section><h2>Страница {number}</h2><p><a href="{html.escape(page["original"], quote=True)}">Исходный скан</a></p>'
                        f'<table><thead><tr><th>Поле</th><th>Скан</th><th>Пробное OCR</th><th>Ручная проверка</th></tr></thead>'
                        f'<tbody>{"".join(rows)}</tbody></table>'
                        f'<h3>Замена ответов — проверяется отдельно</h3><a href="{replacement}"><img class="replacements" src="{replacement}"></a>'
                        '<p>Пока распознаётся основное поле ответа. Исправления из этого блока автоматически не применяются.</p></section>')
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    script = Path(__file__).with_name('review.js').read_text(encoding='utf-8')
    document = '''<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Проверка распознавания ОГЭ</title><style>
body{font:16px system-ui;margin:24px;background:#f3f5f7;color:#17212b}
section{background:white;padding:20px;margin:24px 0;border-radius:10px}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd3db;padding:10px;text-align:left}
td img{width:100%;max-width:640px;min-width:180px}td:nth-child(2){width:52%}
.replacements{max-width:100%}input.value{font:20px system-ui;width:180px}label{display:block}
button{padding:12px;font:inherit}header{position:sticky;top:0;background:#f3f5f7;padding:12px;border-bottom:1px solid #ccd3db}
.ocr{white-space:pre-wrap}tr:has(input.verified:checked){background:#edf9ef}
</style><h1>Ручная проверка пробного распознавания</h1>
<p>Автоматические кандидаты требуют проверки. Если ручные правки уже загружены, они отображаются с отметками «Проверено».
Уверенность модели не означает вероятность правильного ответа.
Пустой результат тоже может быть ошибкой OCR. Баллы не выставляются.</p>
<p>Исправьте текст по исходному фрагменту и отметьте «Проверено».
Правки сохраняются только после нажатия «Скачать правки JSON». При закрытии вкладки несохранённые правки теряются.</p>
<header><button id="download">Скачать правки JSON</button> <label>Загрузить сохранённые правки: <input id="import" type="file" accept=".json"></label>
<span id="progress"></span></header>'''
    (output / 'review.html').write_text(document + ''.join(sections) +
        f'<script id="data" type="application/json">{payload}</script><script>{script}</script></html>', encoding='utf-8')


def recognize(prepared, output, engine=None, corrections=None, restore_decimals=True):
    prepared, output = prepared.resolve(), output.resolve()
    manifest_path = prepared / 'manifest.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get('template') != 'oge_math_form1_v1':
        raise ValueError('Препроцессор настроен на шаблон oge_math_form1_v1')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Папка OCR должна быть пустой; укажите новую --output')
    engine = engine or LocalOCR()
    output.mkdir(parents=True, exist_ok=True)
    data = {'schema_version': 1, 'source_id': hashlib.sha256(manifest_bytes).hexdigest(),
            'source_manifest': str(manifest_path), 'engine': 'RapidOCR 3.10.0 / cyrillic PP-OCRv5 mobile',
            'postprocessing': 'decimal_mark_geometry_v1' if restore_decimals else 'none',
            'run_status': 'running', 'pages': []}
    for page in manifest['pages']:
        number = page['page']
        result = {'page': number, 'status': page['status'], 'fields': []}
        if page['status'] == 'prepared':
            folder = output / f'page_{number:03}'
            folder.mkdir()
            result['original'] = relative(prepared / page['original'], output)
            result['replacements'] = relative(prepared / page['fields']['replacements']['image'], output)
            for name, field in page['fields'].items():
                if name not in ('surname', 'first_name', 'patronymic', 'class') and not name.startswith('answer_'):
                    continue
                original = prepared / field['image']
                image = cv2.imread(str(original))
                cleaned, empty = preprocess(image)
                cleaned_path = folder / f'{name}.png'
                if not cv2.imwrite(str(cleaned_path), cleaned):
                    raise OSError(f'Не удалось записать {cleaned_path}')
                raw, confidence = ('', None) if empty else engine.read(cleaned)
                value = normalize(raw)
                base_candidate = value
                adjustments = []
                if restore_decimals and name.startswith('answer_'):
                    value, adjustments = restore_decimal(value, cleaned)
                result['fields'].append({
                    'id': f'{number}:{name}', 'name': name,
                    'label': f'Ответ {int(name[7:])}' if name.startswith('answer_') else
                             {'surname': 'Фамилия', 'first_name': 'Имя', 'patronymic': 'Отчество', 'class': 'Класс'}[name],
                    'original': relative(original, output), 'cleaned': relative(cleaned_path, output),
                    'raw_text': raw, 'candidate': value, 'confidence': confidence,
                    'base_candidate': base_candidate, 'adjustments': adjustments,
                    'status': 'empty_candidate' if empty else 'needs_review',
                    'reviewed': False, 'corrected_text': None,
                })
        data['pages'].append(result)
        (output / 'recognition.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Пробное OCR страницы {number} завершено', flush=True)
    data['run_status'] = 'complete'
    if corrections is not None:
        data = apply_corrections(data, corrections)
    (output / 'recognition.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    write_review(output, data)
    return data


def main():
    parser = argparse.ArgumentParser(description='Пробное локальное OCR подготовленных полей')
    parser.add_argument('prepared', type=Path, help='Папка с manifest.json')
    parser.add_argument('--output', type=Path, default=Path('output/recognition'))
    parser.add_argument('--corrections', type=Path, help='Перенести ручную проверку из JSON этого же набора страниц')
    parser.add_argument('--no-restore-decimals', action='store_true', help='Отключить восстановление запятой по изображению')
    args = parser.parse_args()
    try:
        corrections = json.loads(args.corrections.read_text(encoding='utf-8')) if args.corrections else None
        recognize(args.prepared, args.output, corrections=corrections,
                  restore_decimals=not args.no_restore_decimals)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')
    print(f'Откройте {args.output / "review.html"}')


if __name__ == '__main__':
    main()
