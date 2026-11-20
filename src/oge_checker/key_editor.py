
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from .keys import HEADERS, key_from_rows, rows_from_key, write_template, load_key


class KeyEditor(tk.Toplevel):
    def __init__(self, parent, apply, key=None):
        super().__init__(parent)
        self.title('Ключи ответов — ручной ввод / Excel / CSV')
        self.geometry('840x760')
        self.apply_key = apply
        self.key = key
        self.demo = (key or {}).get('demo', False)
        self.title_value = tk.StringVar(value=(key or {}).get('title', 'Ключи ответов'))
        ttk.Entry(self, textvariable=self.title_value).pack(fill='x', padx=12, pady=8)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', padx=12)
        for label, callback in [('Импорт', self.import_file), ('Шаблон Excel/CSV', self.template),
                                ('Добавить вариант', self.add_variant), ('Удалить вариант', self.delete_variant)]:
            ttk.Button(toolbar, text=label, command=callback).pack(side='left', padx=3)
        ttk.Label(self, text='Выберите строку, измените ответ и нажмите «Записать строку». Альтернативы: 7|07.').pack(pady=8)
        self.table = ttk.Treeview(self, columns=HEADERS, show='headings', selectmode='browse')
        for header in HEADERS:
            self.table.heading(header, text=header)
            self.table.column(header, width=150)
        self.table.pack(fill='both', expand=True, padx=12)
        self.table.bind('<<TreeviewSelect>>', self.select)
        editor = ttk.Frame(self)
        editor.pack(fill='x', padx=12, pady=8)
        self.values = [tk.StringVar() for _ in HEADERS]
        for i, (header, value) in enumerate(zip(HEADERS, self.values)):
            ttk.Label(editor, text=header).grid(row=0, column=i)
            entry = ttk.Entry(editor, textvariable=value, width=18, state='readonly' if i < 2 else 'normal')
            entry.grid(row=1, column=i, padx=3)
            entry.bind('<Return>', self.commit)
        ttk.Button(editor, text='Записать строку →', command=self.commit).grid(row=1, column=4)
        footer = ttk.Frame(self)
        footer.pack(fill='x', padx=12, pady=12)
        ttk.Button(footer, text='Сохранить ключи JSON', command=self.save).pack(side='left')
        ttk.Button(footer, text='Применить к проекту', command=self.use).pack(side='right')
        self.fill(rows_from_key(key)[1:] if key else [['1', str(n), '', '1'] for n in range(1, 20)])

    def fill(self, rows):
        self.table.delete(*self.table.get_children())
        for row in rows:
            self.table.insert('', 'end', values=row)
        if self.table.get_children():
            self.table.selection_set(self.table.get_children()[0])
            self.select()

    def select(self, event=None):
        selected = self.table.selection()
        if selected:
            for variable, value in zip(self.values, self.table.item(selected[0], 'values')):
                variable.set(value)

    def commit(self, event=None):
        selected = self.table.selection()
        if selected:
            self.table.item(selected[0], values=[v.get() for v in self.values])
            following = self.table.next(selected[0])
            if following:
                self.table.selection_set(following)
                self.table.see(following)

    def build_key(self):

        selected = self.table.selection()
        if selected:
            self.table.item(selected[0], values=[v.get() for v in self.values])
        rows = [list(HEADERS)] + [self.table.item(i, 'values') for i in self.table.get_children()]
        key = key_from_rows(rows, self.title_value.get().strip() or 'Ключи ответов')
        key['demo'] = self.demo
        return key

    def add_variant(self):
        variant = simpledialog.askstring('Вариант', 'Номер или название нового варианта:', parent=self)
        if variant and variant.strip():
            variant = variant.strip()
            if any(self.table.item(i, 'values')[0] == variant for i in self.table.get_children()):
                messagebox.showerror('Вариант', 'Такой вариант уже существует', parent=self)
                return
            for n in range(1, 20):
                self.table.insert('', 'end', values=(variant, n, '', 1))

    def delete_variant(self):
        selected = self.table.selection()
        if selected:
            variant = self.table.item(selected[0], 'values')[0]
            for i in self.table.get_children():
                if self.table.item(i, 'values')[0] == variant:
                    self.table.delete(i)

    def import_file(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[('Ключи', '*.json *.xlsx *.csv')])
        if path:
            try:
                key = load_key(path)
                self.demo = key['demo']
                self.title_value.set(key.get('title', Path(path).stem))
                self.fill(rows_from_key(key)[1:])
            except Exception as exc:
                messagebox.showerror('Импорт ключей', str(exc), parent=self)

    def template(self):
        path = filedialog.asksaveasfilename(parent=self, initialfile='keys_template.xlsx',
            defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx'), ('CSV', '*.csv')])
        if path:
            try:
                write_template(path)
            except Exception as exc:
                messagebox.showerror('Шаблон', str(exc), parent=self)

    def save(self):
        try:
            key = self.build_key()
            path = filedialog.asksaveasfilename(parent=self, initialfile='answers.json', defaultextension='.json', filetypes=[('JSON', '*.json')])
            if path:
                Path(path).write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            messagebox.showerror('Ключи', str(exc), parent=self)

    def use(self):
        try:
            self.apply_key(self.build_key())
            self.destroy()
        except Exception as exc:
            messagebox.showerror('Ключи', str(exc), parent=self)
