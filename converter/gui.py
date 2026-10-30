"""Russian ttk interface; all Tk calls stay on the main thread."""
import os
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .bridge import check_environment, convert
from .models import Cancelled, ConversionError, Options


class Application(tk.Tk):
    def __init__(self, check_startup=True):
        super().__init__()
        self.title('HTML Presentation Converter')
        self.geometry(f'940x{min(820, self.winfo_screenheight() - 100)}')
        self.minsize(780, 620)
        self.configure(background='#edf1f5')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background='#edf1f5', foreground='#24394b')
        style.configure('App.TFrame', background='#edf1f5')
        style.configure('Card.TFrame', background='white', bordercolor='#dce4eb', relief='solid', borderwidth=1)
        style.configure('White.TFrame', background='white')
        style.configure('Title.TLabel', font=('Segoe UI', 21, 'bold'), foreground='#18344a')
        style.configure('Muted.TLabel', foreground='#647789')
        style.configure('Card.TLabel', background='white')
        style.configure('CardTitle.TLabel', background='white', font=('Segoe UI', 11, 'bold'))
        style.configure('Section.TLabel', background='white', font=('Segoe UI', 10, 'bold'), foreground='#17675e')
        style.configure('Hint.TLabel', background='white', foreground='#6d7c89', font=('Segoe UI', 9))
        style.configure('Ready.TLabel', background='#e0eee8', foreground='#17675e', padding=(12, 6), font=('Segoe UI', 9))
        style.configure('Waiting.TLabel', background='#e3e8ee', foreground='#607386', padding=(12, 6), font=('Segoe UI', 9))
        style.configure('Error.TLabel', background='#f8e7e3', foreground='#a23e2d', padding=(12, 6), font=('Segoe UI', 9))
        style.configure('TButton', padding=(14, 9), background='#f5f7fa', bordercolor='#d3dce5')
        style.map('TButton', background=[('active', '#e9eff4')])
        style.configure('Accent.TButton', background='#17675e', foreground='white', bordercolor='#17675e', font=('Segoe UI', 10, 'bold'), padding=(20, 9))
        style.map('Accent.TButton', background=[('disabled', '#c6d7d3'), ('active', '#11574f')],
                  foreground=[('disabled', '#eff5f3'), ('!disabled', 'white')])
        style.configure('Link.TButton', background='#edf1f5', foreground='#17675e', borderwidth=0, padding=(0, 8))
        style.map('Link.TButton', background=[('active', '#edf1f5')])
        style.configure('White.TRadiobutton', background='white', padding=(0, 5), font=('Segoe UI', 11, 'bold'))
        style.map('White.TRadiobutton', background=[('active', 'white')])
        style.configure('White.TCheckbutton', background='white')
        style.map('White.TCheckbutton', background=[('active', 'white')])
        style.configure('TEntry', padding=(9, 7), fieldbackground='white', bordercolor='#d5dee6')
        style.configure('TCombobox', padding=(9, 6), fieldbackground='white', bordercolor='#d5dee6')
        style.map('TCombobox', fieldbackground=[('readonly', 'white')], foreground=[('readonly', '#24394b')])
        style.configure('TSpinbox', padding=(9, 6), fieldbackground='white', bordercolor='#d5dee6')
        style.configure('Horizontal.TProgressbar', background='#229381', troughcolor='#eef3f6', bordercolor='#eef3f6', lightcolor='#229381', darkcolor='#229381', borderwidth=0, thickness=7)
        style.configure('Vertical.TScrollbar', background='#c7d1db', troughcolor='#edf1f5', borderwidth=0, arrowsize=12)
        self.source = None
        self.result = None
        self.worker = None
        self.stop = threading.Event()
        self.events = queue.Queue()
        self.closing = False
        self.format_var = tk.StringVar(value='pdf')
        self.resolution_var = tk.StringVar(value='1600 × 900')
        self.aspect_var = tk.StringVar(value='Автоматически')
        self.count_var = tk.StringVar(value='')
        self.delay_var = tk.StringVar(value='500')
        self.selector_var = tk.StringVar()
        self.capture_var = tk.StringVar()
        self.key_var = tk.StringVar(value='ArrowRight')
        self.external_var = tk.BooleanVar(value=False)
        self.chrome_var = tk.StringVar()
        self.status_var = tk.StringVar(value='Выберите HTML-презентацию.')
        self.counter_var = tk.StringVar(value='Обработано слайдов: 0')
        self._inputs = []
        self._hint_labels = []
        self._build()
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.after(100, self.poll)
        if check_startup:
            self.after(150, self.check_browser)

    def _build(self):
        self.shell = ttk.Frame(self, style='App.TFrame')
        self.shell.place(relx=.5, y=24, anchor='n', width=892, height=740)
        self.shell.columnconfigure(0, weight=1)
        self.shell.rowconfigure(1, weight=1)
        header = ttk.Frame(self.shell, style='App.TFrame')
        header.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text='HTML Presentation Converter', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        self.browser_label = ttk.Label(header, text='Локальный экспорт', style='Waiting.TLabel')
        self.browser_label.grid(row=0, column=1, sticky='e', padx=(12, 0))
        ttk.Label(header, text='Из HTML в PDF или PowerPoint, слайд за слайдом', style='Muted.TLabel').grid(row=1, column=0, columnspan=2, sticky='w', pady=(6, 0))

        body_holder = ttk.Frame(self.shell, style='App.TFrame')
        body_holder.grid(row=1, column=0, sticky='nsew')
        body_holder.columnconfigure(0, weight=1)
        body_holder.rowconfigure(0, weight=1)
        self.body_canvas = tk.Canvas(body_holder, background='#edf1f5', borderwidth=0, highlightthickness=0, yscrollincrement=24)
        self.body_canvas.grid(row=0, column=0, sticky='nsew')
        self.body_scrollbar = ttk.Scrollbar(body_holder, orient='vertical', command=self.body_canvas.yview)
        self.body_scrollbar.grid(row=0, column=1, sticky='ns', padx=(8, 0))
        self.body_canvas.configure(yscrollcommand=self.body_scrollbar.set)
        body = ttk.Frame(self.body_canvas, style='App.TFrame')
        body.columnconfigure(0, weight=1)
        self._body_window = self.body_canvas.create_window(0, 0, window=body, anchor='nw')
        body.bind('<Configure>', self._update_scroll_region)
        self.body_canvas.bind('<Configure>', self._resize_body)
        self.bind('<Configure>', self._resize_shell, add='+')
        self.bind('<MouseWheel>', self._scroll_body, add='+')

        source = self._card(body, 0)
        source.columnconfigure(0, weight=1)
        ttk.Label(source, text='1  Исходная презентация', style='Section.TLabel').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 12))
        self.file_label = ttk.Label(source, text='Файл пока не выбран', style='CardTitle.TLabel', wraplength=500)
        self.file_label.grid(row=1, column=0, sticky='w')
        self.file_path_label = ttk.Label(source, text='Выберите презентацию в формате .html или .htm', style='Hint.TLabel', wraplength=500)
        self.file_path_label.grid(row=2, column=0, sticky='w', pady=(5, 0))
        self.choose_button = ttk.Button(source, text='Выбрать HTML…', command=self.choose_source)
        self.choose_button.grid(row=1, column=1, rowspan=2, sticky='e', padx=(18, 0))

        formats = self._card(body, 1)
        ttk.Label(formats, text='2  Формат результата', style='Section.TLabel').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 6))
        for column, (value, title) in enumerate((('pdf', 'PDF'), ('pptx', 'PowerPoint · PPTX'))):
            formats.columnconfigure(column, weight=1, uniform='format')
            option = ttk.Frame(formats, style='White.TFrame')
            option.grid(row=1, column=column, sticky='ew', padx=(0, 12) if column == 0 else (12, 0))
            radio = ttk.Radiobutton(option, text=title, variable=self.format_var, value=value, style='White.TRadiobutton')
            radio.grid(row=0, column=0, sticky='w')
            self._inputs.append((radio, 'normal'))
        ttk.Label(formats, text='Слайды сохраняются как изображения внутри PDF или PPTX.', style='Hint.TLabel').grid(row=2, column=0, columnspan=2, sticky='w', pady=(7, 0))

        settings = self._card(body, 2)
        for column in (0, 1):
            settings.columnconfigure(column, weight=1, uniform='settings')
        ttk.Label(settings, text='3  Настройки экспорта', style='Section.TLabel').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))
        self._field(settings, 'Разрешение', self.resolution_var, 1, 0,
                    values=['1280 × 720', '1600 × 900', '1920 × 1080'], hint='Размер окна при захвате слайдов')
        self._field(settings, 'Пропорции', self.aspect_var, 1, 1,
                    values=['Автоматически', '16:9', '4:3'], hint='Автоматически — как в оригинале')
        self._field(settings, 'Количество слайдов', self.count_var, 2, 0,
                    hint='Оставьте пустым для автоопределения')
        self._field(settings, 'Пауза перед снимком, мс', self.delay_var, 2, 1,
                    kind='spinbox', hint='Чтобы загрузились картинки и завершились эффекты')

        self.advanced_button = ttk.Button(body, text='+ Дополнительные настройки', style='Link.TButton', command=self.toggle_advanced)
        self.advanced_button.grid(row=3, column=0, sticky='w', pady=(0, 8))
        self.advanced = self._card(body, 4)
        for column in (0, 1):
            self.advanced.columnconfigure(column, weight=1, uniform='advanced')
        ttk.Label(self.advanced, text='Навигация и ресурсы', style='Section.TLabel').grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(self.advanced, text='Для необычных презентаций. Обычно эти поля можно оставить без изменений.',
                  style='Hint.TLabel', wraplength=650).grid(row=1, column=0, columnspan=2, sticky='w', pady=(7, 14))
        self._field(self.advanced, 'CSS-селектор слайдов', self.selector_var, 2, 0, hint='Например: .slide')
        self._field(self.advanced, 'Область захвата', self.capture_var, 2, 1, hint='Необязательно. Например: #stage')
        self._field(self.advanced, 'Клавиша следующего слайда', self.key_var, 3, 0,
                    values=['ArrowRight', 'Space', 'PageDown', 'Enter'], editable=True,
                    hint='Можно ввести свою комбинацию клавиш')
        checkbox = ttk.Checkbutton(self.advanced, text='Разрешить загрузку ресурсов из интернета',
                                   variable=self.external_var, style='White.TCheckbutton')
        checkbox.grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 4))
        self._inputs.append((checkbox, 'normal'))
        ttk.Label(self.advanced, text='Для CDN-шрифтов, стилей и скриптов. Включайте для доверенных файлов.',
                  style='Hint.TLabel', wraplength=650).grid(row=5, column=0, columnspan=2, sticky='w', pady=(0, 16))
        chrome_row = ttk.Frame(self.advanced, style='White.TFrame')
        chrome_row.grid(row=6, column=0, columnspan=2, sticky='ew')
        chrome_row.columnconfigure(1, weight=1)
        self.chrome_button = ttk.Button(chrome_row, text='Указать Chrome…', command=self.choose_chrome)
        self.chrome_button.grid(row=0, column=0, sticky='w', padx=(0, 14))
        self.chrome_path_label = ttk.Label(chrome_row, text='Браузер определяется автоматически', style='Hint.TLabel', wraplength=420)
        self.chrome_path_label.grid(row=0, column=1, sticky='w')
        self.advanced.grid_remove()

        footer = ttk.Frame(self.shell, style='Card.TFrame', padding=(20, 12))
        footer.grid(row=2, column=0, sticky='ew', pady=(10, 0))
        footer.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(footer, textvariable=self.status_var, style='CardTitle.TLabel', wraplength=510)
        self.status_label.grid(row=0, column=0, sticky='w')
        ttk.Label(footer, textvariable=self.counter_var, style='Hint.TLabel').grid(row=0, column=1, sticky='e', padx=(14, 0))
        self.progress = ttk.Progressbar(footer, mode='determinate', maximum=100)
        self.progress.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(10, 10))
        controls = ttk.Frame(footer, style='White.TFrame')
        controls.grid(row=2, column=0, columnspan=2, sticky='ew')
        controls.columnconfigure(2, weight=1)
        self.convert_button = ttk.Button(controls, text='Конвертировать', style='Accent.TButton', command=self.start_conversion)
        self.convert_button.grid(row=0, column=0, sticky='w')
        self.cancel_button = ttk.Button(controls, text='Отменить', state='disabled', command=self.cancel)
        self.cancel_button.grid(row=0, column=1, sticky='w', padx=(10, 0))
        self.open_button = ttk.Button(controls, text='Открыть папку', state='disabled', command=self.open_folder)
        self.open_button.grid(row=0, column=3, sticky='e')
        ttk.Label(footer, text='Обработка на вашем компьютере. Исходный HTML не изменяется.',
                  style='Hint.TLabel').grid(row=3, column=0, columnspan=2, sticky='w', pady=(8, 0))

    def _card(self, parent, row):
        card = ttk.Frame(parent, style='Card.TFrame', padding=(20, 12))
        card.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        return card

    def _field(self, parent, title, variable, row, column, values=None, hint='', kind='entry', editable=False):
        field = ttk.Frame(parent, style='White.TFrame')
        field.grid(row=row, column=column, sticky='nsew', padx=(0, 12) if column == 0 else (12, 0), pady=(0, 8))
        field.columnconfigure(0, weight=1)
        ttk.Label(field, text=title, style='Card.TLabel').grid(row=0, column=0, sticky='w')
        state = 'normal'
        if values:
            state = 'normal' if editable else 'readonly'
            control = ttk.Combobox(field, textvariable=variable, values=values, state=state, width=18)
        elif kind == 'spinbox':
            control = ttk.Spinbox(field, from_=0, to=10000, increment=100, textvariable=variable, width=18)
        else:
            control = ttk.Entry(field, textvariable=variable, width=18)
        control.grid(row=1, column=0, sticky='ew', pady=(4, 3))
        self._inputs.append((control, state))
        helper = ttk.Label(field, text=hint, style='Hint.TLabel', wraplength=320)
        helper.grid(row=2, column=0, sticky='w')
        self._hint_labels.append(helper)

    def _resize_shell(self, event):
        if event.widget is not self:
            return
        width = min(1020, max(1, event.width - 48))
        self.shell.place_configure(width=width, height=max(1, event.height - 48))
        self.file_label.configure(wraplength=max(180, width - 280))
        self.file_path_label.configure(wraplength=max(180, width - 280))
        self.status_label.configure(wraplength=max(240, width - 280))
        self.chrome_path_label.configure(wraplength=max(240, width - 310))

    def _resize_body(self, event):
        self.body_canvas.itemconfigure(self._body_window, width=event.width)
        for label in self._hint_labels:
            label.configure(wraplength=max(180, (event.width - 90) // 2))
        self._update_scroll_region()

    def _update_scroll_region(self, event=None):
        bounds = self.body_canvas.bbox('all')
        self.body_canvas.configure(scrollregion=bounds)
        if bounds and bounds[3] > self.body_canvas.winfo_height() + 2:
            self.body_scrollbar.grid()
        else:
            self.body_scrollbar.grid_remove()

    def _scroll_body(self, event):
        bounds = self.body_canvas.bbox('all')
        if bounds and bounds[3] > self.body_canvas.winfo_height():
            self.body_canvas.yview_scroll(-int(event.delta / 120), 'units')
            return 'break'

    def toggle_advanced(self):
        if self.advanced.winfo_ismapped():
            self.advanced.grid_remove()
            self.advanced_button.configure(text='+ Дополнительные настройки')
            self.body_canvas.yview_moveto(0)
        else:
            self.advanced.grid()
            self.advanced_button.configure(text='− Скрыть дополнительные настройки')
            self._reveal_advanced()

    def _reveal_advanced(self):
        self.update_idletasks()
        self._update_scroll_region()
        bounds = self.body_canvas.bbox('all')
        if bounds and bounds[3]:
            self.body_canvas.yview_moveto(max(0, self.advanced.winfo_y() - 12) / bounds[3])

    def choose_source(self):
        filename = filedialog.askopenfilename(title='Исходная HTML-презентация', filetypes=[('HTML-презентации', '*.html *.htm'), ('Все файлы', '*.*')])
        if filename:
            self.source = Path(filename)
            self.file_label.configure(text=self.source.name)
            self.file_path_label.configure(text=str(self.source.parent))
            self.choose_button.configure(text='Изменить…')

    def choose_chrome(self):
        filename = filedialog.askopenfilename(title='Установленный Google Chrome', filetypes=[('Google Chrome', 'chrome.exe')])
        if filename:
            self.chrome_var.set(filename)
            self.chrome_path_label.configure(text=filename)
            self.check_browser()

    def set_busy(self, busy):
        for button in (self.choose_button, self.convert_button, self.advanced_button, self.chrome_button):
            button.configure(state='disabled' if busy else 'normal')
        for control, idle_state in self._inputs:
            control.configure(state='disabled' if busy else idle_state)
        self.cancel_button.configure(state='normal' if busy else 'disabled')

    def check_browser(self):
        if self.worker and self.worker.is_alive():
            return
        self.stop = threading.Event()
        self.set_busy(True)
        self.browser_label.configure(text='Проверяем Chrome…', style='Waiting.TLabel')
        self.status_var.set('Проверка установленного Google Chrome…')
        chrome_path = self.chrome_var.get()

        def run():
            try:
                result = check_environment(self.stop, chrome_path)
                self.events.put({'type': 'ready', 'message': 'Можно начинать. Выберите HTML-презентацию.',
                                 'version': result['version']})
            except Exception as exc:
                self.events.put({'type': 'failure', 'message': str(exc), 'operation': 'environment'})
        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def start_conversion(self):
        if self.worker and self.worker.is_alive():
            return
        if self.source is None:
            self.choose_source()
            if self.source is None:
                return
        try:
            width, height = map(int, self.resolution_var.get().split(' × '))
            aspect = self.aspect_var.get()
            if aspect in ('16:9', '4:3'):
                a, b = map(int, aspect.split(':'))
                height = round(width * b / a)
            count = int(self.count_var.get().strip() or 0)
            delay = int(self.delay_var.get())
        except ValueError:
            messagebox.showerror('Настройки', 'Количество слайдов и задержка должны быть целыми числами.')
            return
        if self.external_var.get() and not messagebox.askyesno('Внешние ресурсы', 'HTML сможет загружать ресурсы из сети. Разрешайте это только для доверенных презентаций. Продолжить?'):
            return
        fmt = self.format_var.get()
        filename = filedialog.asksaveasfilename(title='Сохранить результат', defaultextension='.' + fmt,
                                               initialdir=self.source.parent, initialfile=self.source.stem + '.' + fmt,
                                               filetypes=[(fmt.upper(), '*.' + fmt)])
        if not filename:
            return
        options = Options(self.source, Path(filename), width=width, height=height, count=count,
                          selector=self.selector_var.get(), capture_selector=self.capture_var.get(),
                          next_key=self.key_var.get(), delay_ms=delay, allow_external=self.external_var.get(),
                          chrome_path=self.chrome_var.get(), aspect='auto' if aspect == 'Автоматически' else aspect)
        try:
            options.validate()
        except ConversionError as exc:
            messagebox.showerror('Настройки', str(exc))
            return
        self.stop = threading.Event()
        self.set_busy(True)
        self.open_button.configure(state='disabled')
        self.progress['value'] = 0
        self.counter_var.set('Обработано слайдов: 0')
        self.status_var.set('Запуск конвертации…')

        def run():
            try:
                result = convert(options, self.events.put, self.stop)
                self.events.put({'type': 'complete', **result})
            except Cancelled:
                self.events.put({'type': 'cancelled', 'message': 'Конвертация отменена. Временные файлы удалены.'})
            except Exception as exc:
                self.events.put({'type': 'failure', 'message': str(exc)})
        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def cancel(self):
        self.stop.set()
        self.cancel_button.configure(state='disabled')
        self.status_var.set('Отмена и закрытие браузера…')

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event['type']
                if kind == 'progress':
                    self.counter_var.set(f'Обработано слайдов: {event["current"]} из {event["total"]}')
                    self.progress['value'] = event['current'] / event['total'] * 85
                elif kind == 'export':
                    self.progress['value'] = 85 + event['current'] / event['total'] * 14
                elif kind == 'complete':
                    self.result = Path(event['output'])
                    self.set_busy(False)
                    self.open_button.configure(state='normal')
                    self.progress['value'] = 100
                    self.status_var.set(f'Готово: {event["count"]} слайдов. {self.result.name}')
                elif kind in ('failure', 'cancelled', 'ready'):
                    self.set_busy(False)
                    self.status_var.set(event['message'][:300])
                    if kind == 'ready':
                        self.browser_label.configure(text='Chrome готов', style='Ready.TLabel')
                    elif event.get('operation') == 'environment':
                        self.browser_label.configure(text='Проверьте Chrome', style='Error.TLabel')
                    if kind == 'failure' and not self.closing:
                        messagebox.showerror('Не удалось выполнить операцию', event['message'][:4000])
                        if 'необходим Google Chrome' in event['message'] and messagebox.askyesno('Google Chrome', 'Открыть официальный сайт для установки Google Chrome?'):
                            webbrowser.open('https://www.google.com/chrome/')
                if kind in ('status', 'progress', 'export'):
                    self.status_var.set(event.get('message', ''))
        except queue.Empty:
            pass
        if self.closing and (self.worker is None or not self.worker.is_alive()):
            self.destroy()
            return
        self.after(100, self.poll)

    def open_folder(self):
        if self.result and self.result.parent.is_dir():
            try:
                os.startfile(self.result.parent)
            except OSError as exc:
                messagebox.showerror('Папка результата', str(exc))

    def on_close(self):
        self.closing = True
        self.stop.set()
        if self.worker and self.worker.is_alive():
            self.status_var.set('Завершение конвертации и очистка…')
        else:
            self.destroy()

    def destroy(self):
        # Cancel Tcl callbacks before deleting their Python command registrations.
        for callback in self.tk.splitlist(self.tk.call('after', 'info')):
            self.after_cancel(callback)
        super().destroy()
