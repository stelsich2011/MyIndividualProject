"""Сравнение пробного OCR с вручную проверенной расшифровкой, не с ключами ОГЭ."""

import argparse
import json
from pathlib import Path

from .recognize import normalize
from .corrections import validate_corrections


def evaluate(recognition, corrections):
    indexed = validate_corrections(recognition, corrections)
    fields = {field['id']: field for page in recognition['pages'] for field in page['fields']}
    compared, mismatches = [], []
    for correction in indexed.values():
        identifier = correction['id']
        if not correction['reviewed']:
            continue
        expected = normalize(correction['corrected_text'])
        actual = fields[identifier]['candidate']
        compared.append(identifier)
        if actual != expected:
            mismatches.append({'id': identifier, 'ocr': actual, 'expected': expected})
    total = len(compared)
    return {'reviewed_fields': total, 'matching_fields': total - len(mismatches),
            'exact_match_rate': (total - len(mismatches)) / total if total else None,
            'unreviewed_fields': len(fields) - total, 'mismatches': mismatches}


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
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
