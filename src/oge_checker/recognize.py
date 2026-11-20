
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
from .geometry import restore_strokes
from .image_io import read_image, write_image


def normalize(text):

    return ''.join(text.split()).replace('−', '-')


def preprocess(image):
    pass
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
    def __init__(self, profile=None, numeric=None):
        try:
            import rapidocr
            from rapidocr import RapidOCR, LangRec, OCRVersion, ModelType
        except ImportError:
            raise ValueError('Установите OCR: .venv/bin/python -m pip install -e ".[ocr]"') from None
        cache_base = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')
        model_root = Path(os.environ.get('OGE_MODEL_DIR') or cache_base / 'OGEChecker' / 'models')
        configuration = json.loads(Path(__file__).with_name('ocr_profile.json').read_text(encoding='utf-8'))
        self.profile = profile or configuration['profile']
        filename = 'cyrillic_PP-OCRv5_rec_mobile.onnx' if self.profile == 'v5' else 'PP-OCRv6_rec_small.onnx'
        parameters = {
            'Rec.lang_type': LangRec.CYRILLIC,
            'Rec.ocr_version': OCRVersion.PPOCRV5 if self.profile == 'v5' else OCRVersion.PPOCRV6,
            'Rec.model_type': ModelType.MOBILE if self.profile == 'v5' else ModelType.SMALL,
            'Global.use_det': False, 'Global.use_cls': False,
            'Global.text_score': 0.0,
            'EngineConfig.onnxruntime.intra_op_num_threads': 2,
            'Global.model_root_dir': str(model_root),
        }
        bundled = Path(__file__).with_name('models') / filename
        if not bundled.is_file():
            bundled = Path(rapidocr.__file__).parent / 'models' / filename
        if not bundled.is_file() and (model_root / filename).is_file():
            bundled = model_root / filename
        if bundled.is_file():
            parameters['Rec.model_path'] = str(bundled)
        self.model_path = str(bundled) if bundled.is_file() else None
        self.engine = RapidOCR(params=parameters)
        self.numeric = None
        if self.profile=='v5' and (configuration.get('numeric',False) if numeric is None else numeric):
            from .digits import NumericOCR
            self.numeric=NumericOCR()

    def read(self, image):
        result = self.engine(image, use_det=False, use_cls=False)
        texts = result.txts or ()
        scores = result.scores or ()
        return ' '.join(texts), min(map(float, scores)) if scores else None


def recognize_replacements(image, engine, row_bounds=None):
    pass
    from .replacements import recognize_block
    return recognize_block(image, engine, preprocess, normalize, row_bounds=row_bounds)


def relative(path, root):
    return Path(os.path.relpath(path, root)).as_posix()


