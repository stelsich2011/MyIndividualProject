

def field_value(field):
    if field is None:
        return None
    value = field.get('corrected_text')
    if isinstance(value, str):
        return value
    return None if field.get('status') == 'ocr_error' else field.get('candidate')


def warnings(field, threshold=.90):
    if field.get('corrected_text') is not None:
        return []
    result = list(field.get('warnings', []))
    if field.get('status') == 'ocr_error':
        result.append('Ошибка OCR')
    elif field.get('candidate'):
        score = field.get('confidence')
        if score is None or score < threshold:
            result.append('Низкая уверенность OCR')
    return list(dict.fromkeys(result))


def effective_answer(page, number):
    pass
    name = f'answer_{int(number):02}'
    field = next((f for f in page['fields'] if f['name'] == name), None)
    changes = page.get('replacement_answers', {})
    if str(number) in changes:
        return changes[str(number)], 'Ручная замена', []
    if field and field.get('corrected_text') is not None:
        return field_value(field), 'Ручное исправление', []
    automatic = page.get('automatic_replacements', {})
    if str(number) in automatic:
        item = automatic[str(number)]
        return item['text'], 'Блок замены OCR', warnings({'candidate': item['text'], **item})
    return field_value(field), 'Основное поле OCR', warnings(field) if field else ['Поле отсутствует']
