"""Нативный интерфейс Tk для Linux и Windows. OCR выполняется в рабочем потоке."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import queue
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont

from PIL import Image, ImageTk

from .grading import demo_key, grade_page, parse_replacements
from .session import Session, read_json


class DesktopApp:
    def __init__(self, root):
        self.root = root
        self.session = None
        self.project_path = None
        self.current_page = None
        self.current_field = None
        self.loading = False
        self.busy = False
        self.events = queue.Queue()
        self.photo = None
        root.title('Проверка бланков ОГЭ')
        root.geometry('1280x860')
        root.minsize(1000, 700)
        tkfont.nametofont('TkDefaultFont').configure(size=11)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Treeview', rowheight=29)
        style.configure('Treeview.Heading', font=('TkDefaultFont', 10, 'bold'))
        style.configure('Title.TLabel', font=('TkDefaultFont', 17, 'bold'))
        style.configure('Demo.TLabel', foreground='#8a4200', background='#fff0d2', padding=10)
        self._build()
        root.bind('<Control-s>', lambda event: self.save_project())
        root.bind('<Control-o>', lambda event: self.open_project())
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.poll_id = root.after(100, self._poll)

    def _button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command)
        button.pack(side='left', padx=(0, 7), pady=5)
        self.buttons.append(button)
        return button

    def _build(self):
        self.buttons = []
        top = ttk.Frame(self.root, padding=(14, 10))
        top.pack(fill='x')
        ttk.Label(top, text='Проверка бланков ОГЭ', style='Title.TLabel').pack(anchor='w')
        toolbar = ttk.Frame(top)
        toolbar.pack(fill='x', pady=(6, 0))
        self._button(toolbar, 'Новый из PDF', self.new_pdf)
        self._button(toolbar, 'Открыть проект / OCR', self.open_project)
        self._button(toolbar, 'Импорт правок', self.import_corrections)
        self._button(toolbar, 'Сохранить проект', self.save_project)
        self._button(toolbar, 'Экспорт Excel', self.export_excel)
        keys = ttk.Frame(top)
        keys.pack(fill='x')
        self._button(keys, 'Загрузить ключи', self.load_key)
        self._button(keys, 'Создать случайные ключи', self.create_demo)
        self.key_label = ttk.Label(keys, text='Ключи не загружены')
        self.key_label.pack(side='left', padx=10)
        self.banner = ttk.Label(top, text='Откройте проект или создайте новый из PDF.', style='Demo.TLabel')
        self.banner.pack(fill='x', pady=(8, 0))
        panes = ttk.Panedwindow(self.root, orient='horizontal')
        panes.pack(fill='both', expand=True, padx=14)
        left = ttk.Frame(panes)
        right = ttk.Frame(panes)
        panes.add(left, weight=1)
        panes.add(right, weight=4)
        ttk.Label(left, text='Бланки').pack(anchor='w', pady=5)
        self.pages = ttk.Treeview(left, columns=('number', 'name', 'review'), show='headings', selectmode='browse')
        for key, title, width in [('number', 'Стр.', 45), ('name', 'Ученик', 170), ('review', 'Поля', 60)]:
            self.pages.heading(key, text=title)
            self.pages.column(key, width=width, stretch=key == 'name')
        self.pages.pack(fill='both', expand=True)
        self.pages.bind('<<TreeviewSelect>>', self._select_page)
        notebook = ttk.Notebook(right)
        notebook.pack(fill='both', expand=True, padx=(12, 0))
        review = ttk.Frame(notebook, padding=10)
        replacements = ttk.Frame(notebook, padding=10)
        results = ttk.Frame(notebook, padding=10)
        notebook.add(review, text='1. Поля и ответы')
        notebook.add(replacements, text='2. Замены и вариант')
        notebook.add(results, text='3. Результаты')
        self.fields = ttk.Treeview(review, columns=('label', 'candidate', 'value', 'checked', 'points'), show='headings', height=9, selectmode='browse')
        for key, title, width in [('label', 'Поле', 110), ('candidate', 'Кандидат OCR', 145),
                                  ('value', 'Ручное значение', 160), ('checked', 'Проверено', 85), ('points', 'Балл', 60)]:
            self.fields.heading(key, text=title)
            self.fields.column(key, width=width)
        self.fields.pack(fill='both', expand=True)
        self.fields.bind('<<TreeviewSelect>>', self._select_field)
        self.field_label = ttk.Label(review, text='Выберите поле в таблице')
        self.field_label.pack(anchor='w', pady=(10, 3))
        self.canvas = tk.Canvas(review, height=105, background='white', highlightthickness=1, highlightbackground='#d5dce4')
        self.canvas.pack(fill='x')
        self.canvas.bind('<Configure>', lambda event: self._render_field())
        editor = ttk.Frame(review)
        editor.pack(fill='x', pady=8)
        self.value = tk.StringVar()
        self.value.trace_add('write', self._edit_value)
        self.entry = ttk.Entry(editor, textvariable=self.value, font=('TkDefaultFont', 16))
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', lambda event: self.confirm_field())
        ttk.Button(editor, text='Подтвердить →', command=self.confirm_field).pack(side='left', padx=8)
        ttk.Button(editor, text='Скан целиком', command=self.show_scan).pack(side='left')
        ttk.Label(review, text='Enter подтверждает поле и переходит к следующему. Пустой ответ тоже нужно подтвердить.').pack(anchor='w')
        ttk.Label(replacements, text='Вариант этой работы').pack(anchor='w')
        self.variant = tk.StringVar()
        self.variant_combo = ttk.Combobox(replacements, textvariable=self.variant, state='readonly')
        self.variant_combo.pack(anchor='w', pady=6)
        self.variant_combo.bind('<<ComboboxSelected>>', self._set_variant)
        ttk.Button(replacements, text='Показать блок замены на скане', command=self.show_replacements).pack(anchor='w', pady=8)
        ttk.Label(replacements, text='Введите окончательные замены: по одной строке номер=ответ, например 12=3.\nЕсли блок пустой, оставьте поле пустым. При нескольких записях выберите окончательную вручную.').pack(anchor='w', pady=8)
        self.replacement_text = tk.Text(replacements, height=8, width=50, font=('TkDefaultFont', 13), undo=True)
        self.replacement_text.pack(fill='x')
        self.replacement_text.bind('<<Modified>>', self._edit_replacements)
        self.replacements_checked = tk.BooleanVar()
        ttk.Checkbutton(replacements, text='Я проверил блок замены и ввёл все окончательные исправления',
                        variable=self.replacements_checked, command=self._save_replacements).pack(anchor='w', pady=12)
        ttk.Button(replacements, text='Применить замены', command=self._save_replacements).pack(anchor='w')
        self.page_status = ttk.Label(replacements, text='', wraplength=650)
        self.page_status.pack(anchor='w', pady=14)
        self.results = ttk.Treeview(results, columns=('page', 'name', 'total', 'provisional', 'maximum', 'status'), show='headings')
        for key, title, width in [('page', 'Стр.', 45), ('name', 'Ученик', 150), ('total', 'Итог', 55),
                                  ('provisional', 'Предвар.', 85), ('maximum', 'Макс.', 55), ('status', 'Статус', 290)]:
            self.results.heading(key, text=title)
            self.results.column(key, width=width)
        self.results.pack(fill='both', expand=True)
        ttk.Label(results, text='Итог появляется после проверки всех ответов и блока замены.\nДЕМО-баллы по случайным ключам не являются результатами ОГЭ.\nЗадания с развёрнутым решением приложение пока не оценивает.').pack(anchor='w', pady=12)
        bottom = ttk.Frame(self.root, padding=(14, 10))
        bottom.pack(fill='x')
        self.status = tk.StringVar(value='Готово')
        ttk.Label(bottom, textvariable=self.status).pack(side='left', fill='x', expand=True)
        self.progress = ttk.Progressbar(bottom, mode='indeterminate', length=170)
        self.progress.pack(side='right')

    def _require_session(self):
        if self.busy:
            return False
        if self.session is None:
            messagebox.showinfo('Нет проекта', 'Сначала откройте данные OCR или создайте проект из PDF.', parent=self.root)
            return False
        return True

    def _can_leave(self):
        if self.busy:
            messagebox.showinfo('Идёт обработка', 'Дождитесь завершения обработки PDF.', parent=self.root)
            return False
        if self.session and self.session.dirty:
            decision = messagebox.askyesnocancel('Сохранение', 'Сохранить изменения проекта?', parent=self.root)
            if decision is None:
                return False
            if decision and not self.save_project():
                return False
        return True

    def open_project(self):
        if not self._can_leave():
            return
        path = filedialog.askopenfilename(parent=self.root, title='Проект или завершённые данные OCR', filetypes=[('JSON', '*.json')])
        if path:
            self.open_path(Path(path))

    def open_path(self, path):
        try:
            session = Session.open(path)
            self.project_path = Path(path) if read_json(path).get('desktop_project_version') == 1 else None
            self.session = session
            self.current_page = self.current_field = None
            self._refresh_pages()
            self._refresh_results()
            if self.pages.get_children():
                self.pages.selection_set(self.pages.get_children()[0])
            self.status.set(f'Открыто: {path}')
        except Exception as exc:
            self._error(exc)

    def import_corrections(self):
        if not self._require_session():
            return
        path = filedialog.askopenfilename(parent=self.root, title='Ручные правки corrections.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                self.session.load_corrections(path)
                self._refresh_pages()
                self._refresh_fields()
                self._refresh_results()
                self.status.set('Ручные правки загружены. Сохраните проект.')
            except Exception as exc:
                self._error(exc)

    def save_project(self):
        if not self._require_session():
            return False
        path = self.project_path or filedialog.asksaveasfilename(parent=self.root, title='Сохранить desktop-проект',
                    initialfile='project.json', defaultextension='.json', filetypes=[('JSON', '*.json')])
        if not path:
            return False
        try:
            self.session.save(Path(path))
            self.project_path = Path(path)
            self.status.set(f'Проект сохранён: {path}')
            return True
        except Exception as exc:
            self._error(exc)
            return False

    def export_excel(self):
        if not self._require_session():
            return
        path = filedialog.asksaveasfilename(parent=self.root, title='Экспорт таблицы', initialfile='students.xlsx',
                                            defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
        if path:
            try:
                self.session.export_excel(Path(path))
                self.status.set(f'Excel сохранён: {path}')
            except Exception as exc:
                self._error(exc)

    def load_key(self):
        if not self._require_session():
            return
        path = filedialog.askopenfilename(parent=self.root, title='Ключи ответов', filetypes=[('JSON', '*.json')])
        if path:
            try:
                self.session.set_key(read_json(path))
                self._refresh_results()
                self._refresh_fields()
            except Exception as exc:
                self._error(exc)

    def create_demo(self):
        if not self._require_session():
            return
        path = filedialog.asksaveasfilename(parent=self.root, title='Создать демонстрационные ключи',
                    initialfile='demo_answers.json', defaultextension='.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                key = demo_key()
                Path(path).write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding='utf-8')
                self.session.set_key(key)
                self._refresh_results()
                self._refresh_fields()
                self.status.set('Созданы случайные ключи. Результаты помечены ДЕМО.')
            except Exception as exc:
                self._error(exc)

    def _page(self):
        if self.session is None or self.current_page is None:
            return None
        return next((page for page in self.session.data['pages'] if page['page'] == self.current_page), None)

    def _field(self):
        page = self._page()
        return next((field for field in page['fields'] if field['id'] == self.current_field), None) if page else None

    @staticmethod
    def _student(page):
        values = {field['name']: field.get('corrected_text') if field.get('corrected_text') is not None else field['candidate'] for field in page['fields']}
        return ' '.join(values.get(key, '') for key in ('surname', 'first_name')).strip() or 'Не распознано'

    def _refresh_pages(self):
        if self.session is None:
            return
        selected = self.pages.selection()
        self.pages.delete(*self.pages.get_children())
        for page in self.session.data['pages']:
            count = sum(field.get('reviewed') is True for field in page['fields'])
            self.pages.insert('', 'end', iid=str(page['page']), values=(page['page'], self._student(page), f'{count}/{len(page["fields"])}'))
        if selected and self.pages.exists(selected[0]):
            self.pages.selection_set(selected[0])

    def _select_page(self, event=None):
        selection = self.pages.selection()
        if not selection:
            return
        if self.current_page == int(selection[0]):
            return
        self.current_page = int(selection[0])
        self.current_field = None
        page = self._page()
        self.loading = True
        self.variant.set(page.get('variant') or (self.session.key or {}).get('default_variant') or '')
        self.replacement_text.delete('1.0', 'end')
        self.replacement_text.insert('1.0', page.get('replacement_draft',
            '\n'.join(f'{number}={answer}' for number, answer in page.get('replacement_answers', {}).items())))
        self.replacement_text.edit_modified(False)
        self.replacements_checked.set(page.get('replacements_reviewed') is True)
        self.loading = False
        self._refresh_fields()
        self._refresh_results()
        if self.fields.get_children():
            self.fields.selection_set(self.fields.get_children()[0])
        else:
            self.value.set('')
            self.canvas.delete('all')
            self.field_label.configure(text='Метки не найдены: откройте исходный скан и проверьте тип бланка.')

    def _refresh_fields(self):
        page = self._page()
        if page is None:
            return
        selected = self.current_field
        self.fields.delete(*self.fields.get_children())
        points = {}
        if self.session.key:
            points = {task['number']: task['points'] for task in grade_page(page, self.session.key)['tasks']}
        for field in page['fields']:
            number = int(field['name'][7:]) if field['name'].startswith('answer_') else None
            self.fields.insert('', 'end', iid=field['id'], values=(field['label'], field['candidate'],
                field.get('corrected_text') if field.get('corrected_text') is not None else '',
                'Да' if field.get('reviewed') else 'Нет', points.get(number) if points.get(number) is not None else '—'))
        if selected and self.fields.exists(selected):
            self.fields.selection_set(selected)

    def _select_field(self, event=None):
        selection = self.fields.selection()
        if not selection:
            return
        self.current_field = selection[0]
        field = self._field()
        if field is None:
            return
        self.loading = True
        self.value.set(field.get('corrected_text') if field.get('corrected_text') is not None else field['candidate'])
        self.loading = False
        self.field_label.configure(text=f'{field["label"]} — исходный фрагмент (без удаления пунктира)')
        self._render_field()

    def _render_field(self):
        field = self._field()
        if field is None:
            return
        self.canvas.delete('all')
        try:
            with Image.open(self.session.root / field['original']) as source:
                image = source.convert('RGB')
            image.thumbnail((max(200, self.canvas.winfo_width() - 20), 95))
            self.photo = ImageTk.PhotoImage(image, master=self.root)
            self.canvas.create_image(10, 5, anchor='nw', image=self.photo)
        except OSError:
            self.canvas.create_text(15, 30, anchor='w', text='Фрагмент не найден. Проверьте расположение папок проекта.')

    def _edit_value(self, *args):
        field = self._field()
        if self.loading or field is None or self.busy:
            return
        field['corrected_text'] = self.value.get()
        field['reviewed'] = False
        field['status'] = 'needs_review'
        self.session.dirty = True
        # Не перестраиваем таблицу при вводе: это сбросило бы выделение и курсор.
        self.fields.set(field['id'], 'value', self.value.get())
        self.fields.set(field['id'], 'checked', 'Нет')
        self.fields.set(field['id'], 'points', '—')
        self._refresh_results()

    def confirm_field(self):
        if self.busy:
            return
        field = self._field()
        if field is None:
            return
        field.update(corrected_text=self.value.get(), reviewed=True, status='human_reviewed')
        self.session.dirty = True
        children = list(self.fields.get_children())
        position = children.index(field['id'])
        self._refresh_fields()
        self._refresh_pages()
        self._refresh_results()
        if position + 1 < len(children):
            self.fields.selection_set(children[position + 1])
            self.fields.see(children[position + 1])
        self.entry.focus_set()

    def _set_variant(self, event=None):
        page = self._page()
        if page and not self.loading and not self.busy:
            page['variant'] = self.variant.get()
            self.session.dirty = True
            self._refresh_results()
            self._refresh_fields()

    def _edit_replacements(self, event=None):
        if not self.replacement_text.edit_modified():
            return
        self.replacement_text.edit_modified(False)
        page = self._page()
        if self.loading or page is None or self.busy:
            return
        page['replacement_draft'] = self.replacement_text.get('1.0', 'end-1c')
        page['replacements_reviewed'] = False
        self.replacements_checked.set(False)
        self.session.dirty = True
        self._refresh_results()

    def _save_replacements(self):
        page = self._page()
        if page is None or self.busy:
            return
        try:
            changes = parse_replacements(self.replacement_text.get('1.0', 'end-1c'))
            page['replacement_answers'] = changes
            page['replacement_draft'] = self.replacement_text.get('1.0', 'end-1c')
            page['replacements_reviewed'] = self.replacements_checked.get()
            self.session.dirty = True
            self._refresh_results()
            self._refresh_fields()
        except ValueError as exc:
            page['replacements_reviewed'] = False
            self.replacements_checked.set(False)
            self._refresh_results()
            self._error(exc)

    def _refresh_results(self):
        if self.session is None:
            return
        key = self.session.key
        self.variant_combo.configure(values=list(key['variants']) if key else [])
        page = self._page()
        if page is not None:
            self.variant.set(page.get('variant') or (key or {}).get('default_variant') or '')
        self.key_label.configure(text=key.get('title', 'Ключи загружены') if key else 'Ключи не загружены')
        self.banner.configure(text='ДЕМО: ключи содержат случайные цифры. Баллы не являются результатами ОГЭ.'
            if key and key['demo'] else 'Проверяются краткие ответы 1–19. Перед итогом подтвердите ответы и блок замены.')
        self.results.delete(*self.results.get_children())
        for page in self.session.data['pages']:
            score = grade_page(page, key) if key else {}
            show = lambda value: '—' if value is None else value
            self.results.insert('', 'end', values=(page['page'], self._student(page), show(score.get('total')),
                show(score.get('provisional')), show(score.get('maximum')), score.get('status', 'Загрузите ключи')))
            if page['page'] == self.current_page:
                self.page_status.configure(text=score.get('status', 'Загрузите ключи'))

    def _show_image(self, relative_path, title):
        if self.session is None or not relative_path:
            return
        try:
            with Image.open(self.session.root / relative_path) as source:
                image = source.convert('RGB')
            # Прокрутка сохраняет возможность проверить мелкий текст в исходном масштабе.
            window = tk.Toplevel(self.root)
            window.title(title)
            window.geometry('1000x750')
            canvas = tk.Canvas(window, background='#e4e8ed')
            vertical = ttk.Scrollbar(window, orient='vertical', command=canvas.yview)
            horizontal = ttk.Scrollbar(window, orient='horizontal', command=canvas.xview)
            canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            vertical.pack(side='right', fill='y')
            horizontal.pack(side='bottom', fill='x')
            canvas.pack(fill='both', expand=True)
            window.photo = ImageTk.PhotoImage(image, master=window)
            canvas.create_image(0, 0, anchor='nw', image=window.photo)
            canvas.configure(scrollregion=(0, 0, image.width, image.height))
        except OSError as exc:
            self._error(exc)

    def show_scan(self):
        page = self._page()
        if page:
            self._show_image(page.get('original'), f'Страница {page["page"]}')

    def show_replacements(self):
        page = self._page()
        if page:
            self._show_image(page.get('replacements'), 'Блок замены ответов')

    def new_pdf(self):
        if not self._can_leave():
            return
        pdf = filedialog.askopenfilename(parent=self.root, title='Выберите PDF со сканами', filetypes=[('PDF', '*.pdf')])
        if not pdf:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title('Подготовка PDF')
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=Path(pdf).name).pack(anchor='w')
        ttk.Label(frame, text='Страницы, например 1-3,44,88. Пусто — весь PDF.').pack(anchor='w', pady=10)
        pages = ttk.Entry(frame, width=45)
        pages.pack(fill='x')
        pages.insert(0, '1-3')
        def start():
            try:
                from .__main__ import parse_pages
                numbers = parse_pages(pages.get()) if pages.get().strip() else None
            except argparse.ArgumentTypeError as exc:
                messagebox.showerror('Страницы', str(exc), parent=dialog)
                return
            target = filedialog.askdirectory(parent=dialog, title='Папка для нового проекта')
            if not target:
                return
            # Каждый запуск получает новую папку; предыдущие файлы не перезаписываются.
            folder = Path(target) / datetime.now().strftime('oge_%Y%m%d_%H%M%S_%f')
            dialog.destroy()
            self._start_worker(Path(pdf), folder, numbers)
        ttk.Button(frame, text='Выбрать папку и начать', command=start).pack(pady=(15, 0))

    def _start_worker(self, pdf, folder, numbers):
        self.busy = True
        self.progress.start(12)
        for button in self.buttons:
            button.state(['disabled'])
        self.entry.state(['disabled'])
        self.status.set('Подготовка сканов…')
        def worker():
            try:
                from .pipeline import prepare
                from .recognize import recognize
                prepare(pdf, folder / 'prepared', numbers)
                self.events.put(('status', 'Распознавание… При первом запуске загружается модель OCR.'))
                recognize(folder / 'prepared', folder / 'ocr')
                session = Session.open(folder / 'ocr/recognition.json')
                session.save(folder / 'project.json')
                self.events.put(('done', folder / 'project.json'))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'status':
                    self.status.set(value)
                else:
                    self.busy = False
                    self.progress.stop()
                    for button in self.buttons:
                        button.state(['!disabled'])
                    self.entry.state(['!disabled'])
                    if kind == 'done':
                        self.open_path(value)
                    else:
                        self._error(value)
        except queue.Empty:
            pass
        self.poll_id = self.root.after(100, self._poll)

    def shutdown(self):
        self.root.after_cancel(self.poll_id)
        self.root.destroy()

    def _error(self, error):
        self.status.set(f'Ошибка: {error}')
        messagebox.showerror('Ошибка', str(error), parent=self.root)

    def close(self):
        if self._can_leave():
            self.shutdown()


def main():
    parser = argparse.ArgumentParser(description='Desktop-приложение проверки бланков ОГЭ')
    parser.add_argument('--project', type=Path, help='Открыть desktop-проект или recognition.json')
    parser.add_argument('--self-test', action='store_true', help='Проверить окно, OCR и Excel и завершить работу')
    args = parser.parse_args()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        parser.exit(1, f'Не удалось открыть окно: {exc}\nЗапустите приложение в графическом сеансе Linux или Windows.\n')
    app = DesktopApp(root)
    if args.self_test:
        try:
            import cv2
            import numpy as np
            from .recognize import LocalOCR, normalize
            root.update()
            image = np.full((80, 240, 3), 255, dtype=np.uint8)
            cv2.putText(image, '123', (15, 58), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 0, 0), 3)
            raw, _ = LocalOCR().read(image)
            if normalize(raw) != '123':
                raise ValueError(f'Проверка OCR не прошла: {raw!r}')
            session = Session.open(args.project) if args.project else Session({
                'run_status': 'complete', 'source_id': 'self-test', 'source_manifest': '', 'pages': []}, Path.cwd())
            with tempfile.TemporaryDirectory(prefix='oge-check-') as temporary:
                session.export_excel(Path(temporary) / 'check.xlsx')
            print('self-test: OK (Tk, OCR, Excel)')
        except Exception as exc:
            app.shutdown()
            parser.exit(1, f'self-test: {exc}\n')
        app.shutdown()
        return
    if args.project:
        root.after(0, lambda: app.open_path(args.project))
    root.mainloop()


if __name__ == '__main__':
    main()
