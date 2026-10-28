# gui/gui_template_editor.py - Визуальный редактор шаблонов этикеток
#
# Открывается по кнопке "Шаблон". Позволяет перетаскивать и растягивать
# штрихкод / текстовые блоки / картинки на холсте (масштабированная
# этикетка в мм) и сохранять раскладку - она затем используется при
# генерации PDF (см. BarcodeGenerator._create_pdf_from_template).
#
# Поддерживает несколько именованных шаблонов: пользователь может
# сохранить "Шаблон для полки", "Шаблон для тары" и переключаться между
# ними. Активный шаблон сохраняется в settings как "label_template".
#
# Формат шаблона (JSON-совместимый dict):
#   {
#     "label_width": 58, "label_height": 40,
#     "elements": [
#         {"id": "barcode", "type": "barcode", "x": 4, "y": 12, "w": 50, "h": 22},
#         {"id": "code_text", "type": "text", "text": "{code}",
#          "x": 4, "y": 2, "w": 50, "h": 8, "font_size": 10},
#         {"id": "logo", "type": "image", "src": "...", "x": 4, "y": 4, "w": 15, "h": 10},
#     ]
#   }
# x/y/w/h - в миллиметрах от левого верхнего угла этикетки.
# {code} в тексте подставляется реальным кодом при генерации PDF;
# {name}, {price} и т.п. — метаданными из импортированного CSV/XLSX.

import copy
import os
import shutil
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from . import theme as T

# Единый логгер (если доступен) - иначе работаем молча
try:
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from logger import logger
except Exception:
    class _DummyLogger:
        def info(self, *a, **k): pass
        def warning(self, *a, **k): pass
        def error(self, *a, **k): pass
    logger = _DummyLogger()

FONT_UI = T.FONT_UI

MAX_SCALE = 10         # максимум пикселей на 1 мм (маленькие этикетки)
CANVAS_PAD = 30        # отступ от края холста до листа, px
HANDLE_SIZE = 10       # размер квадратика для изменения размера (px)
MIN_SIZE_MM = 4        # минимальная ширина/высота элемента

COLORS = {
    "bg": T.BG, "card": T.SURFACE, "border": T.BORDER,
    "input": T.SURFACE_2, "text": T.TEXT, "text2": T.TEXT_2,
    "accent": T.ACCENT,
    # цвета внутри белого листа этикетки
    "ink": "#111111", "guide": "#C9C9CF", "barcode_guide": "#9FB8E8",
}

DEFAULT_ELEMENTS = [
    {"id": "barcode", "type": "barcode", "x": 4, "y": 12, "w": 50, "h": 22},
    {"id": "code_text", "type": "text", "text": "{code}", "x": 4, "y": 2, "w": 50, "h": 8, "font_size": 10},
]


def default_template(width_mm, height_mm):
    """Шаблон по умолчанию: штрихкод + текст кода — повторяет прежнее поведение."""
    return {
        "label_width": width_mm,
        "label_height": height_mm,
        "elements": copy.deepcopy(DEFAULT_ELEMENTS),
    }


