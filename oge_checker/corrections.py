"""Проверка и применение ручной расшифровки без изменения кандидатов OCR."""

from copy import deepcopy


def validate_corrections(recognition, corrections):
    if corrections.get('source_id') != recognition['source_id']:
        raise ValueError('Правки относятся к другому набору сканов')
    fields = {field['id']: field for page in recognition['pages'] for field in page['fields']}
    seen = set()
    for correction in corrections['fields']:
        identifier = correction['id']
        if identifier not in fields or identifier in seen:
            raise ValueError(f'Неизвестное или повторное поле: {identifier}')
        seen.add(identifier)
        if not isinstance(correction.get('reviewed'), bool) or not isinstance(correction.get('corrected_text'), str):
            raise ValueError(f'Неверный формат правки: {identifier}')
    return {item['id']: item for item in corrections['fields']}


def apply_corrections(recognition, corrections):
    indexed = validate_corrections(recognition, corrections)
    result = deepcopy(recognition)
    for page in result['pages']:
        for field in page['fields']:
            correction = indexed.get(field['id'])
            if correction is None:
                continue
            field['reviewed'] = correction['reviewed']
            field['corrected_text'] = correction['corrected_text']
            field['status'] = 'human_reviewed' if correction['reviewed'] else 'needs_review'
    return result
