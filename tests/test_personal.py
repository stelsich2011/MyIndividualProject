import unittest
import numpy as np
from oge_checker.personal import name_candidate, read_class, valid_class


class PersonalTests(unittest.TestCase):
    def test_language_hint_is_limited_to_ambiguous_first_name(self):
        self.assertEqual(name_candidate('ВуКТОРИЯ','first_name',.59),('ВИКТОРИЯ',True))
        self.assertEqual(name_candidate('CTENAH','first_name',.67),('СТЕПАН',True))
        self.assertEqual(name_candidate('ВУКТОРИЯ','surname',.59),('ВУКТОРИЯ',False))
        self.assertEqual(name_candidate('ВУКТОРИЯ','first_name',.95),('ВУКТОРИЯ',False))
        self.assertEqual(name_candidate('АМИНА','first_name',.4),('АМИНА',False))
        self.assertEqual(name_candidate('АБВГД','first_name',.4),('АБВГД',False))

    def test_class_context_preserves_grade_and_requires_image_reading(self):
        image=np.full((48,120),255,np.uint8); image[10:35,10:25]=0
        self.assertEqual(read_class('95',image,lambda _:('95',.99))[0],'95')
        self.assertEqual(read_class('95',image,lambda _:('9 Б',.7))[0],'9Б')
        self.assertEqual(read_class('95',image,lambda _:('8Б',.7))[0],'95')
        for value in ('9А','10Б','11В','09А'):
            self.assertEqual(read_class(value,image,lambda _:self.fail('Already valid'))[0],value)
        self.assertEqual(valid_class('gB'),'9В')
        self.assertIsNone(valid_class('95'))
        self.assertEqual(read_class('105',image,lambda _:('10Б',.7))[0],'10Б')

    def test_conflicting_class_letters_are_not_selected(self):
        image=np.full((48,120),255,np.uint8); image[10:35,10:25]=0
        readings=iter([('9Б',.9),('9В',.9),('95',.9)])
        self.assertEqual(read_class('95',image,lambda _:next(readings))[0],'95')
