import unittest
import numpy as np
from oge_checker.text_answers import canonical_word,refine_text

class TextAnswerTests(unittest.TestCase):
    def test_preserves_numbers_units_and_latin(self):
        for text in ('103','0,3','10км','MINECRAFT','StaringCraft','COH','x3'):
            self.assertEqual(canonical_word(text),text)
        self.assertEqual(canonical_word('СЫР0K'),'СЫРОК')
        self.assertEqual(canonical_word('TATYAЖ'),'ТАТУАЖ')

    def test_requires_agreement_and_preserves_punctuation(self):
        image=np.full((48,120),255,np.uint8)
        replies=iter([('СЫРОК',.8),('СЫР0К',.8)])
        self.assertEqual(refine_text('СЫР0K',image,lambda _:next(replies))[0],'СЫРОК')
        self.assertEqual(refine_text('СЫР0K-',image,lambda _:('СЫРОК',.99))[0],'СЫР0K-')

