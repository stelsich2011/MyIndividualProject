"""Состояние desktop-проекта: сохранение правок, ключей и проверки замен."""

from copy import deepcopy
import json
from pathlib import Path

from .corrections import apply_corrections
from .grading import demo_key, grade_data, validate_key
from .recognize import relative


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rebase(data, old_root, new_root):
    result = deepcopy(data)
    for page in result['pages']:
        for key in ('original', 'replacements', 'aligned', 'preview'):
            if page.get(key):
                page[key] = relative(old_root / page[key], new_root)
        for field in page['fields']:
            for key in ('original', 'cleaned'):
                if field.get(key):
                    field[key] = relative(old_root / field[key], new_root)
    return result


class Session:
    def __init__(self, data, root):
        self.data = data
        self.root = Path(root).resolve()
        self.key = data.get('answer_key')
        self.dirty = False

    @classmethod
    def open(cls, path):
        path = Path(path).resolve()
        data = read_json(path)
        if data.get('desktop_project_version') == 1:
            data = data['recognition']
        if data.get('run_status') != 'complete' or not isinstance(data.get('pages'), list):
            raise ValueError('Выберите завершённый recognition.json, confirmed.json или project.json')
        for page in data['pages']:
            if not isinstance(page.get('fields'), list):
                raise ValueError('Неверный формат полей OCR')
        session = cls(data, path.parent)
        if session.key:
            validate_key(session.key)
        return session

    def load_corrections(self, path):
        self.data = apply_corrections(self.data, read_json(path))
        self.dirty = True

    def set_key(self, key):
        validate_key(key)
        self.key = deepcopy(key)
        self.dirty = True

    def use_demo(self, seed=42):
        self.set_key(demo_key(seed))

    def snapshot(self):
        result = deepcopy(self.data)
        if self.key:
            result = grade_data(result, self.key)
        return result

    def save(self, path):
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = rebase(self.snapshot(), self.root, path.parent)
        payload = {'desktop_project_version': 1, 'recognition': data}
        # Атомарная запись: предыдущий проект остаётся целым при ошибке записи.
        temporary = path.with_name(path.name + '.tmp')
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
        self.dirty = False

    def corrections(self):
        return {'schema_version': 1, 'source_id': self.data['source_id'], 'fields': [
            {'id': field['id'], 'corrected_text': field.get('corrected_text') if field.get('corrected_text') is not None else field['candidate'],
             'reviewed': field.get('reviewed') is True, 'raw_text': field['raw_text'], 'candidate': field['candidate']}
            for page in self.data['pages'] for field in page['fields']]}

    def export_excel(self, path):
        from .export import workbook
        from .evaluate import evaluate
        path = Path(path).resolve()
        data = rebase(self.snapshot(), self.root, path.parent)
        metrics = evaluate(self.data, self.corrections())
        workbook(data, metrics, path)
