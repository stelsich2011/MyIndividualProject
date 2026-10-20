"""Проверка подтверждённых ответов по явным ключам; без угадывания варианта."""

from copy import deepcopy
import random

from .recognize import normalize


def demo_key(seed=42):
    generator = random.Random(seed)
    return {'schema_version': 1, 'demo': True, 'title': 'ДЕМО: случайные цифры, не ключи ОГЭ',
            'seed': seed, 'default_variant': 'demo', 'variants': {'demo': {
                str(number): {'accepted': [str(generator.randrange(10))], 'points': 1}
                for number in range(1, 20)}}}


def validate_key(key):
    if key.get('schema_version') != 1 or not isinstance(key.get('demo'), bool):
        raise ValueError('Ключ должен содержать schema_version: 1 и demo: true/false')
    variants = key.get('variants')
    if not isinstance(variants, dict) or not variants:
        raise ValueError('В ключе отсутствуют варианты')
    for variant, tasks in variants.items():
        if not isinstance(variant, str) or not isinstance(tasks, dict) or set(tasks) != {str(i) for i in range(1, 20)}:
            raise ValueError('Каждый вариант должен содержать задания 1–19')
        for task in tasks.values():
            if not isinstance(task, dict):
                raise ValueError('Неверный формат задания')
            accepted, points = task.get('accepted'), task.get('points')
            if not isinstance(accepted, list) or not accepted or any(not isinstance(x, str) or not normalize(x) for x in accepted):
                raise ValueError('accepted должен содержать непустые строковые ответы')
            if type(points) is not int or not 1 <= points <= 100:
                raise ValueError('points должен быть целым числом от 1 до 100')
    if key.get('default_variant') is not None and key['default_variant'] not in variants:
        raise ValueError('default_variant отсутствует в variants')
    return key


def parse_replacements(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        task, separator, answer = line.partition('=')
        task = task.strip()
        if not separator or not task.isdecimal() or not 1 <= int(task) <= 19:
            raise ValueError('Каждая замена задаётся строкой номер=ответ, например 12=3')
        task = str(int(task))
        if task in result:
            raise ValueError(f'Повторная замена задания {task}: выберите окончательный ответ')
        result[task] = answer.strip()
    return result


def grade_page(page, key):
    variant = page.get('variant') or key.get('default_variant')
    base = {'demo': key['demo'], 'variant': variant, 'total': None, 'provisional': None,
            'maximum': None, 'tasks': [], 'status': 'Не определён вариант'}
    if variant not in key['variants']:
        return base
    tasks = key['variants'][variant]
    fields = {field['name']: field for field in page['fields']}
    changes = page.get('replacement_answers', {})
    checked_changes = page.get('replacements_reviewed') is True
    if not isinstance(changes, dict) or any(str(k) not in tasks or not isinstance(v, str) for k, v in changes.items()):
        raise ValueError(f'Неверный блок замен страницы {page["page"]}')
    earned, ready = 0, 0
    for number, task in sorted(tasks.items(), key=lambda item: int(item[0])):
        field = fields.get(f'answer_{int(number):02}')
        confirmed = field is not None and field.get('reviewed') is True
        value = field.get('corrected_text') if confirmed else None
        source = 'Основное поле'
        if checked_changes and number in changes:
            value, confirmed, source = changes[number], True, 'Блок замены'
        if confirmed and not isinstance(value, str):
            raise ValueError('Подтверждённый ответ должен быть строкой')
        points = None
        status = 'Не проверено вручную'
        if confirmed:
            ready += 1
            match = normalize(value) in {normalize(answer) for answer in task['accepted']}
            points = task['points'] if match else 0
            earned += points
            status = 'Верно' if match else ('Нет ответа' if not normalize(value) else 'Неверно')
        base['tasks'].append({'number': int(number), 'answer': value, 'source': source,
                              'accepted': task['accepted'], 'points': points,
                              'maximum': task['points'], 'status': status})
    base['maximum'] = sum(task['points'] for task in tasks.values())
    # Предварительная сумма не является итоговой: ещё могут быть непроверенные замены.
    base['provisional'] = earned if ready else None
    if page.get('status') != 'prepared':
        base['status'] = 'Нужна проверка подготовки скана'
    elif ready != 19:
        base['status'] = f'Проверено ответов {ready}/19'
    elif not checked_changes:
        base['status'] = 'Предварительно: блок замены не проверен'
    else:
        base['total'] = earned
        base['status'] = 'Проверено'
    if key['demo']:
        base['status'] = 'ДЕМО — ' + base['status']
    return base


def grade_data(data, key):
    validate_key(key)
    result = deepcopy(data)
    result['answer_key'] = deepcopy(key)
    for page in result['pages']:
        page['grading'] = grade_page(page, key)
    return result
