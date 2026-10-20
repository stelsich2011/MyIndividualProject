from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from oge_checker.grading import demo_key, grade_data, grade_page, parse_replacements, validate_key
from oge_checker.session import Session


def complete_data():
    return {'source_id': 'test', 'source_manifest': 'manifest.json', 'run_status': 'complete', 'pages': [{
        'page': 1, 'status': 'prepared', 'original': 'images/scan.png', 'replacements': 'images/changes.png',
        'replacements_reviewed': True, 'fields': [
            {'id': f'1:answer_{number:02}', 'name': f'answer_{number:02}', 'label': f'Ответ {number}',
             'candidate': '7', 'raw_text': '7', 'corrected_text': '7', 'reviewed': True,
             'original': 'images/crop.png', 'cleaned': 'images/cleaned.png', 'confidence': .8}
            for number in range(1, 20)]}]}


def all_sevens_key():
    key = demo_key()
    for task in key['variants']['demo'].values():
        task['accepted'] = ['7']
    return key


class GradingTests(unittest.TestCase):
    def test_reproducible_demo_is_explicit(self):
        self.assertEqual(demo_key(), demo_key())
        self.assertNotEqual(demo_key(1), demo_key(2))
        self.assertTrue(demo_key()['demo'])
        self.assertTrue(all(task['accepted'][0].isdigit() for task in demo_key()['variants']['demo'].values()))
        validate_key(demo_key())

    def test_scoring_correct_wrong_blank_and_alternatives(self):
        data = complete_data()
        key = all_sevens_key()
        key['variants']['demo']['1'] = {'accepted': ['7', '07'], 'points': 2}
        data['pages'][0]['fields'][0]['corrected_text'] = ' 0 7 '
        data['pages'][0]['fields'][1]['corrected_text'] = '8'
        data['pages'][0]['fields'][2]['corrected_text'] = ''
        result = grade_page(data['pages'][0], key)
        self.assertEqual(result['total'], 18)
        self.assertEqual(result['maximum'], 20)
        self.assertEqual(result['tasks'][2]['status'], 'Нет ответа')

    def test_unreviewed_answer_and_block_never_become_final_zero(self):
        page = complete_data()['pages'][0]
        page['fields'][0]['reviewed'] = False
        result = grade_page(page, all_sevens_key())
        self.assertIsNone(result['total'])
        self.assertIsNone(result['tasks'][0]['points'])
        page['fields'][0]['reviewed'] = True
        page['replacements_reviewed'] = False
        result = grade_page(page, all_sevens_key())
        self.assertEqual(result['provisional'], 19)
        self.assertIsNone(result['total'])

    def test_replacement_overrides_main_and_can_clear_answer(self):
        page = complete_data()['pages'][0]
        page['replacement_answers'] = {'1': '8', '2': ''}
        result = grade_page(page, all_sevens_key())
        self.assertEqual(result['total'], 17)
        self.assertEqual(result['tasks'][0]['source'], 'Блок замены')
        self.assertEqual(result['tasks'][1]['status'], 'Нет ответа')

    def test_unknown_variant_and_failed_preparation_remain_pending(self):
        page = complete_data()['pages'][0]
        page['variant'] = 'unknown'
        self.assertIsNone(grade_page(page, all_sevens_key())['total'])
        page.pop('variant')
        page['status'] = 'needs_review'
        self.assertIsNone(grade_page(page, all_sevens_key())['total'])

    def test_numeric_strings_do_not_lose_sign_or_leading_zero(self):
        page = complete_data()['pages'][0]
        page['fields'][0]['corrected_text'] = '07'
        page['fields'][1]['corrected_text'] = '-7'
        self.assertEqual(grade_page(page, all_sevens_key())['total'], 17)

    def test_invalid_keys_and_replacements_are_rejected(self):
        invalid = all_sevens_key()
        invalid['variants']['demo']['1']['points'] = True
        with self.assertRaises(ValueError):
            validate_key(invalid)
        invalid = all_sevens_key()
        del invalid['variants']['demo']['19']
        with self.assertRaises(ValueError):
            validate_key(invalid)
        for text in ['0=7', '20=7', '1=7\n01=8', '1:7']:
            with self.assertRaises(ValueError):
                parse_replacements(text)
        self.assertEqual(parse_replacements('1=7\n\n12='), {'1': '7', '12': ''})

    def test_grading_does_not_mutate_source(self):
        source = complete_data()
        old = deepcopy(source)
        grade_data(source, all_sevens_key())
        self.assertEqual(source, old)

    def test_desktop_project_roundtrip_rebases_assets_and_keeps_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = root / 'ocr'
            assets.mkdir()
            session = Session(complete_data(), assets)
            session.set_key(all_sevens_key())
            session.data['pages'][0]['replacement_answers'] = {'1': '8'}
            session.data['pages'][0]['replacement_draft'] = '1=8'
            destination = root / 'project/project.json'
            session.save(destination)
            loaded = Session.open(destination)
            page = loaded.snapshot()['pages'][0]
            self.assertEqual(page['grading']['total'], 18)
            self.assertTrue(page['fields'][0]['reviewed'])
            self.assertEqual(page['replacement_draft'], '1=8')
            self.assertEqual((loaded.root / page['original']).resolve(), (assets / 'images/scan.png').resolve())
            self.assertFalse(session.dirty)
