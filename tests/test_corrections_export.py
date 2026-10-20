from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from oge_checker.corrections import apply_corrections, validate_corrections
from oge_checker.decimal_mark import restore_decimal
from oge_checker.export import export


class DecimalTests(unittest.TestCase):
    def image(self, comma=True):
        image = np.full((60, 140), 255, dtype=np.uint8)
        cv2.rectangle(image, (10, 10), (25, 43), 0, -1)
        cv2.rectangle(image, (90, 10), (110, 43), 0, -1)
        if comma:
            cv2.rectangle(image, (55, 32), (61, 45), 0, -1)
        return image

    def test_restore_only_visible_separator(self):
        value, changes = restore_decimal('-27', self.image())
        self.assertEqual(value, '-2,7')
        self.assertEqual(changes[0]['before'], '-27')
        self.assertEqual(restore_decimal('27', self.image(False)), ('27', []))

    def test_preserve_explicit_separator_and_non_numeric_answers(self):
        for candidate in ['0,3', '2)3)', '120см2', '12.5', '1', '|2', '']:
            self.assertEqual(restore_decimal(candidate, self.image()), (candidate, []))

    def test_ambiguous_extra_mark_is_not_restored(self):
        image = self.image()
        cv2.rectangle(image, (70, 32), (76, 45), 0, -1)
        self.assertEqual(restore_decimal('27', image), ('27', []))


class CorrectionsTests(unittest.TestCase):
    def source(self):
        return {'source_id': 'source', 'run_status': 'complete', 'source_manifest': 'manifest.json',
                'pages': [{'page': 1, 'status': 'prepared', 'original': 'scan.png', 'replacements': 'scan.png',
                           'fields': [{'id': '1:answer_01', 'name': 'answer_01', 'label': 'Ответ 1',
                            'raw_text': '03', 'candidate': '03', 'original': 'scan.png', 'cleaned': 'scan.png',
                            'confidence': .8, 'reviewed': False, 'corrected_text': None, 'status': 'needs_review'}]}]}

    def test_apply_preserves_candidate_and_original_and_handles_blank(self):
        source = self.source()
        old = deepcopy(source)
        corrections = {'source_id': 'source', 'fields': [
            {'id': '1:answer_01', 'corrected_text': '', 'reviewed': True}]}
        result = apply_corrections(source, corrections)
        self.assertEqual(source, old)
        field = result['pages'][0]['fields'][0]
        self.assertEqual(field['candidate'], '03')
        self.assertEqual(field['corrected_text'], '')
        self.assertTrue(field['reviewed'])

    def test_duplicates_unknown_ids_and_wrong_source_are_rejected(self):
        item = {'id': '1:answer_01', 'corrected_text': '0,3', 'reviewed': True}
        for corrections in [
            {'source_id': 'other', 'fields': [item]},
            {'source_id': 'source', 'fields': [item, item]},
            {'source_id': 'source', 'fields': [dict(item, id='88:class')]},
            {'source_id': 'source', 'fields': [dict(item, reviewed='true')]},
        ]:
            with self.assertRaises(ValueError):
                validate_corrections(self.source(), corrections)

    @unittest.skipUnless(importlib.util.find_spec('openpyxl'), 'Нужна зависимость export')
    def test_excel_roundtrip_preserves_text_and_unreviewed_fields(self):
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recognition = root / 'recognition.json'
            corrections = root / 'corrections.json'
            original = self.source()
            more = deepcopy(original['pages'][0]['fields'][0])
            more.update(id='1:answer_02', name='answer_02', label='Ответ 2', candidate='007')
            original['pages'][0]['fields'].append(more)
            recognition.write_text(json.dumps(original))
            edits = {'source_id': 'source', 'fields': [
                {'id': '1:answer_01', 'corrected_text': '=1+1', 'reviewed': True},
                {'id': '1:answer_02', 'corrected_text': '007', 'reviewed': False}]}
            corrections.write_text(json.dumps(edits))
            before = corrections.read_bytes()
            data, _ = export(recognition, corrections, root / 'out')
            book = load_workbook(root / 'out/students.xlsx')
            self.assertEqual(book['Ученики']['F2'].value, '=1+1')
            self.assertEqual(book['Ученики']['F2'].data_type, 's')
            self.assertIsNone(book['Ученики']['G2'].value)
            self.assertIsNone(book['Ученики']['AD2'].value)  # Баллы ещё не вычислены.
            self.assertEqual(book['Поля']['D3'].value, '007')
            self.assertEqual(corrections.read_bytes(), before)
            self.assertEqual(data['pages'][0]['fields'][0]['raw_text'], '03')
            with self.assertRaises(ValueError):
                export(recognition, corrections, root / 'out')
