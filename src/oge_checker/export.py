
import argparse
import json
from pathlib import Path

from .corrections import apply_corrections
from .evaluate import evaluate
from .recognize import relative, write_review
from .answers import effective_answer, field_value


def text_cell(sheet, row, column, value):
    cell = sheet.cell(row, column, value)
    if isinstance(value, str):

        cell.data_type = 's'
        cell.number_format = '@'
    return cell


def add_row(sheet, values):
    row = sheet.max_row + 1 if sheet.max_row > 1 or sheet.cell(1, 1).value is not None else 1
    for column, value in enumerate(values, 1):
        text_cell(sheet, row, column, value)


def workbook(data, metrics, destination):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise ValueError('Установите экспорт: .venv/bin/python -m pip install -e ".[export]"') from None
    book = Workbook()
    students = book.active
    students.title = 'Ученики'
    details = book.create_sheet('Поля')
    errors = book.create_sheet('Ошибки OCR')
    replacements = book.create_sheet('Проверка замен')
    info = book.create_sheet('Сведения')
    add_row(students, ['Страница', 'Фамилия', 'Имя', 'Отчество', 'Класс'] +
            [f'Ответ {number}' for number in range(1, 20)] +
            ['Ручных отметок из старых данных', 'Всего полей', 'Статус расшифровки', 'Блок замены', 'Вариант', 'Баллы', 'Статус оценивания', 'Исходный скан',
             'Предварительный балл', 'Максимум', 'Демонстрационные ключи', 'Причина пропуска', 'Способ выравнивания'])
    add_row(details, ['Страница', 'Поле', 'Текст OCR', 'Кандидат', 'Используемое значение',
                      'Ручная отметка из старых данных', 'Уверенность OCR', 'Изменено правилом', 'Фрагмент скана'])
    add_row(errors, ['Поле', 'Кандидат OCR', 'Ручная расшифровка'])
    add_row(replacements, ['Страница', 'Изображение блока', 'Статус', 'Применённые замены'])
    add_row(info, ['Параметр', 'Значение'])
    scores = book.create_sheet('Проверка ответов')
    add_row(scores, ['Страница', 'Вариант', 'Задание', 'Ответ', 'Источник ответа', 'Ключ', 'Балл', 'Максимум', 'Результат', 'ДЕМО', 'Предупреждения'])
    for page in data['pages']:
        by_name = {field['name']: field for field in page['fields']}
        def confirmed(name):
            if name.startswith('answer_'):
                return effective_answer(page, int(name[7:]))[0]
            return field_value(by_name.get(name))
        reviewed = sum(field['reviewed'] for field in page['fields'])
        complete = len(by_name) == 23 and page['status'] == 'prepared'
        grading = page.get('grading', {})
        replacement_status = '; '.join(page.get('replacement_warnings', [])) or 'Автоматически / ручные правки'
        add_row(students, [page['page']] + [confirmed(name) for name in
                ['surname', 'first_name', 'patronymic', 'class']] +
                [confirmed(f'answer_{number:02}') for number in range(1, 20)] +
                [reviewed, len(by_name), 'Обработана автоматически' if complete else 'Ошибка подготовки',
                 replacement_status, grading.get('variant'), grading.get('total'),
                 grading.get('status', 'Не выполнено: нужны ключи, варианты и проверка замен'), page.get('original'),
                 grading.get('provisional'), grading.get('maximum'), 'Да' if grading.get('demo') else 'Нет',
                 page.get('error'),(page.get('alignment') or {}).get('method')])
        add_row(replacements, [page['page'], page.get('replacements'), replacement_status,
                              json.dumps({'manual': page.get('replacement_answers', {}), 'ocr': page.get('automatic_replacements', {})}, ensure_ascii=False)])
        for task in grading.get('tasks', []):
            add_row(scores, [page['page'], grading['variant'], task['number'], task['answer'], task['source'],
                             ' / '.join(task['accepted']), task['points'], task['maximum'], task['status'],
                             'Да' if grading['demo'] else 'Нет', '; '.join(task.get('warnings', []))])
        for field in page['fields']:
            add_row(details, [page['page'], field['label'], field['raw_text'], field['candidate'],
                              field_value(field),
                              'Да' if field['reviewed'] else 'Нет', field['confidence'],
                              ', '.join(item['rule'] for item in field.get('adjustments', [])), field['original']])
    for mismatch in metrics['mismatches']:
        add_row(errors, [mismatch['id'], mismatch['ocr'], mismatch['expected']])
    for key, value in [
        ('Содержание', 'Расшифровка и проверка кратких ответов 1–19; развёрнутые решения не оцениваются'),
        ('Ключи', data.get('answer_key', {}).get('title', 'Не загружены')),
        ('ДЕМО', 'Случайные ответы! Баллы не являются результатами ОГЭ.' if data.get('answer_key', {}).get('demo') else 'Нет'),
        ('Страниц', len(data['pages'])),
        ('Подтверждено полей', metrics['reviewed_fields']),
        ('Точно распознано до ручных правок', metrics['matching_fields']),
        ('Доля точных совпадений', metrics['exact_match_rate']),
        ('Ограничение метрики', 'OCR сравнивается с ручными правками. Это не точность выставления баллов.'),
        ('Блок замены', 'Однозначные замены применяются автоматически; конфликты помечаются'),
        ('Пустые значения', 'Распознанное пустое поле даёт 0; техническая ошибка обработки не считается пустым ответом'),
        ('Ручные правки', 'Сохранены дословно; регистр и смешение алфавитов не исправлялись'),
        ('Источник', data['source_manifest']),
    ]:
        add_row(info, [key, value])
    if not metrics['reviewed_fields']:
        add_row(info, ['Точность OCR', 'Не измерена: эталонная расшифровка не загружена'])
    for group, stats in metrics.get('groups', {}).items():
        add_row(info, [f'Точность OCR / {group}', stats['exact_match_rate']])
        add_row(info, [f'CER / {group}', stats['cer']])
    for sheet in book:
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='254A70')
        for column in sheet.columns:
            width = min(55, max(12, max(len(str(cell.value or '')) for cell in column) + 2))
            sheet.column_dimensions[get_column_letter(column[0].column)].width = width
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical='top', wrap_text=True)
    book.save(destination)


