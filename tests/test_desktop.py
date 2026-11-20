
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

try:
    import tkinter as tk
    from oge_checker.desktop import DesktopApp
except ImportError:
    tk = None

from oge_checker.session import Session
from test_grading import complete_data, all_sevens_key


@unittest.skipUnless(tk is not None and (os.name == 'nt' or os.environ.get('DISPLAY')), 'Нужен графический экран')
class DesktopTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest('Графический экран недоступен')
        self.errors = patch('oge_checker.desktop.messagebox.showerror', side_effect=AssertionError('GUI error'))
        self.errors.start()
        self.app = DesktopApp(self.root)
        self.app.session = Session(complete_data(), Path('.'))
        self.app.session.set_key(all_sevens_key())
        self.app._refresh_pages()
        self.app.pages.selection_set('1')
        self.root.update()

    def tearDown(self):
        self.errors.stop()
        if hasattr(self, 'root'):
            self.app.shutdown()

    def test_edit_immediately_recalculates_and_enter_moves_without_confirmation(self):
        field = self.app._field()
        self.app.value.set('8')
        self.assertFalse(field['reviewed'])
        self.assertEqual(self.app.session.snapshot()['pages'][0]['grading']['total'], 18)
        self.app.confirm_field()
        self.root.update()
        self.assertFalse(field['reviewed'])
        self.assertEqual(self.app.current_field, '1:answer_02')
        self.assertEqual(self.app.session.snapshot()['pages'][0]['grading']['total'], 18)

    def test_failed_page_reason_without_answer_keys(self):
        self.app.session.key=None
        self.app.session.data['pages'].append({'page':36,'status':'needs_review','fields':[],
            'error':'Обрезаны опорные метки','original':'missing.png'})
        self.app._refresh_pages()
        self.app.pages.selection_set('36')
        self.root.update()
        self.assertIn('Обрезаны опорные метки',self.app.field_label.cget('text'))
        self.assertIn('Обрезаны опорные метки',self.app.page_status.cget('text'))
        self.assertIn('36',self.app.banner.cget('text'))

    def test_search_filters_pages_and_clear_restores_them(self):
        total=len(self.app.pages.get_children())
        self.app.search.set('no-such-student-xyz')
        self.root.update()
        self.assertEqual(self.app.pages.get_children(),())
        self.app.search.set('')
        self.root.update()
        self.assertEqual(len(self.app.pages.get_children()),total)
        self.assertTrue(self.app.pages.winfo_ismapped())

    def test_replacement_draft_survives_switching_page_and_save(self):
        self.app.replacement_text.delete('1.0', 'end')
        self.app.replacement_text.insert('1.0', '1=8')
        self.root.update()
        self.assertFalse(self.app._page()['replacements_reviewed'])
        self.app.replacements_checked.set(True)
        self.app._save_replacements()
        self.assertEqual(self.app.session.snapshot()['pages'][0]['grading']['total'], 18)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'project.json'
            self.app.session.save(path)
            self.assertEqual(Session.open(path).snapshot()['pages'][0]['grading']['total'], 18)

    def test_open_existing_demo_project_and_render(self):
        project = Path('data/processed/desktop_demo/project.json')
        if not project.is_file():
            self.skipTest('Демонстрационный проект ещё не создан')
        self.app.open_path(project)
        self.root.update()
        self.assertEqual(len(self.app.pages.get_children()), 5)
        self.assertEqual(len(self.app.fields.get_children()), 23)
        self.assertTrue(self.app.session.key['demo'])
        self.assertIn('ДЕМО', self.app.banner.cget('text'))
        self.assertIsNotNone(self.app.photo)
        if os.name != 'nt':
            from PIL import ImageGrab
            ImageGrab.grab(xdisplay=os.environ.get('DISPLAY')).save('/tmp/oge-desktop-preview.png')

    def test_background_pdf_pipeline_keeps_window_responsive(self):
        pdf = Path('data/raw/full_pdf.pdf')
        if not pdf.is_file():
            self.skipTest('Нет локального PDF для интеграционной проверки')
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'new_project'
            self.app._start_worker(pdf, target, [1])
            ticks = 0
            deadline = time.monotonic() + 45
            while self.app.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.01)
                ticks += 1
            self.assertFalse(self.app.busy, 'OCR не завершился за 45 секунд')
            self.root.update()
            self.assertGreater(ticks, 2)
            self.assertTrue((target / 'project.json').is_file())
            self.assertEqual(len(self.app.session.data['pages']), 1)
            self.assertEqual(len(self.app.session.data['pages'][0]['fields']), 23)
            self.assertFalse(any(field['reviewed'] for field in self.app.session.data['pages'][0]['fields']))

    def test_key_editor_preserves_leading_zero_and_demo_status(self):
        from oge_checker.key_editor import KeyEditor
        from oge_checker.grading import demo_key
        key = demo_key()
        key['variants']['demo']['1']['accepted'] = ['007', '-0,5']
        editor = KeyEditor(self.root, lambda key: None, key)
        try:
            self.root.update()
            saved = editor.build_key()
            self.assertTrue(saved['demo'])
            self.assertEqual(saved['variants']['demo']['1']['accepted'], ['007', '-0,5'])
        finally:
            editor.destroy()

    def test_standalone_key_editor_and_batch_variant(self):
        key = all_sevens_key()
        key['variants']['other'] = key['variants']['demo'].copy()
        self.app.apply_key(key)
        self.app.variant.set('other')
        self.app.set_batch_variant()
        self.assertTrue(all(p['variant'] == 'other' for p in self.app.session.data['pages']))
        self.app.session = None
        self.app.apply_key(key)
        self.assertEqual(self.app.pending_key, key)

    def test_edit_without_variant_and_filter_does_not_leave_hidden_field(self):
        key = all_sevens_key()
        key.pop('default_variant')
        self.app.session.set_key(key)
        self.app.value.set('8')
        self.assertEqual(self.app._field()['corrected_text'], '8')
        self.assertIsNone(self.app.session.snapshot()['pages'][0]['grading']['total'])
        for field in self.app._page()['fields']:
            field['corrected_text'] = field['candidate']
        self.app.suspect_only.set(True)
        self.app._refresh_fields()
        self.root.update()
        self.assertIsNone(self.app.current_field)
        self.assertEqual(self.app.value.get(), '')
