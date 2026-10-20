import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from oge_checker.__main__ import parse_pages
from oge_checker.pipeline import align, detect_markers, prepare
from oge_checker.template import HEIGHT, WIDTH, MARKERS, fields


class PreparationTests(unittest.TestCase):
    def blank_form(self):
        image = np.full((HEIGHT, WIDTH, 3), 255, dtype=np.uint8)
        for x, y in MARKERS:
            x, y = round(x), round(y)
            cv2.rectangle(image, (x - 24, y - 24), (x + 24, y + 24), (0, 0, 0), -1)
        return image

    def test_alignment_corrects_perspective(self):
        image = self.blank_form()
        source = np.float32([[0, 0], [WIDTH, 0], [0, HEIGHT], [WIDTH, HEIGHT]])
        destination = np.float32([[25, 20], [WIDTH - 30, 5], [10, HEIGHT - 10], [WIDTH - 10, HEIGHT - 35]])
        distorted = cv2.warpPerspective(image, cv2.getPerspectiveTransform(source, destination),
                                       (WIDTH, HEIGHT), borderValue=(255, 255, 255))
        aligned, _ = align(distorted)
        np.testing.assert_allclose(detect_markers(aligned), MARKERS, atol=2)

    def test_missing_marker_requires_review(self):
        image = self.blank_form()
        x, y = map(round, MARKERS[0])
        image[y-30:y+30, x-30:x+30] = 255
        with self.assertRaises(ValueError):
            align(image)

    def test_all_crops_stay_inside_canvas(self):
        for name, (x1, y1, x2, y2) in fields().items():
            with self.subTest(name=name):
                self.assertTrue(0 <= x1 < x2 <= WIDTH)
                self.assertTrue(0 <= y1 < y2 <= HEIGHT)

    def test_existing_results_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            sentinel = folder / 'manual.json'
            sentinel.write_text('{}')
            with self.assertRaises(ValueError):
                prepare(Path('unused.pdf'), folder, [1])
            self.assertEqual(sentinel.read_text(), '{}')

    def test_page_selection(self):
        self.assertEqual(parse_pages('1-3,2,88'), [1, 2, 3, 88])


if __name__ == '__main__':
    unittest.main()
