import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from oge_checker.evaluate import evaluate
from oge_checker.recognize import normalize, preprocess, recognize


class RecognitionTests(unittest.TestCase):
    def test_removes_dots_but_keeps_minus_and_comma(self):
        image = np.full((64, 300), 255, dtype=np.uint8)
        for x in range(0, 300, 10):
            cv2.rectangle(image, (x, 0), (x + 2, 3), 0, -1)
        cv2.rectangle(image, (40, 25), (65, 28), 0, -1)  # Минус.
        cv2.rectangle(image, (85, 37), (90, 49), 0, -1)  # Запятая.
        cleaned, empty = preprocess(image)
        self.assertFalse(empty)
        components, _, stats, _ = cv2.connectedComponentsWithStats(255 - cleaned)
        self.assertEqual(components - 1, 2)
        self.assertTrue(any(width == 26 and height == 4 for _, _, width, height, _ in stats[1:]))
        self.assertTrue(any(width == 6 and height == 13 for _, _, width, height, _ in stats[1:]))

    def test_grid_only_is_empty_candidate(self):
        image = np.full((64, 100), 255, dtype=np.uint8)
        image[2:5, 4:7] = 0
        _, empty = preprocess(image)
        self.assertTrue(empty)

    def test_normalization_preserves_punctuation_and_letters(self):
        self.assertEqual(normalize(' − 0 , 3 '), '-0,3')
        self.assertEqual(normalize('О 1'), 'О1')
        self.assertNotEqual(normalize('0,3'), normalize('03'))

    def test_evaluation_requires_review_and_matching_source(self):
        recognition = {'source_id': 'source', 'pages': [{'fields': [
            {'id': '1:answer_01', 'candidate': '03'},
            {'id': '1:answer_02', 'candidate': '2'}]}]}
        corrections = {'source_id': 'source', 'fields': [
            {'id': '1:answer_01', 'corrected_text': '0,3', 'reviewed': True},
            {'id': '1:answer_02', 'corrected_text': '2', 'reviewed': False}]}
        result = evaluate(recognition, corrections)
        self.assertEqual(result['reviewed_fields'], 1)
        self.assertEqual(result['matching_fields'], 0)
        corrections['source_id'] = 'other'
        with self.assertRaises(ValueError):
            evaluate(recognition, corrections)

    def test_pipeline_keeps_source_and_does_not_confirm_ocr(self):
        class FakeOCR:
            def read(self, image):
                return '</script> − 0 , 3', .99

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared = root / 'prepared'
            prepared.mkdir()
            image = np.full((64, 200, 3), 255, dtype=np.uint8)
            cv2.rectangle(image, (20, 20), (40, 45), (0, 0, 0), -1)
            cv2.imwrite(str(prepared / 'crop.png'), image)
            source = {'template': 'oge_math_form1_v1', 'pages': [
                {'page': 1, 'status': 'prepared', 'original': 'crop.png', 'fields': {
                    'answer_01': {'image': 'crop.png'}, 'replacements': {'image': 'crop.png'}}},
                {'page': 2, 'status': 'needs_review'}]}
            manifest = prepared / 'manifest.json'
            manifest.write_text(json.dumps(source), encoding='utf-8')
            original = manifest.read_bytes()
            output = root / 'ocr'
            data = recognize(prepared, output, engine=FakeOCR())
            field = data['pages'][0]['fields'][0]
            self.assertEqual(manifest.read_bytes(), original)
            self.assertFalse(field['reviewed'])
            self.assertIsNone(field['corrected_text'])
            self.assertEqual(field['status'], 'needs_review')
            self.assertEqual(data['run_status'], 'complete')
            self.assertIn('\\u003c/script>', (output / 'review.html').read_text())
            self.assertTrue((output / field['original']).is_file())
            with self.assertRaises(ValueError):
                recognize(prepared, output, engine=FakeOCR())


if __name__ == '__main__':
    unittest.main()
