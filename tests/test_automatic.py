from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest

import cv2
import numpy as np

from oge_checker.answers import effective_answer, field_value
from oge_checker.evaluate import evaluate, import_reference
from oge_checker.geometry import restore_strokes
from oge_checker.grading import grade_page
from oge_checker.image_io import read_image, write_image
from oge_checker.keys import key_from_rows, load_key, write_template
from oge_checker.replacements import recognize_block
from oge_checker.session import Session
from test_grading import complete_data, all_sevens_key


class AutomaticTests(unittest.TestCase):
    def test_unreviewed_candidates_are_scored_and_not_marked_human(self):
        page = complete_data()['pages'][0]
        for field in page['fields']:
            field.update(reviewed=False, corrected_text=None)
        old = deepcopy(page)
        result = grade_page(page, all_sevens_key())
        self.assertEqual(result['total'], 19)
        self.assertIn('сомнения', result['status'])
        self.assertEqual(page, old)

    def test_empty_is_zero_but_ocr_failure_is_not_a_blank(self):
        page = complete_data()['pages'][0]
        page['fields'][0].update(candidate='', corrected_text=None, reviewed=False)
        self.assertEqual(grade_page(page, all_sevens_key())['total'], 18)
        page['fields'][0]['status'] = 'ocr_error'
        result = grade_page(page, all_sevens_key())
        self.assertIsNone(result['total'])
        self.assertIsNone(result['tasks'][0]['points'])
        page['fields'][0]['corrected_text'] = '7'
        self.assertEqual(grade_page(page, all_sevens_key())['total'], 19)

    def test_replacement_and_manual_priorities_and_explicit_clear(self):
        page = complete_data()['pages'][0]
        page['fields'][0]['corrected_text'] = None
        page['automatic_replacements'] = {'1': {'text': '8', 'confidence': .99}}
        self.assertEqual(effective_answer(page, 1)[0], '8')
        page['fields'][0]['corrected_text'] = '7'
        self.assertEqual(effective_answer(page, 1)[0], '7')
        page['replacement_answers'] = {'1': ''}
        self.assertEqual(effective_answer(page, 1)[0], '')

    def test_automatic_use_never_creates_accuracy_reference(self):
        data = complete_data()
        session = Session(data, Path('.'))
        session.set_key(all_sevens_key())
        session.snapshot()
        self.assertIsNone(session.metrics()['exact_match_rate'])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'project.json'
            session.save(path)
            self.assertIsNone(Session.open(path).metrics()['exact_match_rate'])

    def test_legacy_replacement_draft_migrates_without_confirmation(self):
        data = complete_data()
        data['pages'][0]['replacement_draft'] = '1=8'
        data['pages'][0]['replacements_reviewed'] = False
        data['answer_key'] = all_sevens_key()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'legacy.json'
            path.write_text(json.dumps({'desktop_project_version': 1, 'recognition': data}), encoding='utf-8')
            session = Session.open(path)
            self.assertEqual(session.snapshot()['pages'][0]['grading']['total'], 18)

    def test_cer_groups_empty_and_nonempty(self):
        data = complete_data()
        data['pages'][0]['fields'][0]['candidate'] = '17'
        data['pages'][0]['fields'][1]['candidate'] = ''
        ref = {'source_id': data['source_id'], 'fields': [
            {'id': '1:answer_01', 'corrected_text': '12', 'reviewed': True},
            {'id': '1:answer_02', 'corrected_text': '', 'reviewed': True}]}
        metrics = evaluate(data, ref)
        self.assertEqual(metrics['exact_match_rate'], .5)
        self.assertEqual(metrics['groups']['answers']['cer'], .5)
        self.assertEqual(metrics['groups']['empty']['matches'], 1)
        self.assertEqual(metrics['groups']['nonempty']['matches'], 0)

    def test_reference_csv_preserves_blank_and_rejects_other_source(self):
        data = complete_data()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'reference.csv'
            path.write_text('source_id;страница;поле;текст\ntest;1;answer_01;\n', encoding='utf-8-sig')
            reference = import_reference(path, data)
            self.assertEqual(reference['fields'][0]['corrected_text'], '')
            path.write_text('source_id;страница;поле;текст\nother;1;answer_01;7\n', encoding='utf-8-sig')
            with self.assertRaises(ValueError):
                import_reference(path, data)

    def test_unicode_image_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'Пример с пробелами.png'
            image = np.full((50, 50), 255, np.uint8)
            image[15:35, 20:30] = 0
            write_image(path, image)
            np.testing.assert_array_equal(read_image(path, cv2.IMREAD_GRAYSCALE), image)

    def test_visible_leading_one_and_minus_are_not_guessed_without_strokes(self):
        image = np.full((60, 110), 255, np.uint8)
        cv2.rectangle(image, (10, 10), (13, 45), 0, -1)
        cv2.rectangle(image, (40, 10), (60, 45), 0, -1)
        self.assertEqual(restore_strokes('2', image)[0], '12')
        self.assertEqual(restore_strokes('|2', image)[0], '12')
        self.assertEqual(restore_strokes('12', image)[0], '12')
        cv2.rectangle(image, (10, 5), (23, 45), 0, -1)
        self.assertEqual(restore_strokes('2', image)[0], '2')


