# gui/gui_preview.py - Окно предпросмотра печати (CustomTkinter)
#
# Постраничный рендер этикеток, навигация, зум, отправка на печать.
# Страница рисуется белой «бумагой» на тёмном фоне.

import os
import io
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw

from . import theme as T
from utils import GRID_MAP, validate_code


class PreviewWindow:
    """Окно предпросмотра печати с точным отображением страницы."""

    def __init__(self, parent, codes, app):
        self.parent = parent
        self.codes = codes
        self.app = app
        self.window = None
        self.images = []
        self.current_page = 0
        self.total_pages = 0
        self.zoom_level = 1.0
        self.preview_images = []

        # Параметры страницы
        try:
            self.page_width_mm = float(self.app.label_width.get())
            self.page_height_mm = float(self.app.label_height.get())
            self.margins = [
                float(self.app.margin_top.get()),
                float(self.app.margin_bottom.get()),
                float(self.app.margin_left.get()),
                float(self.app.margin_right.get())
            ]
            self.labels_per_page = self.app.labels_per_page.get()
            self.show_border = self.app.show_border.get()
        except Exception:
            messagebox.showerror("Ошибка", "Некорректные размеры этикетки")
            self.window = None
            return

        self.create_window()
        self.generate_preview_pages()

        if self.preview_images:
            self.show_page(0)

    # ========== ОКНО ==========
    def create_window(self):
        self.window = ctk.CTkToplevel(self.parent)
        T.setup_dialog(self.window, self.parent, "Предпросмотр печати", 1000, 780, modal=False)
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(1, weight=1)

        # ----- Заголовок и управление -----
        head = ctk.CTkFrame(self.window, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 16))

        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side="left")
        T.overline(titles, "Предпросмотр").pack(anchor="w")
        T.title(titles, "Как это будет напечатано", size=24).pack(anchor="w")

        info = [f"{self.page_width_mm:g}×{self.page_height_mm:g} мм",
                f"поля {self.margins[0]:g} / {self.margins[1]:g} / {self.margins[2]:g} / {self.margins[3]:g} мм",
                f"{self.labels_per_page} на странице"]
        if self.show_border:
            info.append("с рамкой")
        T.label(titles, "  ·  ".join(info), size=13, color=T.TEXT_2).pack(anchor="w", pady=(2, 0))

        T.button(head, "Печать", self.print_page, variant="primary", height=44, width=130
                 ).pack(side="right")

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

        self.page_info_label = T.label(bar, "Страница 1 из 1", size=13)
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

        self.status_label = T.label(bar, "", size=12, color=T.TEXT_3)

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

    def _set_status(self, text, color=T.TEXT_3):
        self.status_label.configure(text=text, text_color=color)

    # ========== ГЕНЕРАЦИЯ СТРАНИЦ ==========
    def generate_preview_pages(self):
        self.app.set_status("Генерация предпросмотра...", 'warning')

        codes = self.codes
        if not codes:
            self._set_status("Нет кодов для отображения", T.ERROR)
            return

        labels_per_page = self.labels_per_page
        total_labels = len(codes)
        self.total_pages = (total_labels + labels_per_page - 1) // labels_per_page
        self.total_labels_label.configure(text=f"·  всего этикеток: {total_labels}")

        self.preview_images = []

        for page_num in range(self.total_pages):
            start_idx = page_num * labels_per_page
            end_idx = min(start_idx + labels_per_page, total_labels)
            page_codes = codes[start_idx:end_idx]

            img = self.create_page_image(page_codes, page_num + 1, self.total_pages)
            if img:
                self.preview_images.append(img)

        self.app.set_status("Предпросмотр готов", 'success')

    def create_page_image(self, page_codes, page_num, total_pages):
        try:
            # Рендерим крупно, чтобы на экране страница была чёткой
            scale = 8.0
            page_w = int(self.page_width_mm * scale)
            page_h = int(self.page_height_mm * scale)

            if page_w > 1600 or page_h > 1200:
                scale = min(1600 / self.page_width_mm, 1200 / self.page_height_mm)
                page_w = int(self.page_width_mm * scale)
                page_h = int(self.page_height_mm * scale)

            img = Image.new('RGB', (page_w, page_h), 'white')
            draw = ImageDraw.Draw(img)

            mt = int(self.margins[0] * scale)
            mb = int(self.margins[1] * scale)
            ml = int(self.margins[2] * scale)
            mr = int(self.margins[3] * scale)

            available_w = page_w - ml - mr
            available_h = page_h - mt - mb

            labels_per_page = self.labels_per_page
            if labels_per_page > 1:
                cols, rows = self.get_grid(labels_per_page)
                label_w = available_w / cols
                label_h = available_h / rows
            else:
                cols, rows = 1, 1
                label_w = available_w
                label_h = available_h

            for idx, code in enumerate(page_codes):
                if idx >= labels_per_page:
                    break

                col = idx % cols
                row = idx // cols

                x = ml + col * label_w
                y = mt + row * label_h

                if self.show_border:
                    draw.rectangle([x, y, x + label_w, y + label_h],
                                   outline='#cccccc', width=2)

                valid, _ = validate_code(code, self.app.barcode_type.get())

                if not valid:
                    self._draw_error(draw, x, y, label_w, label_h, code)
                    continue

                try:
                    img_bytes = self.app.generator.generate_barcode_to_bytes(code)
                    if img_bytes:
                        img_bytes.seek(0)
                        barcode_pil = Image.open(img_bytes)

                        barcode_w = int(label_w * 0.85)
                        barcode_h = int(label_h * 0.80)
                        barcode_resized = barcode_pil.resize(
                            (barcode_w, barcode_h), Image.Resampling.LANCZOS
                        )

                        bx = x + (label_w - barcode_w) / 2
                        by = y + (label_h - barcode_h) / 2
                        img.paste(barcode_resized, (int(bx), int(by)))
                except Exception:
                    self._draw_error(draw, x, y, label_w, label_h, code)

            if self.show_border:
                draw.rectangle([0, 0, page_w - 1, page_h - 1],
                               outline='#999999', width=2)

            return img

        except Exception as e:
            print(f"Ошибка создания страницы: {e}")
            return None

    @staticmethod
    def _draw_error(draw, x, y, w, h, code):
        """Красная плашка на месте кода, который не удалось сгенерировать."""
        draw.rectangle([x + 5, y + 5, x + w - 5, y + h - 5],
                       outline='#ff6b6b', fill='#fff5f5', width=3)
        try:
            from PIL import ImageFont
            fnt = ImageFont.load_default(size=max(10, int(h * 0.08)))
        except Exception:
            fnt = None  # Pillow < 10.1 — шрифт по умолчанию без размера
        draw.text((x + w / 2, y + h / 2), f"Ошибка: {code[:15]}",
                  fill='#d00000', anchor='mm', font=fnt)

    def get_grid(self, labels_per_page):
        return GRID_MAP.get(labels_per_page, (2, 2))

    # ========== НАВИГАЦИЯ ==========
    def show_page(self, page_num):
        if not self.preview_images:
            return

        if page_num < 0:
            page_num = 0
        elif page_num >= len(self.preview_images):
            page_num = len(self.preview_images) - 1

        self.current_page = page_num
        self.page_info_label.configure(
            text=f"Страница {page_num + 1} из {len(self.preview_images)}"
        )

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
        if self.preview_images:
            self.display_image(self.preview_images[self.current_page])

    def zoom_out(self):
        self.zoom_level = max(self.zoom_level / 1.2, 0.2)
        if self.preview_images:
            self.display_image(self.preview_images[self.current_page])

    def zoom_reset(self):
        self.zoom_level = 1.0
        if self.preview_images:
            self.display_image(self.preview_images[self.current_page])

    def on_resize(self, event):
        if self.preview_images:
            self.display_image(self.preview_images[self.current_page])

    # ========== ПЕЧАТЬ ==========
    def print_page(self):
        if not self.preview_images:
            messagebox.showwarning("Внимание", "Нет страниц для печати")
            return

        try:
            import tempfile
            import subprocess
            import platform
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import ImageReader

            temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            temp_path = temp_file.name
            temp_file.close()

            c = canvas.Canvas(
                temp_path,
                pagesize=(self.page_width_mm * 2.83465, self.page_height_mm * 2.83465)
            )

            for img in self.preview_images:
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)

                img_reader = ImageReader(img_bytes)
                c.drawImage(img_reader, 0, 0,
                            width=self.page_width_mm * 2.83465,
                            height=self.page_height_mm * 2.83465)
                c.showPage()

            c.save()

            if platform.system() == "Windows":
                os.startfile(temp_path, "print")
            elif platform.system() == "Darwin":
                subprocess.run(["lp", temp_path])
            else:
                subprocess.run(["lp", temp_path])

            self.app.set_status("Отправлено на печать", 'success')

        except ImportError:
            messagebox.showwarning(
                "Внимание",
                "Для печати требуется установить reportlab:\npip install reportlab"
            )
        except Exception as e:
            messagebox.showerror("Ошибка печати",
                                 f"Не удалось отправить на печать:\n{str(e)}")
            self.app.set_status(f"Ошибка печати: {str(e)[:30]}", 'error')

    def on_close(self):
        self.images.clear()
        self.preview_images.clear()
        self.window.destroy()