def write_review(output, data):
    sections = []
    for page in data['pages']:
        number = page['page']
        if page['status'] != 'prepared':
            sections.append(f'<section><h2>Страница {number}</h2><p>{html.escape(page.get("error", "Нужно проверить подготовку скана."))}</p>'
                            f'<a href="{html.escape(page.get("original", ""), quote=True)}">Исходный скан</a></section>')
            continue
        rows = []
        for field in page['fields']:
            original = html.escape(field['original'], quote=True)
            cleaned = html.escape(field['cleaned'], quote=True)
            rows.append(f'<tr data-id="{field["id"]}"><th>{html.escape(field["label"])}</th>'
                        f'<td><a href="{original}"><img loading="lazy" src="{original}"></a>'
                        f'<details><summary>После удаления точек</summary><img loading="lazy" src="{cleaned}"></details></td>'
                        f'<td class="ocr"></td><td><input class="value" aria-label="Исправленный текст"></td></tr>')
        replacement = html.escape(page['replacements'], quote=True)
        sections.append(f'<section><h2>Страница {number}</h2><p><a href="{html.escape(page["original"], quote=True)}">Исходный скан</a></p>'
                        f'<table><thead><tr><th>Поле</th><th>Скан</th><th>Пробное OCR</th><th>Ручная проверка</th></tr></thead>'
                        f'<tbody>{"".join(rows)}</tbody></table>'
                        f'<h3>Блок замены ответов</h3><a href="{replacement}"><img class="replacements" src="{replacement}"></a>'
                        '<p>Результат автоматического чтения замен и конфликты доступны в desktop-приложении.</p></section>')
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
</style><h1>Распознанные ответы</h1>
<p>Распознанные ответы используются автоматически. Исправления добровольны.
Уверенность модели не означает вероятность правильного ответа.
Пустой результат тоже может быть ошибкой OCR. Баллы доступны в desktop-приложении.</p>
<p>При необходимости исправьте текст по исходному фрагменту.
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
            'source_manifest': str(manifest_path), 'engine': f'RapidOCR / {getattr(engine, "profile", "custom")}',
            'postprocessing': ('visible_strokes_v1+decimal_geometry_v2' if restore_decimals else 'none') + ('+cell_classifier_v1' if getattr(engine,'numeric',None) is not None else ''),
            'numeric_model': 'oge_digits_hog_svm_v1' if getattr(engine,'numeric',None) is not None else None,
            'run_status': 'running', 'pages': []}
    for page in manifest['pages']:
        number = page['page']
        result = {'page': number, 'status': page['status'], 'fields': [], 'field_alignment':page.get('field_alignment'),
                  'alignment':page.get('alignment')}
        if page.get('original'):
            result['original']=relative(prepared / page['original'], output)
        if page.get('error'):
            result['error']=page['error']
        if page['status'] == 'prepared':
            folder = output / f'page_{number:03}'
            folder.mkdir()
            result['original'] = relative(prepared / page['original'], output)
            result['replacements'] = relative(prepared / page['fields']['replacements']['image'], output)
            block = read_image(prepared / page['fields']['replacements']['image'])
            row_bounds=(page.get('field_alignment') or {}).get('replacement_rows')
            if row_bounds == []:
                result['automatic_replacements'], result['replacement_warnings'], result['replacement_entries'] = {}, ['Не удалось выделить строки блока замен'], []
            else:
                result['automatic_replacements'], result['replacement_warnings'], result['replacement_entries'] = recognize_replacements(block, engine, row_bounds)
            for name, field in page['fields'].items():
                if name not in ('surname', 'first_name', 'patronymic', 'class') and not name.startswith('answer_'):
                    continue
                original = prepared / field['image']
                image = read_image(original)
                grid_removed = 0
                stretched = False
                if name.startswith('answer_') and (page.get('alignment') or {}).get('method') in ('adaptive_markers','printed_affine'):
                    from .grid import clean_recovered_grid
                    image, grid_removed = clean_recovered_grid(image)
                    if image.shape[0]>75:
                        stretched=True
                        image=cv2.resize(image,(image.shape[1],62),interpolation=cv2.INTER_AREA)
                cleaned, empty = preprocess(image)
                cleaned_path = folder / f'{name}.png'
                write_image(cleaned_path, cleaned)
                ocr_error = None
                try:
                    raw, confidence = ('', None) if empty else engine.read(cleaned)
                    if not empty and not normalize(raw):
                        ocr_error = 'Текст на изображении есть, но OCR не вернул символов'
                except Exception as exc:
                    raw, confidence, ocr_error = '', None, str(exc)
                value = normalize(raw)
                base_candidate = value
                adjustments = []
                numeric_result = None
                field_warnings = []
                personal_result = None
                if not empty and not ocr_error and name in ('surname','first_name','patronymic','class'):
                    from .personal import name_candidate, read_class, valid_class
                    try:
                        if name == 'class':
                            improved, readings = read_class(value, cleaned, engine.read)
                            personal_result = {'readings': readings}
                            if not valid_class(improved):
                                field_warnings.append('Не удалось уверенно прочитать номер и букву класса')
                        else:
                            improved, lexical = name_candidate(value, name, confidence)
                            personal_result = {'language_hint': lexical}
                            if lexical:
                                field_warnings.append('Имя уточнено по словарю и похожим буквам; исходное OCR сохранено')


                        if stretched and improved != value:
                            field_warnings.append('Растянутая строка: использовано последовательное OCR')
                            improved=value
                        if improved != value:
                            adjustments.append({'rule':'personal_context_v1','before':value,'after':improved})
                            value = improved
                    except Exception as exc:
                        field_warnings.append(f'Уточнение ФИО/класса недоступно: {exc}')
                if restore_decimals and name.startswith('answer_'):
                    value, adjustments = restore_strokes(value, cleaned)
                    value, decimal_adjustments = restore_decimal(value, cleaned)
                    adjustments += decimal_adjustments
                sequence_candidate = value
                text_readings = []
                if not empty and not ocr_error and name.startswith('answer_'):
                    from .text_answers import refine_text
                    try:
                        improved,text_readings=refine_text(value,cleaned,engine.read)
                        if improved!=value:
                            adjustments.append({'rule':'text_consensus_v1','before':value,'after':improved})
                            value=improved
                    except Exception as exc:
                        field_warnings.append(f'Повторное чтение текста недоступно: {exc}')
                if not empty and getattr(engine,'numeric',None) is not None and name.startswith('answer_'):
                    from .digits import combine_numeric
                    try:
                        numeric_result = engine.numeric.read(image)
                        if numeric_result['candidate'] != value:
                            field_warnings.append('Модели OCR расходятся')
                        improved = combine_numeric(value,numeric_result['candidate'],numeric_result['agreements'],numeric_result['distances'],allow_separator_deletion=numeric_result.get('allow_separator_deletion',False),boxes=numeric_result.get('boxes'),small_separators=numeric_result.get('small_separators'))
                        if improved != value:
                            adjustments.append({'rule':'cell_classifier_v1','before':value,'after':improved})
                            value = improved
                            ocr_error = None
                    except Exception as exc:
                        field_warnings.append(f'Клеточный OCR недоступен для поля: {exc}')
                result['fields'].append({
                    'id': f'{number}:{name}', 'name': name,
                    'label': f'Ответ {int(name[7:])}' if name.startswith('answer_') else
                             {'surname': 'Фамилия', 'first_name': 'Имя', 'patronymic': 'Отчество', 'class': 'Класс'}[name],
                    'original': relative(original, output), 'cleaned': relative(cleaned_path, output),
                    'raw_text': raw, 'candidate': value, 'confidence': confidence,
                    'base_candidate': base_candidate, 'adjustments': adjustments,
                    'sequence_candidate':sequence_candidate,'numeric_result':numeric_result,
                    'personal_result': personal_result,
                    'text_readings': text_readings,
                    'grid_components_removed': grid_removed,
                    'status': 'ocr_error' if ocr_error else ('empty_candidate' if empty else 'recognized'),
                    'warnings': ([f'Ошибка OCR: {ocr_error}'] if ocr_error else []) + field_warnings,
                    'reviewed': False, 'corrected_text': None,
                })
        data['pages'].append(result)
        (output / 'recognition.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Пробное OCR страницы {number} завершено', flush=True)
    data['run_status'] = 'complete'
    data['processing_summary']={'pages':len(data['pages']),
        'prepared':sum(p['status']=='prepared' for p in data['pages']),
        'failed_pages':[p['page'] for p in data['pages'] if p['status']!='prepared']}
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
    parser.add_argument('--profile', choices=['v5', 'v6'], help='Модель для сравнительной оценки')
    parser.add_argument('--no-numeric', action='store_true', help='Отключить клеточный классификатор для сравнительной оценки')
    args = parser.parse_args()
    try:
        corrections = json.loads(args.corrections.read_text(encoding='utf-8')) if args.corrections else None
        recognize(args.prepared, args.output, engine=LocalOCR(args.profile,numeric=False if args.no_numeric else None), corrections=corrections,
                  restore_decimals=not args.no_restore_decimals)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')
    print(f'Откройте {args.output / "review.html"}')


if __name__ == '__main__':
    main()