class KeysTests(unittest.TestCase):
    def rows(self):
        return [['Вариант', 'Задание', 'Ответ', 'Баллы']] + [['01', str(n), '007|-0,5' if n == 1 else '7', '1'] for n in range(1, 20)]

    def test_real_keys_and_alternatives_remain_text(self):
        key = key_from_rows(self.rows())
        self.assertFalse(key['demo'])
        self.assertEqual(key['default_variant'], '01')
        self.assertEqual(key['variants']['01']['1']['accepted'], ['007', '-0,5'])

    def test_missing_duplicate_and_bad_points_report_errors(self):
        for rows in [self.rows()[:-1], self.rows() + [self.rows()[1]], self.rows()[:1] + [['1', '1', '7', '1.5']]]:
            with self.assertRaises(ValueError):
                key_from_rows(rows)

    def test_excel_and_csv_templates_and_cp1251(self):
        import csv
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for extension in ('xlsx', 'csv'):
                path = root / f'ключи.{extension}'
                write_template(path)
                self.assertEqual(load_key(path)['variants']['1']['1']['accepted'], ['0,5'])
            path = root / 'ansi.csv'
            with path.open('w', encoding='cp1251', newline='') as stream:
                csv.writer(stream, delimiter=';').writerows(self.rows())
            self.assertEqual(load_key(path)['variants']['01']['1']['accepted'][0], '007')

    def test_excel_formula_rejected(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'formula.xlsx'
            book = Workbook()
            for row in self.rows():
                book.active.append(row)
            book.active['C2'] = '=1+1'
            book.save(path)
            with self.assertRaisesRegex(ValueError, 'Строка 2'):
                load_key(path)


class ReplacementTests(unittest.TestCase):
    def test_printed_equals_does_not_create_false_replacements(self):
        from oge_checker.recognize import preprocess
        class Engine:
            def read(self, image):
                raise AssertionError('OCR не должен вызываться для пустого блока')
        image = np.full((196, 1846, 3), 255, np.uint8)
        for row in range(3):
            for x in (104, 1056):
                for offset in (28, 34):
                    cv2.line(image, (x, row * 65 + offset), (x + 16, row * 65 + offset), (0, 0, 0), 3)
        changes, warnings, entries = recognize_block(image, Engine(), preprocess, lambda v: v)
        self.assertEqual((changes, warnings, entries), ({}, [], []))

    def test_blank_and_conflicting_entries(self):
        class Engine:
            def __init__(self):
                self.values = iter([('1', .99), ('7', .99), ('1', .99), ('8', .99)])
            def read(self, image):
                return next(self.values)
        image = np.full((196, 1822, 3), 255, np.uint8)
        calls = iter([False] * 4 + [True] * 8)
        def preprocess(crop):
            return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), next(calls)
        changes, warnings, entries = recognize_block(image, Engine(), preprocess, lambda v: v)
        self.assertEqual(changes, {})
        self.assertEqual(len(entries), 2)
        self.assertTrue(any('Конфликт' in w for w in warnings))

    def test_unambiguous_replacement_and_low_number_confidence(self):
        class Engine:
            def __init__(self, score):
                self.values = iter([('12', score), ('007', .99)])
            def read(self, image):
                return next(self.values)
        image = np.full((196, 1822, 3), 255, np.uint8)
        for score in (.99, .5):
            calls = iter([False] * 2 + [True] * 10)
            changes, warnings, _ = recognize_block(image, Engine(score), lambda crop: (cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), next(calls)), lambda v: v)
            if score > .9:
                self.assertEqual(changes['12']['text'], '007')
            else:
                self.assertEqual(changes, {})
                self.assertTrue(warnings)