class TemplateEditor(ctk.CTkToplevel):
    """Окно редактора шаблона этикетки."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        T.setup_dialog(self, master, "Редактор шаблона", 1120, 760, modal=False)

        # Загружаем сохранённые именованные шаблоны и текущее имя
        self.templates = dict(app.settings.get("label_templates", {}) or {})
        self.current_name = app.settings.get("current_template", "") or "По умолчанию"

        # Активный шаблон: либо из именованных, либо из legacy label_template,
        # либо шаблон по умолчанию
        if self.current_name in self.templates:
            self.template = copy.deepcopy(self.templates[self.current_name])
        else:
            stored = app.settings.get("label_template")
            if stored:
                self.template = copy.deepcopy(stored)
                self.templates[self.current_name] = copy.deepcopy(stored)
            else:
                self.template = default_template(
                    float(app.label_width.get() or 58),
                    float(app.label_height.get() or 40),
                )

        self.selected_index = None
        self.drag_mode = None      # "move" | "resize" | None
        self.drag_start = None
        self.photo_refs = {}
        self.canvas_offset = (CANVAS_PAD, CANVAS_PAD)
        self.scale = 6.0           # пикселей на 1 мм, пересчитывается в redraw()
        self.sample_image = None
        self.fill_margin_var = tk.StringVar(value="0")

        self._build_ui()
        self._render_sample_barcode()
        self.redraw()

    # ========== ПРЕДПРОСМОТР ШТРИХКОДА ==========
    def _render_sample_barcode(self):
        """Генерирует один пример штрихкода для наглядного превью в редакторе."""
        samples = {
            "code39": "SAMPLE123",
            "ean13": "123456789012",
            "ean8": "1234567",
            "upca": "12345678901",
            "itf": "12345678",
            "codabar": "A12345B",
        }
        try:
            sample_code = samples.get(self.app.barcode_type.get(), "123456789012")
            buf = self.app.generator.generate_barcode_to_bytes(sample_code)
            if buf:
                self.sample_image = Image.open(buf).convert("RGB")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сгенерировать пример для редактора: {e}")
            self.sample_image = None

    # ========== UI ==========
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ---------- Заголовок ----------
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 0))

        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side="left")
        T.overline(titles, "Шаблон этикетки").pack(anchor="w")
        T.title(titles, "Редактор", size=26).pack(anchor="w")

        T.button(head, "Сохранить и применить", self.save_template, variant="primary",
                 height=44, width=220).pack(side="right")

        # ---------- Панель: выбор шаблона + добавление элементов ----------
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=28, pady=(18, 14))

        self.template_names = list(self.templates.keys()) or ["По умолчанию"]
        if self.current_name not in self.template_names:
            self.template_names.append(self.current_name)

        self.template_var = tk.StringVar(value=self.current_name)
        self.template_menu = T.option_menu(bar, values=self.template_names,
                                           variable=self.template_var,
                                           command=self.load_named_template,
                                           width=210, height=36)
        self.template_menu.pack(side="left")
        T.button(bar, "Сохранить как…", self.save_as_new_template, height=36, width=150
                 ).pack(side="left", padx=(8, 0))
        T.button(bar, "Удалить", self.delete_current_template, variant="ghost", height=36
                 ).pack(side="left", padx=(4, 0))

        for text, cmd in [("Картинка", self.add_image_element),
                          ("Текст", self.add_text_element),
                          ("Штрихкод", self.add_barcode_element)]:
            T.button(bar, text, cmd, height=36, icon_name="plus"
                     ).pack(side="right", padx=(8, 0))

        # ---------- Основная область: холст + панель свойств ----------
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 22))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        canvas_card = T.card(body, fg_color=T.CANVAS_BG)
        canvas_card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        canvas_card.grid_columnconfigure(0, weight=1)
        canvas_card.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_card, bg=T.CANVAS_BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Configure>", lambda e: self.redraw())

        # Размер этикетки — под холстом
        size_row = ctk.CTkFrame(canvas_card, fg_color="transparent")
        size_row.grid(row=1, column=0, sticky="ew", padx=20, pady=(6, 16))

        T.field_label(size_row, "Размер этикетки").pack(side="left", padx=(0, 10))
        self.width_var = tk.StringVar(value=str(self.template["label_width"]))
        self.height_var = tk.StringVar(value=str(self.template["label_height"]))
        T.entry(size_row, self.width_var, width=64, height=34).pack(side="left")
        T.label(size_row, "×", color=T.TEXT_2).pack(side="left", padx=6)
        T.entry(size_row, self.height_var, width=64, height=34).pack(side="left")
        T.label(size_row, "мм", size=12, color=T.TEXT_2).pack(side="left", padx=(6, 10))
        T.button(size_row, "Применить", self.apply_size, height=34).pack(side="left")

        T.button(size_row, "Сбросить шаблон", self.reset_template, variant="ghost", height=34
                 ).pack(side="right")

        side = T.card(body, width=290)
        side.grid(row=0, column=1, sticky="ns")
        side.grid_propagate(False)
        side.pack_propagate(False)

        T.section_title(side, "Свойства").pack(anchor="w", padx=20, pady=(18, 10))

        self.props_frame = ctk.CTkFrame(side, fg_color="transparent")
        self.props_frame.pack(fill="x", padx=20)

    # ========== ОТРИСОВКА ==========
    def redraw(self):
        c = COLORS
        self.canvas.delete("all")

        w_mm = self.template["label_width"]
        h_mm = self.template["label_height"]

        # Масштаб: этикетка вписывается в холст целиком
        canvas_w = max(self.canvas.winfo_width(), 200)
        canvas_h = max(self.canvas.winfo_height(), 200)
        self.scale = max(1.0, min(MAX_SCALE,
                                  (canvas_w - 2 * CANVAS_PAD) / w_mm,
                                  (canvas_h - 2 * CANVAS_PAD) / h_mm))
        k = self.scale
        cw, ch = w_mm * k, h_mm * k
        ox, oy = (canvas_w - cw) / 2, (canvas_h - ch) / 2
        self.canvas_offset = (ox, oy)

        # Лист этикетки с тенью
        self.canvas.create_rectangle(ox + 4, oy + 6, ox + cw + 4, oy + ch + 6,
                                     fill=T.PAPER_SHADOW, outline="")
        self.canvas.create_rectangle(ox, oy, ox + cw, oy + ch, fill=T.PAPER, outline="")

        self.photo_refs.clear()

        for i, el in enumerate(self.template["elements"]):
            x0 = ox + el["x"] * k
            y0 = oy + el["y"] * k
            x1 = x0 + el["w"] * k
            y1 = y0 + el["h"] * k

            selected = (i == self.selected_index)

            # ----- Отрисовка по типу элемента -----
            if el["type"] == "image":
                src = el.get("src", "")
                if src and os.path.exists(src):
                    try:
                        px_w = max(1, int(x1 - x0))
                        px_h = max(1, int(y1 - y0))
                        img = Image.open(src).convert("RGBA").resize((px_w, px_h))
                        photo = ImageTk.PhotoImage(img)
                        self.photo_refs[i] = photo
                        self.canvas.create_image(x0, y0, image=photo, anchor="nw")
                    except Exception as e:
                        logger.warning(f"Не удалось отобразить картинку: {e}")
                else:
                    self.canvas.create_text(
                        (x0 + x1) / 2, (y0 + y1) / 2,
                        text="Картинка\n(файл не найден)",
                        font=(FONT_UI, 9), fill="#8A8A92", justify="center"
                    )

            elif el["type"] == "barcode" and self.sample_image is not None:
                try:
                    px_w, px_h = max(1, int(x1 - x0)), max(1, int(y1 - y0))
                    img = self.sample_image.resize((px_w, px_h))
                    photo = ImageTk.PhotoImage(img)
                    self.photo_refs[i] = photo
                    self.canvas.create_image(x0, y0, image=photo, anchor="nw")
                except Exception:
                    pass

            elif el["type"] == "barcode":
                self.canvas.create_text(
                    (x0 + x1) / 2, (y0 + y1) / 2,
                    text="ШТРИХКОД",
                    font=(FONT_UI, 10), fill="#8A8A92"
                )

            # Текст (для type="text")
            if el["type"] == "text":
                label_text = str(el.get("text", "")).replace("{code}", "232183-VPVY69P2")
                # pt → px на холсте: 1 pt = 0.3528 мм (как в PDF)
                font_px = max(7, int(el.get("font_size", 10) * 0.3528 * k))
                self.canvas.create_text(
                    (x0 + x1) / 2, (y0 + y1) / 2,
                    text=label_text, font=(FONT_UI, -font_px), fill=c["ink"]
                )

            # Рамка: у выделенного — сплошная тёмная, у остальных — пунктир
            if selected:
                self.canvas.create_rectangle(x0, y0, x1, y1, outline=c["ink"], width=2)
                hs = HANDLE_SIZE
                self.canvas.create_rectangle(x1 - hs, y1 - hs, x1 + 2, y1 + 2,
                                             fill=c["accent"], outline=c["ink"])
            else:
                guide = c["barcode_guide"] if el["type"] == "barcode" else c["guide"]
                self.canvas.create_rectangle(x0, y0, x1, y1, outline=guide, dash=(4, 3))

        self.update_props_panel()

    # ========== ХИТ-ТЕСТ И ДРАГ ==========
    def _element_at(self, x, y):
        ox, oy = self.canvas_offset
        k = self.scale
        for i in reversed(range(len(self.template["elements"]))):
            el = self.template["elements"][i]
            x0 = ox + el["x"] * k
            y0 = oy + el["y"] * k
            x1 = x0 + el["w"] * k
            y1 = y0 + el["h"] * k
            hs = HANDLE_SIZE
            if i == self.selected_index and x1 - hs <= x <= x1 + 4 and y1 - hs <= y <= y1 + 4:
                return i, "resize"
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i, "move"
        return None, None

    def on_press(self, event):
        idx, mode = self._element_at(event.x, event.y)
        self.selected_index = idx
        self.drag_mode = mode
        self.drag_start = (event.x, event.y)
        self.redraw()

    def on_drag(self, event):
        if self.selected_index is None or self.drag_mode is None:
            return
        dx_mm = (event.x - self.drag_start[0]) / self.scale
        dy_mm = (event.y - self.drag_start[1]) / self.scale
        el = self.template["elements"][self.selected_index]

        if self.drag_mode == "move":
            el["x"] = max(0.0, round(el["x"] + dx_mm, 1))
            el["y"] = max(0.0, round(el["y"] + dy_mm, 1))
        else:
            el["w"] = max(MIN_SIZE_MM, round(el["w"] + dx_mm, 1))
            el["h"] = max(MIN_SIZE_MM, round(el["h"] + dy_mm, 1))

        self.drag_start = (event.x, event.y)
        self.redraw()

    def on_release(self, event):
        self.drag_mode = None
        self.drag_start = None

    # ========== ПАНЕЛЬ СВОЙСТВ ==========
    def update_props_panel(self):
        for widget in self.props_frame.winfo_children():
            widget.destroy()

        if self.selected_index is None:
            T.label(self.props_frame, "Нажмите на элемент на этикетке, чтобы изменить его.\n\n"
                                      "Элементы можно перетаскивать мышью, а жёлтый уголок "
                                      "справа внизу меняет размер.",
                    size=12, color=T.TEXT_2, wraplength=240, justify="left"
                    ).pack(anchor="w", pady=(0, 10))
            return

        el = self.template["elements"][self.selected_index]
        names = {"barcode": "Штрихкод", "text": "Текст", "image": "Картинка"}
        T.label(self.props_frame, names.get(el["type"], el["type"]), size=13, weight="bold",
                color=T.ACCENT).pack(anchor="w", pady=(0, 8))

        grid = ctk.CTkFrame(self.props_frame, fg_color="transparent")
        grid.pack(fill="x")

        def field(parent, label, key, row, col, width=110):
            box = ctk.CTkFrame(parent, fg_color="transparent")
            box.grid(row=row, column=col, sticky="w", padx=(0 if col == 0 else 10, 0), pady=3)
            T.field_label(box, label).pack(anchor="w")
            var = tk.StringVar(value=str(el[key]))
            entry = T.entry(box, var, width=width, height=34)
            entry.pack(anchor="w", pady=(2, 0))

            def commit(event=None):
                try:
                    val = float(var.get())
                    if key in ("w", "h"):
                        val = max(MIN_SIZE_MM, val)
                    else:
                        val = max(0.0, val)
                    el[key] = round(val, 1)
                    self.redraw()
                except ValueError:
                    var.set(str(el[key]))

            entry.bind("<Return>", commit)
            entry.bind("<FocusOut>", commit)

        field(grid, "X, мм", "x", 0, 0)
        field(grid, "Y, мм", "y", 0, 1)
        field(grid, "Ширина, мм", "w", 1, 0)
        field(grid, "Высота, мм", "h", 1, 1)

        # ----- Растягивание -----
        T.field_label(self.props_frame, "Растянуть на всю этикетку").pack(anchor="w", pady=(12, 4))
        stretch = ctk.CTkFrame(self.props_frame, fg_color="transparent")
        stretch.pack(fill="x")
        for text, cmd in [("↔", self.fill_width), ("↕", self.fill_height), ("⛶", self.fill_selected)]:
            T.button(stretch, text, cmd, height=32, width=44, font_size=15
                     ).pack(side="left", padx=(0, 6))
        T.label(stretch, "отступ", size=11, color=T.TEXT_2).pack(side="left", padx=(4, 4))
        T.entry(stretch, self.fill_margin_var, width=46, height=32).pack(side="left")

        # ----- Специфичные настройки для text -----
        if el["type"] == "text":
            T.field_label(self.props_frame, "Текст").pack(anchor="w", pady=(12, 2))

            text_var = tk.StringVar(value=el.get("text", ""))
            text_entry = T.entry(self.props_frame, text_var, height=34)
            text_entry.pack(fill="x", pady=(0, 4))

            def commit_text(event=None):
                el["text"] = text_var.get()
                self.redraw()

            text_entry.bind("<Return>", commit_text)
            text_entry.bind("<FocusOut>", commit_text)

            T.label(self.props_frame,
                    "{code} — код этикетки, {name}, {price} — данные из CSV/Excel",
                    size=11, color=T.TEXT_3, wraplength=240, justify="left"
                    ).pack(anchor="w", pady=(0, 6))

            size_box = ctk.CTkFrame(self.props_frame, fg_color="transparent")
            size_box.pack(fill="x")
            field(size_box, "Шрифт, pt", "font_size", 0, 0, width=80)

        # ----- Специфичные настройки для image -----
        elif el["type"] == "image":
            T.field_label(self.props_frame, "Файл").pack(anchor="w", pady=(12, 2))

            file_row = ctk.CTkFrame(self.props_frame, fg_color="transparent")
            file_row.pack(fill="x", pady=(0, 4))

            T.label(file_row, os.path.basename(el.get("src", ""))[:26], size=12,
                    wraplength=170, justify="left"
                    ).pack(side="left", fill="x", expand=True)
            T.button(file_row, "Заменить", self.replace_image, height=30
                     ).pack(side="right")

        # ----- Кнопка удаления -----
        can_delete = len(self.template["elements"]) > 1
        T.button(self.props_frame,
                 "Удалить элемент" if can_delete else "Последний элемент нельзя удалить",
                 self.delete_selected, variant="danger" if can_delete else "ghost",
                 height=36, state="normal" if can_delete else "disabled",
                 ).pack(fill="x", pady=(16, 0))

    # ========== ДЕЙСТВИЯ ==========
    def add_barcode_element(self):
        existing = sum(1 for e in self.template["elements"] if e["type"] == "barcode")
        w_mm = self.template["label_width"]
        h_mm = self.template["label_height"]
        self.template["elements"].append({
            "id": f"barcode_{existing}_{len(self.template['elements'])}",
            "type": "barcode",
            "x": round(max(0.0, w_mm / 2 - 20), 1),
            "y": round(max(0.0, h_mm / 2 - 10), 1),
            "w": min(40, w_mm),
            "h": min(20, h_mm),
        })
        self.selected_index = len(self.template["elements"]) - 1
        self.redraw()

    def add_text_element(self):
        existing = sum(1 for e in self.template["elements"] if e["type"] == "text")
        w_mm = self.template["label_width"]
        h_mm = self.template["label_height"]
        self.template["elements"].append({
            "id": f"custom_text_{existing}_{len(self.template['elements'])}",
            "type": "text", "text": "Текст",
            "x": round(max(0.0, w_mm / 2 - 15), 1),
            "y": round(max(0.0, h_mm / 2 - 3), 1),
            "w": 30, "h": 6, "font_size": 9,
        })
        self.selected_index = len(self.template["elements"]) - 1
        self.redraw()

    def add_image_element(self):
        """Открывает диалог выбора картинки и добавляет элемент 'image'."""
        path = filedialog.askopenfilename(
            title="Выберите картинку для этикетки",
            filetypes=[
                ("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif"),
                ("Все файлы", "*.*"),
            ]
        )
        if not path:
            return

        # Копируем картинку в папку данных приложения (assets/)
        try:
            from settings import APP_DATA_PATH
            assets_dir = os.path.join(APP_DATA_PATH, "assets")
            os.makedirs(assets_dir, exist_ok=True)
            fname = os.path.basename(path)
            dst = os.path.join(assets_dir, f"{uuid.uuid4().hex[:8]}_{fname}")
            shutil.copy(path, dst)
        except Exception as e:
            logger.error(f"Не удалось скопировать картинку: {e}")
            messagebox.showerror("Ошибка", f"Не удалось скопировать файл:\n{e}")
            return

        w_mm = self.template["label_width"]
        h_mm = self.template["label_height"]

        self.template["elements"].append({
            "id": f"image_{len(self.template['elements'])}",
            "type": "image",
            "src": dst,
            "x": round(max(0.0, w_mm / 2 - 10), 1),
            "y": round(max(0.0, h_mm / 2 - 10), 1),
            "w": min(20, w_mm),
            "h": min(20, h_mm),
        })
        self.selected_index = len(self.template["elements"]) - 1
        self.redraw()
        logger.info(f"Добавлена картинка: {os.path.basename(dst)}")

    def replace_image(self):
        """Заменяет картинку у выделенного элемента 'image'."""
        if self.selected_index is None:
            return
        el = self.template["elements"][self.selected_index]
        if el["type"] != "image":
            return

        path = filedialog.askopenfilename(
            title="Выберите новую картинку",
            filetypes=[
                ("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif"),
                ("Все файлы", "*.*"),
            ]
        )
        if not path:
            return
        try:
            from settings import APP_DATA_PATH
            assets_dir = os.path.join(APP_DATA_PATH, "assets")
            os.makedirs(assets_dir, exist_ok=True)
            fname = os.path.basename(path)
            dst = os.path.join(assets_dir, f"{uuid.uuid4().hex[:8]}_{fname}")
            shutil.copy(path, dst)
            el["src"] = dst
            self.redraw()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось заменить:\n{e}")

    def _get_margin(self):
        try:
            return max(0.0, float(self.fill_margin_var.get()))
        except ValueError:
            return 0.0

    def fill_width(self):
        """Растягивает элемент по ширине листа с учётом отступа."""
        if self.selected_index is None:
            return
        el = self.template["elements"][self.selected_index]
        m = self._get_margin()
        el["x"] = round(m, 1)
        el["w"] = round(max(MIN_SIZE_MM, self.template["label_width"] - 2 * m), 1)
        self.redraw()

    def fill_height(self):
        """Растягивает элемент по высоте листа с учётом отступа."""
        if self.selected_index is None:
            return
        el = self.template["elements"][self.selected_index]
        m = self._get_margin()
        el["y"] = round(m, 1)
        el["h"] = round(max(MIN_SIZE_MM, self.template["label_height"] - 2 * m), 1)
        self.redraw()

    def fill_selected(self):
        """Растягивает элемент на весь лист по обеим осям с учётом отступа."""
        if self.selected_index is None:
            return
        el = self.template["elements"][self.selected_index]
        m = self._get_margin()
        el["x"], el["y"] = round(m, 1), round(m, 1)
        el["w"] = round(max(MIN_SIZE_MM, self.template["label_width"] - 2 * m), 1)
        el["h"] = round(max(MIN_SIZE_MM, self.template["label_height"] - 2 * m), 1)
        self.redraw()

    def delete_selected(self):
        if self.selected_index is None:
            return
        if len(self.template["elements"]) <= 1:
            return
        del self.template["elements"][self.selected_index]
        self.selected_index = None
        self.redraw()

    def apply_size(self):
        try:
            w = float(self.width_var.get())
            h = float(self.height_var.get())
            if w <= 0 or h <= 0:
                raise ValueError
            self.template["label_width"] = w
            self.template["label_height"] = h
            self.redraw()
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректные числа для размера этикетки")

    def reset_template(self):
        if messagebox.askyesno("Подтверждение", "Сбросить шаблон к стандартному виду?"):
            self.template = default_template(self.template["label_width"],
                                              self.template["label_height"])
            self.selected_index = None
            self.redraw()

    # ========== ИМЕНОВАННЫЕ ШАБЛОНЫ ==========
    def load_named_template(self, name):
        """Загружает сохранённый шаблон по имени."""
        if name in self.templates:
            self.template = copy.deepcopy(self.templates[name])
        else:
            self.template = default_template(
                float(self.app.label_width.get() or 58),
                float(self.app.label_height.get() or 40),
            )
        self.current_name = name
        self.selected_index = None
        self.width_var.set(str(self.template["label_width"]))
        self.height_var.set(str(self.template["label_height"]))
        self.redraw()
        logger.info(f"Загружен шаблон: {name}")

    def save_as_new_template(self):
        """Сохраняет текущий шаблон под новым именем."""
        dialog = ctk.CTkInputDialog(text="Введите имя шаблона:", title="Сохранить как")
        name = dialog.get_input()
        if not name or not name.strip():
            return
        name = name.strip()

        self.templates[name] = copy.deepcopy(self.template)
        self.current_name = name

        values = list(self.templates.keys())
        self.template_menu.configure(values=values)
        self.template_var.set(name)

        # Сохраняем в settings сразу
        self.app.settings.set("label_templates", self.templates)
        self.app.settings.set("current_template", name)

        messagebox.showinfo("Сохранено", f"Шаблон «{name}» сохранён")
        logger.info(f"Сохранён новый шаблон: {name}")

    def delete_current_template(self):
        """Удаляет текущий именованный шаблон."""
        if self.current_name not in self.templates:
            messagebox.showinfo("Информация", "Этот шаблон ещё не сохранён")
            return
        if not messagebox.askyesno("Удаление", f"Удалить шаблон «{self.current_name}»?"):
            return

        del self.templates[self.current_name]
        self.current_name = "По умолчанию"
        self.template = default_template(
            float(self.app.label_width.get() or 58),
            float(self.app.label_height.get() or 40),
        )

        values = list(self.templates.keys()) or ["По умолчанию"]
        self.template_menu.configure(values=values)
        self.template_var.set(self.current_name)
        self.selected_index = None
        self.redraw()

        self.app.settings.set("label_templates", self.templates)
        self.app.settings.set("current_template", self.current_name)
        logger.info(f"Удалён шаблон: {self.current_name}")

    def save_template(self):
        """Сохраняет текущий шаблон и делает его активным."""
        self.templates[self.current_name] = copy.deepcopy(self.template)
        self.app.settings.update({
            "label_templates": self.templates,
            "current_template": self.current_name,
            "label_template": self.template,  # активный для PDF
        })

        # Размер страницы = размер шаблона только при одной этикетке на странице.
        # При раскладке сеткой страница — это лист, на который шаблон вписывается,
        # и её размер трогать нельзя.
        if int(self.app.labels_per_page.get()) == 1:
            self.app.label_width.set(str(self.template["label_width"]))
            self.app.label_height.set(str(self.template["label_height"]))
        self.app.save_current_settings()
        self.app.generator.load_settings()
        self.app.update_all()

        messagebox.showinfo("Сохранено",
                             f"Шаблон «{self.current_name}» сохранён и активен")
        logger.info(f"Шаблон сохранён и активен: {self.current_name}")
        self.destroy()