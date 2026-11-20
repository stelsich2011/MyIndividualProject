from tkinter import ttk
import tkinter.font as tkfont

def apply_theme(root):
    bg='#f3f6fb';ink='#192a43';muted='#61718a';accent='#2563eb'
    root.configure(background=bg)
    tkfont.nametofont('TkDefaultFont').configure(family='Segoe UI',size=10)
    tkfont.nametofont('TkTextFont').configure(family='Segoe UI',size=10)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',background=bg,foreground=ink,font=('Segoe UI',10))
    style.configure('TFrame',background=bg)
    style.configure('TLabel',background=bg)
    style.configure('Title.TLabel',font=('Segoe UI',23,'bold'))
    style.configure('Subtitle.TLabel',foreground=muted)
    style.configure('Section.TLabel',font=('Segoe UI',12,'bold'))
    style.configure('Demo.TLabel',background='#e8efff',foreground='#274779',padding=(14,10))
    style.configure('TButton',padding=(12,8),background='white',bordercolor='#dbe3ef',relief='flat')
    style.map('TButton',background=[('active','#e8efff')])
    style.configure('Primary.TButton',background=accent,foreground='white',bordercolor=accent)
    style.map('Primary.TButton',background=[('disabled','#a9badb'),('active','#1d4ed8')],foreground=[('disabled','#eef2fa'),('!disabled','white')])
    style.configure('TEntry',padding=7,fieldbackground='white',bordercolor='#dbe3ef')
    style.configure('Treeview',background='white',fieldbackground='white',foreground=ink,rowheight=34,borderwidth=0)
    style.configure('Treeview.Heading',background='#eaf0f8',foreground=muted,font=('Segoe UI',10,'bold'),padding=(8,9),relief='flat')
    style.map('Treeview',background=[('selected','#dce9ff')],foreground=[('selected','#143e80')])
    style.configure('TNotebook',background=bg,borderwidth=0)
    style.configure('TNotebook.Tab',padding=(16,10),background='#e9eef6')
    style.map('TNotebook.Tab',background=[('selected','white')],foreground=[('selected',accent)])
    style.configure('Horizontal.TProgressbar',background=accent,troughcolor='#e1e8f3',borderwidth=0)

def scroll_table(table):
    pass
    frame=ttk.Frame(table.master)
    frame.pack(fill='both',expand=True)
    vertical=ttk.Scrollbar(frame,orient='vertical',command=table.yview)
    horizontal=ttk.Scrollbar(frame,orient='horizontal',command=table.xview)
    table.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
    vertical.pack(side='right',fill='y');horizontal.pack(side='bottom',fill='x')
    table.pack(in_=frame,fill='both',expand=True)
    table.tk.call('raise',table._w)
