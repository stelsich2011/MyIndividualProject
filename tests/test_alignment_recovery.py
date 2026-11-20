import json
from pathlib import Path
import tempfile
import unittest
import cv2
import numpy as np
from oge_checker.pipeline import align_with_diagnostics
from oge_checker.recognize import recognize
from oge_checker.grading import grade_page,demo_key
from oge_checker.session import Session
from oge_checker.grid import clean_recovered_grid,refine_recovered_boxes
from oge_checker.template import fields


class RecoveryTests(unittest.TestCase):
    def test_stretched_grid_removed_but_digit_and_decimal_kept(self):
        image=np.full((84,200),255,np.uint8)
        for x in (2,48,58,98,108,148,158,198):
            for y in (4,15,27,54,66,78):
                cv2.circle(image,(x,y),1,0,-1)
            cv2.line(image,(x,30),(x,48),0,1)
        cv2.line(image,(23,22),(23,65),0,3)
        cv2.circle(image,(78,60),2,0,-1)
        cleaned,removed=clean_recovered_grid(image)
        self.assertGreater(removed,0)
        self.assertTrue(np.all(cleaned[31:47,2]==255))
        self.assertEqual(cleaned[45,23],0)
        self.assertEqual(cleaned[60,78],0)

    def test_unrelated_page_is_not_accepted(self):
        image=np.full((1400,1000,3),255,np.uint8)
        cv2.putText(image,'NOT AN OGE FORM',(100,200),cv2.FONT_HERSHEY_SIMPLEX,2,(0,0,0),3)
        with self.assertRaises(ValueError): align_with_diagnostics(image)

    def test_failed_page_keeps_reason_scan_and_has_no_zero_grade(self):
        class UnusedOCR:
            def read(self,image): raise AssertionError('Failed page must not enter OCR')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);prepared=root/'prepared';prepared.mkdir()
            (prepared/'scan.png').write_bytes(b'scan-placeholder')
            manifest={'template':'oge_math_form1_v1','pages':[{'page':36,'status':'needs_review',
                      'error':'Обрезан край','original':'scan.png'}]}
            (prepared/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            result=recognize(prepared,root/'ocr',engine=UnusedOCR())
            page=result['pages'][0]
            self.assertEqual(page['error'],'Обрезан край')
            self.assertTrue((root/'ocr'/page['original']).is_file())
            self.assertEqual(result['processing_summary']['failed_pages'],[36])
            score=grade_page(page,demo_key())
            self.assertIsNone(score['total']);self.assertIsNone(score['provisional'])
            self.assertIn('Обрезан край',score['warnings'])
            session=Session(result,root/'ocr');session.save(root/'project.json')
            self.assertEqual(Session.open(root/'project.json').data['pages'][0]['error'],'Обрезан край')
            self.assertIn('Обрезан край',(root/'ocr/review.html').read_text(encoding='utf-8'))

    @unittest.skipUnless(Path('data/raw/full_pdf.pdf').is_file(),'Requires local scan fixture')
    def test_recovery_of_cropped_qr_and_faint_scans(self):
        import pymupdf
        with pymupdf.open('data/raw/full_pdf.pdf') as doc:
            for number,method in ((36,'printed_affine'),(38,'adaptive_markers'),(62,'adaptive_markers')):
                with self.subTest(page=number):
                    pix=doc[number-1].get_pixmap(dpi=300,colorspace=pymupdf.csRGB,alpha=False)
                    im=cv2.cvtColor(np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3),cv2.COLOR_RGB2BGR)
                    aligned,_,diagnostics=align_with_diagnostics(im)
                    self.assertEqual(aligned.shape[:2],(2800,2000))
                    self.assertEqual(diagnostics['method'],method)
                    self.assertTrue(diagnostics['grid']['left'] and diagnostics['grid']['right'])
                    boxes,grid=refine_recovered_boxes(aligned,fields())
                    self.assertEqual([len(side) for side in grid['replacement_rows']],[3,3])
                    self.assertGreater(boxes['replacements'][1],boxes['answer_17'][3])
                    for side in grid['replacement_rows']:
                        self.assertGreater(side[2][0],side[1][1])
