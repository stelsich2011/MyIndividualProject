
import csv
import io
import json
from pathlib import Path

from .grading import validate_key

HEADERS = ('Вариант', 'Задание', 'Ответ', 'Баллы')


def read_table(path):
    path = Path(path)
    if path.suffix.lower() == '.xlsx':
        from openpyxl import load_workbook
        book = load_workbook(path, read_only=True, data_only=False)
        try:
            rows = []
            for cells in book.active.iter_rows():
                if any(c.data_type == 'f' for c in cells):
                    raise ValueError(f'Строка {cells[0].row}: формулы не поддерживаются; вставьте текстовые значения')
                rows.append([c.value if c.value is not None else '' for c in cells])
            return rows
        finally:
            book.close()
    if path.suffix.lower() != '.csv':
        raise ValueError('Нужен файл .xlsx или .csv')
    content = path.read_bytes()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('cp1251')
    return list(csv.reader(io.StringIO(text), delimiter=';'))


def key_from_rows(rows, title='Ключи ответов'):
    rows = list(rows)
    if not rows or tuple(str(v).strip() for v in rows[0][:4]) != HEADERS:
        raise ValueError('Первая строка: ' + ';'.join(HEADERS))
    variants = {}
    for index, row in enumerate(rows[1:], 2):
        if not any(str(x).strip() for x in row):
            continue
        try:
            if len(row) < 4 or any(str(x).strip() for x in row[4:]):
                raise ValueError('нужно четыре столбца')
            variant, number, answer, points = (str(x).strip() for x in row[:4])
            if not variant or not number.isdecimal() or not 1 <= int(number) <= 19:
                raise ValueError('укажите вариант и номер задания от 1 до 19')
            if not points.isdecimal() or not 1 <= int(points) <= 100:
                raise ValueError('баллы должны быть целым числом от 1 до 100')
            accepted = [x.strip() for x in answer.split('|')]
            if not all(accepted):
                raise ValueError('ответ и альтернативы не должны быть пустыми')
            tasks = variants.setdefault(variant, {})
            number = str(int(number))
            if number in tasks:
                raise ValueError('задание повторяется; альтернативы разделяйте знаком |')
            tasks[number] = {'accepted': accepted, 'points': int(points)}
        except ValueError as exc:
            raise ValueError(f'Строка {index}: {exc}') from exc
    for variant, tasks in variants.items():
        missing = sorted(set(map(str, range(1, 20))) - set(tasks), key=int)
        if missing:
            raise ValueError(f'Вариант {variant}: отсутствуют задания {", ".join(missing)}')
    key = {'schema_version': 1, 'demo': False, 'title': title, 'variants': variants}
    if len(variants) == 1:
        key['default_variant'] = next(iter(variants))
    return validate_key(key)


def rows_from_key(key):
    return [list(HEADERS)] + [[variant, number, '|'.join(task['accepted']), str(task['points'])]
        for variant, tasks in key['variants'].items()
        for number, task in sorted(tasks.items(), key=lambda x: int(x[0]))]


def load_key(path):
    path = Path(path)
    if path.suffix.lower() == '.json':
        return validate_key(json.loads(path.read_text(encoding='utf-8-sig')))
    return key_from_rows(read_table(path), path.stem)


def write_template(path):
    path = Path(path)
    rows = [list(HEADERS)] + [['1', str(n), '0,5' if n == 1 else '7', '1'] for n in range(1, 20)]
    if path.suffix.lower() == '.xlsx':
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = 'Ключи'
        for row in rows:
            sheet.append(row)
        for row in sheet:
            for cell in row:
                cell.number_format = '@'
                cell.data_type = 's'
        sheet.freeze_panes = 'A2'
        for column in ('A', 'B', 'C', 'D'):
            sheet.column_dimensions[column].width = 24
        book.save(path)
    else:
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            csv.writer(stream, delimiter=';').writerows(rows)
