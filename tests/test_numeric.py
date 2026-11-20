from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import shutil
import json

import cv2
import numpy as np

from oge_checker.digits import combine_numeric, features, NumericOCR, split_symbols, has_small_separator
from oge_checker.grid import grid_rows, refine_boxes
from oge_checker.template import fields
from oge_checker.image_io import write_image


class NumericTests(unittest.TestCase):
    def test_pipeline_keeps_raw_text_and_handles_numeric_failure(self):
        from oge_checker.recognize import recognize
        class Digits:
            def __init__(self,fail): self.fail=fail
            def read(self,image):
                if self.fail: raise ValueError('classifier unavailable')
                return {'candidate':'12','agreements':[1.,1.],'distances':[.5,.5],'boxes':[]}
        class Engine:
            def __init__(self,fail): self.numeric=Digits(fail)
            def read(self,image): return '72',.99
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            image=np.full((62,859),255,np.uint8)
            cv2.rectangle(image,(20,12),(40,48),0,-1)
            cv2.rectangle(image,(75,12),(95,48),0,-1)
            write_image(root/'answer.png',image)
            write_image(root/'blank.png',np.full((196,1846),255,np.uint8))
            manifest={'template':'oge_math_form1_v1','pages':[{'page':1,'status':'prepared','original':'answer.png','fields':{
                'answer_01':{'image':'answer.png'},'replacements':{'image':'blank.png'}}}]}
            (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            for fail in (False,True):
                data=recognize(root,root/str(fail),engine=Engine(fail))
                field=data['pages'][0]['fields'][0]
                self.assertEqual(field['raw_text'],'72')
                self.assertEqual(field['candidate'],'72' if fail else '12')
                self.assertFalse(field['reviewed'])
                self.assertTrue(field['warnings'])
                self.assertEqual(data['run_status'],'complete')

    def test_only_supported_edits_and_leading_zeros(self):
        self.assertEqual(combine_numeric('72','12',[1.,1.],[.8,.8]),'12')
        self.assertEqual(combine_numeric('72','12',[.2,1.],[4.,.8]),'72')
        self.assertEqual(combine_numeric('03','0,3',[1.,1.,1.],[1.,1.,1.]),'0,3')
        self.assertEqual(combine_numeric('007','007',[1.]*3,[1.]*3),'007')
        self.assertEqual(combine_numeric('0.25','025',[1.]*3,[.5]*3),'0.25')
        self.assertEqual(combine_numeric('0,25','025',[1.]*3,[.5]*3),'0,25')
        boxes=[[10,10,20,35],[110,10,20,35],[160,10,20,35]]
        self.assertEqual(combine_numeric('0.25','025',[1.]*3,[.5]*3,boxes=boxes,small_separators=[[75,42]]),'0.25')
        self.assertEqual(combine_numeric('025.','025',[1.]*3,[.5]*3,boxes=boxes,small_separators=[[20,42]]),'025')
        self.assertEqual(combine_numeric('7','-7',[1.,1.],[1.,1.]),'-7')

    def test_units_special_notation_and_bad_grammar_are_preserved(self):
        for value in ('120см2','10°','3%','2)3)1)','12²','12м'):
            self.assertEqual(combine_numeric(value,'120',[1.]*3,[.5]*3),value)
        for value in ('1,,2','--12',',12','12,'):
            self.assertEqual(combine_numeric('12',value,[1.]*len(value),[.1]*len(value)),'12')

    def test_feature_dimension_and_blank_grid(self):
        image=np.zeros((30,20),np.uint8)
        cv2.line(image,(8,2),(8,27),255,2)
        vector=features(image)
        self.assertEqual(vector.shape,(326,))
        self.assertTrue(np.all(np.isfinite(vector)))
        blank=np.full((62,859),255,np.uint8)
        for x in range(5,859,50):
            for y in range(4,57,7):
                cv2.circle(blank,(x,y),1,0,-1)
        self.assertEqual(split_symbols(blank),[])
        self.assertFalse(has_small_separator(blank))
        cv2.circle(blank,(77,42),1,0,-1)
        self.assertTrue(has_small_separator(blank))
        self.assertEqual(combine_numeric('0.25','025',[1.]*3,[.5]*3,allow_separator_deletion=not has_small_separator(blank)),'0.25')

    def test_model_loads_from_unicode_path(self):
        source=Path(__file__).resolve().parents[1]/'src/oge_checker/models'
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'Модель с пробелами'
            target.mkdir()
            for filename in ('digits_svm.xml','digits_neighbors.npz'):
                shutil.copyfile(source/filename,target/filename)
            model=NumericOCR(target)
            self.assertEqual(model.read(np.full((62,859),255,np.uint8))['candidate'],'')

    def test_grid_adjusts_shifted_rows_using_printed_dots(self):
        image=np.full((2800,2000),255,np.uint8)
        for top in (1135,1205):
            for y in (top,top+46):
                for x in range(1580,1910,7):
                    cv2.circle(image,(x,y),1,0,-1)
        rows=grid_rows(image,(1580,1070,1910,1290),2)
        self.assertEqual(len(rows),2)
        self.assertLessEqual(abs(rows[0][0]-(1135-9)),2)

    def test_right_fallback_is_idempotent(self):
        image=np.full((2800,2000,3),255,np.uint8)
        left=[(1130+i*68,1192+i*68) for i in range(17)]
        def detect(gray,area,count):
            return left if count==17 else []
        with patch('oge_checker.grid.grid_rows',side_effect=detect):
            first,_=refine_boxes(image,fields())
            second,_=refine_boxes(image,first)
        self.assertEqual(first,second)
        self.assertEqual(first['answer_18'][1],fields()['answer_18'][1]+22)