def export(recognition_path, corrections_path, output):
    recognition_path, corrections_path, output = (path.resolve() for path in
                                                  (recognition_path, corrections_path, output))
    recognition = json.loads(recognition_path.read_text(encoding='utf-8'))
    corrections = json.loads(corrections_path.read_text(encoding='utf-8'))
    if recognition.get('run_status') != 'complete':
        raise ValueError('Сначала завершите запуск OCR')
    data = apply_corrections(recognition, corrections)
    metrics = evaluate(recognition, corrections)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Папка экспорта должна быть пустой; укажите новую --output')
    output.mkdir(parents=True, exist_ok=True)

    for page in data['pages']:
        for key in ('original', 'replacements'):
            if key in page:
                page[key] = relative(recognition_path.parent / page[key], output)
        for field in page['fields']:
            for key in ('original', 'cleaned'):
                field[key] = relative(recognition_path.parent / field[key], output)
    data['corrections_source'] = str(corrections_path)
    workbook(data, metrics, output / 'students.xlsx')
    (output / 'confirmed.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    write_review(output, data)
    print(f'Подтверждено полей: {metrics["reviewed_fields"]}; таблица: {output / "students.xlsx"}')
    return data, metrics


def main():
    parser = argparse.ArgumentParser(description='Экспорт ручных правок в Excel и JSON')
    parser.add_argument('recognition', type=Path)
    parser.add_argument('corrections', type=Path)
    parser.add_argument('--output', type=Path, default=Path('output/results'))
    args = parser.parse_args()
    try:
        export(args.recognition, args.corrections, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')


if __name__ == '__main__':
    main()
