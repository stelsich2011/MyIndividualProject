
import argparse
import json
from pathlib import Path

from .recognize import normalize
from .corrections import validate_corrections


def distance(a, b):
    previous = list(range(len(b) + 1))
    for i, char in enumerate(a, 1):
        current = [i]
        for j, other in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (char != other)))
        previous = current
    return previous[-1]


def evaluate(recognition, corrections):
    indexed = validate_corrections(recognition, corrections)
    fields = {field['id']: field for page in recognition['pages'] for field in page['fields']}
    compared, mismatches = [], []
    groups = {}
    for correction in indexed.values():
        identifier = correction['id']
        if not correction['reviewed']:
            continue
        expected = normalize(correction['corrected_text'])
        actual = fields[identifier]['candidate']
        compared.append(identifier)
        name = fields[identifier]['name'] if 'name' in fields[identifier] else identifier.split(':', 1)[-1]
        kind = 'answers' if name.startswith('answer_') else ('class' if name == 'class' else 'names')
        for group in ('all', kind, 'nonempty' if expected else 'empty'):
            stats = groups.setdefault(group, {'fields': 0, 'matches': 0, 'character_errors': 0, 'characters': 0})
            stats['fields'] += 1
            stats['matches'] += actual == expected
            stats['character_errors'] += distance(expected, actual)
            stats['characters'] += len(expected)
        if actual != expected:
            mismatches.append({'id': identifier, 'ocr': actual, 'expected': expected})
    total = len(compared)
    for stats in groups.values():
        stats['exact_match_rate'] = stats['matches'] / stats['fields']
        stats['cer'] = stats['character_errors'] / stats['characters'] if stats['characters'] else None
    return {'reviewed_fields': total, 'matching_fields': total - len(mismatches), 'groups': groups,
            'exact_match_rate': (total - len(mismatches)) / total if total else None,
            'unreviewed_fields': len(fields) - total, 'mismatches': mismatches}


def import_reference(path, recognition):
    pass
    from .keys import read_table
    path = Path(path)
    if path.suffix.lower() == '.json':
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    else:
        rows = read_table(path)
        if not rows or list(rows[0]) != ['source_id', 'страница', 'поле', 'текст']:
            raise ValueError('Столбцы эталона: source_id;страница;поле;текст')
        data = {'schema_version': 1, 'source_id': recognition['source_id'], 'fields': []}
        for i, row in enumerate(rows[1:], 2):
            if not any(str(v).strip() for v in row):
                continue
            if len(row) != 4 or str(row[0]) != recognition['source_id']:
                raise ValueError(f'Строка {i}: эталон относится к другому набору сканов')
            data['fields'].append({'id': f'{int(row[1])}:{row[2]}', 'corrected_text': str(row[3]), 'reviewed': True})
    validate_corrections(recognition, data)
    return data


def main():
    parser = argparse.ArgumentParser(description='Измерение точности OCR по ручной расшифровке')
    parser.add_argument('recognition', type=Path)
    parser.add_argument('corrections', type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.recognition.read_text(encoding='utf-8')),
                          json.loads(args.corrections.read_text(encoding='utf-8')))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Ошибка: {exc}\n')
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
