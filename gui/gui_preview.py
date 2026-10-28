# gui/gui_preview.py - Окно предпросмотра печати (CustomTkinter)
#
# Предпросмотр рисуется по той же раскладке страниц, что и PDF
# (BarcodeGenerator.layout_pages), поэтому показывает ровно то, что будет
# напечатано — с шаблоном, сеткой и полями. Штрихкоды готовятся в фоновом
# потоке: окно открывается сразу, страницы появляются по мере готовности.
# «Печать» отправляет на принтер настоящий PDF.

import os
import queue
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from . import theme as T
from logger import logger
from utils import validate_code, print_pdf

MAX_PAGE_PX = (1600, 1200)   # потолок размера картинки страницы


class PreviewWindow:
    """Окно предпросмотра печати с точным отображением страницы."""

    def __init__(self, parent, codes, app):
        self.parent = parent
        self.codes = codes
        self.app = app
        self.gen = app.generator
        self.metadata = dict(getattr(app, "codes_metadata", {}) or {})
        self.preview_images = []    # PIL-картинки страниц
        self.images = []            # ссылки на PhotoImage (иначе Tk их выбросит)
        self.barcode_images = []    # [(код, путь к картинке)] — для печати
        self.skipped = []
        self.current_page = 0
        self.zoom_level = 1.0
        self.ready = False

        self.queue = queue.Queue()
        self.cancel = threading.Event()
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

        self.create_window()
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()
        self.window.after(50, self._poll)

    # ========== ОКНО ==========
    def create_window(self):
        self.window = ctk.CTkToplevel(self.parent)
        T.setup_dialog(self.window, self.parent, "Предпросмотр печати", 1000, 780, modal=False)
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(1, weight=1)

        # ----- Заголовок -----
        head = ctk.CTkFrame(self.window, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 16))

        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side="left")
        T.overline(titles, "Предпросмотр").pack(anchor="w")
        T.title(titles, "Как это будет напечатано", size=24).pack(anchor="w")

        g = self.gen
        if g.template_active():
            mode = "по шаблону этикетки"
        else:
            mode = (f"поля {g.margins[0]:g} / {g.margins[1]:g} / "
                    f"{g.margins[2]:g} / {g.margins[3]:g} мм")
        info = [mode, f"{g.labels_per_page} на странице"]
        if g.show_border:
            info.append("с рамкой")
        self.info_label = T.label(titles, "  ·  ".join(info), size=13, color=T.TEXT_2)
        self.info_label.pack(anchor="w", pady=(2, 0))

        self.print_button = T.button(head, "Печать", self.print_page, variant="primary",
                                     height=44, width=130, state="disabled")
        self.print_button.pack(side="right")

        # ----- Холст -----
        canvas_card = T.card(self.window, fg_color=T.CANVAS_BG)
        canvas_card.grid(row=1, column=0, sticky="nsew", padx=28)

        self.canvas = tk.Canvas(canvas_card, bg=T.CANVAS_BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)

        # ----- Нижняя панель: страницы и масштаб -----
        bar = ctk.CTkFrame(self.window, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=28, pady=(14, 20))

        prev_btn = T.button(bar, "‹", self.prev_page, height=40, width=40, font_size=20)
        prev_btn.pack(side="left")
        T.Tooltip(prev_btn, "Предыдущая страница (←)")
        next_btn = T.button(bar, "›", self.next_page, height=40, width=40, font_size=20)
        next_btn.pack(side="left", padx=(8, 0))
        T.Tooltip(next_btn, "Следующая страница (→)")

        self.page_info_label = T.label(bar, "Подготовка…", size=13)
        self.page_info_label.pack(side="left", padx=14)

        self.total_labels_label = T.label(bar, "", size=12, color=T.TEXT_3)
        self.total_labels_label.pack(side="left", padx=(6, 0))

        T.button(bar, "1:1", self.zoom_reset, height=36, width=52).pack(side="right")
        T.button(bar, "+", self.zoom_in, height=36, width=40, font_size=16
                 ).pack(side="right", padx=(0, 6))
        self.zoom_label = T.label(bar, "100%", size=12, color=T.TEXT_2, width=50)
        self.zoom_label.pack(side="right", padx=4)
        T.button(bar, "−", self.zoom_out, height=36, width=40, font_size=16
                 ).pack(side="right", padx=(0, 4))

        # ----- Обработка -----
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.window.bind('<Escape>', lambda e: self.on_close())
        self.window.bind('<Left>', lambda e: self.prev_page())
        self.window.bind('<Right>', lambda e: self.next_page())
        self.window.bind('<Control-plus>', lambda e: self.zoom_in())
        self.window.bind('<Control-equal>', lambda e: self.zoom_in())
        self.window.bind('<Control-minus>', lambda e: self.zoom_out())
        self.window.bind('<Control-0>', lambda e: self.zoom_reset())
        self.canvas.bind('<Configure>', self.on_resize)

    # ========== ФОНОВАЯ ПОДГОТОВКА ==========
    def _worker(self):
        """Генерирует штрихкоды и рисует страницы. К Tk не обращается."""
        q = self.queue
        try:
            total = len(self.codes)
            for i, code in enumerate(self.codes, 1):
                if self.cancel.is_set():
                    return
                valid, msg = validate_code(code, self.gen.barcode_type)
                path = self.gen.generate_barcode_image(code, self.temp.name) if valid else None
                if path:
                    self.barcode_images.append((code, path))
                else:
                    self.skipped.append(code)
                q.put(("progress", (i, total)))

            page_w, page_h, pages = self.gen.layout_pages(self.barcode_images, self.metadata)
            k = min(8.0, MAX_PAGE_PX[0] / page_w, MAX_PAGE_PX[1] / page_h)
            q.put(("layout", (page_w, page_h, len(pages))))
            for ops in pages:
                if self.cancel.is_set():
                    return
                q.put(("page", self.gen.render_page_image(page_w, page_h, ops, k)))
            q.put(("done", None))
        except Exception as e:
            logger.error(f"Ошибка предпросмотра: {e}")
            q.put(("error", e))

    def _poll(self):
        if self.cancel.is_set():
            return
        try:
            while True:
                kind, data = self.queue.get_nowait()
                if kind == "progress":
                    i, total = data
                    self._show_message(f"Готовим штрихкоды: {i} из {total}")
                    self.page_info_label.configure(text=f"Подготовка… {i} из {total}")
                elif kind == "layout":
                    w, h, self.total_pages = data
                    self.info_label.configure(text=f"{w:g}×{h:g} мм  ·  " + self.info_label.cget("text"))
                    if not self.total_pages:
                        self._show_message("Нет кодов, которые можно напечатать")
                elif kind == "page":
                    self.preview_images.append(data)
                    if len(self.preview_images) == 1:
                        self.show_page(0)
                    else:
                        self._update_page_label()
                elif kind == "done":
                    self._on_ready()
                elif kind == "error":
                    self._show_message(f"Ошибка: {data}")
                    self.app.set_status("Ошибка предпросмотра", 'error')
                    return
        except queue.Empty:
            pass
        self.window.after(50, self._poll)

    def _on_ready(self):
        self.ready = True
        done = len(self.barcode_images)
        text = f"·  этикеток: {done}"
        if self.skipped:
            text += f"  ·  пропущено с ошибками: {len(self.skipped)}"
            self.total_labels_label.configure(text_color=T.ERROR)
        self.total_labels_label.configure(text=text)
        if done:
            self.print_button.configure(state="normal")
        self.app.set_status("Предпросмотр готов", 'success')

    def _show_message(self, text):
        """Сообщение по центру холста, пока страниц ещё нет."""
        if self.preview_images:
            return
        self.canvas.delete("all")
        self.canvas.create_text(max(self.canvas.winfo_width(), 200) / 2,
                                max(self.canvas.winfo_height(), 200) / 2,
                                text=text, fill=T.TEXT_2, font=(T.FONT_UI, 13))

    # ========== НАВИГАЦИЯ ==========
    def _update_page_label(self):
        total = getattr(self, "total_pages", len(self.preview_images)) or len(self.preview_images)
        self.page_info_label.configure(text=f"Страница {self.current_page + 1} из {total}")

    def show_page(self, page_num):
        if not self.preview_images:
            return
        page_num = max(0, min(page_num, len(self.preview_images) - 1))
        self.current_page = page_num
        self._update_page_label()
        self.display_image(self.preview_images[page_num])

    def display_image(self, img):
        self.canvas.delete("all")

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w < 10 or canvas_h < 10:
            canvas_w, canvas_h = 800, 560

        # 100% — страница вписана в холст с запасом по краям
        fit = min((canvas_w - 60) / img.width, (canvas_h - 60) / img.height)
        img_w = max(1, int(img.width * fit * self.zoom_level))
        img_h = max(1, int(img.height * fit * self.zoom_level))

        img_resized = img.resize((img_w, img_h), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img_resized)
        self.images = [photo]

        x = (canvas_w - img_w) / 2
        y = (canvas_h - img_h) / 2

        # Мягкая «тень» под листом
        self.canvas.create_rectangle(x + 4, y + 6, x + img_w + 4, y + img_h + 6,
                                     fill=T.PAPER_SHADOW, outline="")
        self.canvas.create_image(x, y, anchor="nw", image=photo)

        self.zoom_label.configure(text=f"{int(self.zoom_level * 100)}%")

    def prev_page(self):
        if self.current_page > 0:
            self.show_page(self.current_page - 1)

    def next_page(self):
        if self.current_page < len(self.preview_images) - 1:
            self.show_page(self.current_page + 1)

    def zoom_in(self):
        self.zoom_level = min(self.zoom_level * 1.2, 3.0)
        self.show_page(self.current_page)

    def zoom_out(self):
        self.zoom_level = max(self.zoom_level / 1.2, 0.2)
        self.show_page(self.current_page)

    def zoom_reset(self):
        self.zoom_level = 1.0
        self.show_page(self.current_page)

    def on_resize(self, event):
        if self.preview_images:
            self.display_image(self.preview_images[self.current_page])

    # ========== ПЕЧАТЬ ==========
    def print_page(self):
        """Собирает настоящий PDF из тех же картинок и отправляет на принтер."""
        if not self.ready or not self.barcode_images:
            return
        self.print_button.configure(state="disabled", text="ГОТОВИМ…")
        result = queue.Queue()
        # Не в папке предпросмотра: окно могут закрыть раньше, чем
        # программа печати успеет прочитать файл
        fd, pdf_path = tempfile.mkstemp(prefix="barcodegen_print_", suffix=".pdf")
        os.close(fd)

        def work():
            try:
                self.gen.create_pdf(pdf_path, self.barcode_images, metadata=self.metadata)
                result.put(print_pdf(pdf_path))
            except Exception as e:
                result.put((False, str(e)))

        def wait():
            try:
                ok, message = result.get_nowait()
            except queue.Empty:
                self.window.after(100, wait)
                return
            self.print_button.configure(state="normal", text="ПЕЧАТЬ")
            if ok:
                self.app.set_status(message, 'success')
            else:
                self.app.set_status(f"Ошибка печати: {message[:40]}", 'error')
                messagebox.showerror("Ошибка печати", f"Не удалось отправить на печать:\n{message}",
                                     parent=self.window)

        threading.Thread(target=work, daemon=True).start()
        self.window.after(100, wait)

    def on_close(self):
        self.cancel.set()
        self.images.clear()
        self.preview_images.clear()
        self.window.destroy()
        # Временные картинки удаляем, когда фоновый поток точно закончит работу
        worker, temp = self.worker, self.temp
        threading.Thread(target=lambda: (worker.join(), temp.cleanup()), daemon=True).start()
