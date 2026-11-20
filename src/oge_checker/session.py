
from copy import deepcopy
import json
from pathlib import Path

from .corrections import apply_corrections
from .grading import demo_key, grade_data, validate_key, parse_replacements
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
        self.reference = data.get('accuracy_reference')

    @classmethod
    def open(cls, path):
        path = Path(path).resolve()
        data = read_json(path)
        legacy = data.get('desktop_project_version') == 1
        if data.get('desktop_project_version') in (1, 2):
            data = data['recognition']
        if data.get('run_status') != 'complete' or not isinstance(data.get('pages'), list):
            raise ValueError('Выберите завершённый recognition.json, confirmed.json или project.json')
        for page in data['pages']:
            if not isinstance(page.get('fields'), list):
                raise ValueError('Неверный формат полей OCR')
            if legacy and 'replacement_draft' in page:
                try:
                    page['replacement_answers'] = parse_replacements(page['replacement_draft'])
                    page.pop('replacement_draft_error', None)
                except ValueError as exc:
                    page['replacement_draft_error'] = str(exc)
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
        if self.reference:
            result['accuracy_reference'] = deepcopy(self.reference)
        if self.key:
            result = grade_data(result, self.key)
        return result

    def save(self, path):
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = rebase(self.snapshot(), self.root, path.parent)
        payload = {'desktop_project_version': 2, 'recognition': data}

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
        metrics = self.metrics()
        workbook(data, metrics, path)

    def metrics(self):
        from .evaluate import evaluate
        empty = {'schema_version': 1, 'source_id': self.data['source_id'], 'fields': []}
        return evaluate(self.data, self.reference or empty)

    def load_reference(self, path):
        from .evaluate import import_reference
        self.reference = import_reference(path, self.data)
        self.dirty = True
