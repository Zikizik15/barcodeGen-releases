# gui/gui_barcode_settings.py - Окно настроек модуля «Штрихкоды»
#
# Работает с копиями значений: главное окно меняется только по «Сохранить».
# Тип кода выбирается прямо на главном экране, поэтому здесь его нет.

import tkinter as tk
import customtkinter as ctk

from . import theme as T
from .gui_widgets import SettingsWindow
from utils import LABEL_PRESETS, LABELS_PER_PAGE_OPTIONS, DPI_PRESETS, DEFAULT_DPI
from logger import logger

CUSTOM_PRESET = "Свой размер"


def _dpi_hint(dpi):
    for value, desc in DPI_PRESETS:
        if value == dpi:
            return desc.split(" — ", 1)[-1].capitalize()
    return ""


class BarcodeSettingsWindow(SettingsWindow):
    """Окно настроек только для модуля «Штрихкоды»."""

    def __init__(self, master, app):
        self.app = app
        a = app
        # Локальные копии — до «Сохранить» главное окно не меняется
        self.width_var = tk.StringVar(value=a.label_width.get())
        self.height_var = tk.StringVar(value=a.label_height.get())
        self.margins = [tk.StringVar(value=v.get()) for v in
                        (a.margin_top, a.margin_bottom, a.margin_left, a.margin_right)]
        self.per_page_var = tk.StringVar(value=str(a.labels_per_page.get()))
        self.dpi_var = tk.StringVar(value=a.barcode_dpi.get() or DEFAULT_DPI)
        self.selected_only = tk.BooleanVar(value=a.selected_only.get())
        self.batch_mode = tk.BooleanVar(value=a.batch_mode.get())
        self.show_border = tk.BooleanVar(value=a.show_border.get())
        self.use_template = tk.BooleanVar(value=a.use_template.get())
        self.show_text = tk.BooleanVar(value=a.show_text.get())
        preset = a.selected_preset.get()
        self.preset_var = tk.StringVar(value=preset if preset in LABEL_PRESETS else CUSTOM_PRESET)

        super().__init__(master, "Настройки штрихкодов",
                         "Размер этикетки, раскладка и качество печати")

    def build(self):
        # ----- Размер этикетки -----
        size = self.section("Размер этикетки", "Выберите готовый размер или введите свой")
        T.option_menu(size, values=list(LABEL_PRESETS.keys()) + [CUSTOM_PRESET],
                      variable=self.preset_var, command=self._apply_preset, width=440
                      ).pack(anchor="w", pady=(0, 12))
        self.number_fields(size, [("Ширина", self.width_var), ("Высота", self.height_var)])
        for var in (self.width_var, self.height_var):
            var.trace_add("write", self._on_manual_size)

        # ----- Отступы -----
        margins = self.section("Поля", "Расстояние от края этикетки до штрихкода")
        self.number_fields(margins, list(zip(("Сверху", "Снизу", "Слева", "Справа"), self.margins)))

        # ----- Раскладка -----
        layout = self.section("Этикеток на одной странице PDF")
        T.segmented(layout, [str(v) for v in LABELS_PER_PAGE_OPTIONS],
                    variable=self.per_page_var).pack(anchor="w")

        # ----- Качество -----
        quality = self.section("Качество штрихкода",
                               "Больше DPI — чётче при печати, но дольше генерация и тяжелее файл")
        T.segmented(quality, [v for v, _ in DPI_PRESETS], variable=self.dpi_var,
                    command=lambda v: self.dpi_hint.configure(text=_dpi_hint(v))
                    ).pack(anchor="w")
        self.dpi_hint = T.label(quality, _dpi_hint(self.dpi_var.get()), size=12, color=T.TEXT_2)
        self.dpi_hint.pack(anchor="w", pady=(8, 0))

        # ----- Дополнительно -----
        extra = self.section("Дополнительно")
        for text, var in [
            ("Печатать код под штрихкодом (без шаблона)", self.show_text),
            ("Генерировать только выделенные строки", self.selected_only),
            ("Сохранять картинки в ZIP вместо PDF", self.batch_mode),
            ("Рисовать рамку вокруг этикетки", self.show_border),
            ("Использовать сохранённый шаблон этикетки", self.use_template),
        ]:
            T.switch(extra, text, var).pack(anchor="w", pady=5)

    def _apply_preset(self, name):
        if name in LABEL_PRESETS:
            w, h = LABEL_PRESETS[name]
            self._setting_preset = True
            self.width_var.set(w)
            self.height_var.set(h)
            self._setting_preset = False

    def _on_manual_size(self, *_):
        # Ручной ввод размера — пресет больше не соответствует
        if not getattr(self, "_setting_preset", False):
            self.preset_var.set(CUSTOM_PRESET)

    def apply(self):
        w, h = float(self.width_var.get()), float(self.height_var.get())
        if w <= 0 or h <= 0:
            raise ValueError("Ширина и высота должны быть больше 0")
        for var in self.margins:
            float(var.get())

        a = self.app
        a.label_width.set(self.width_var.get())
        a.label_height.set(self.height_var.get())
        for target, var in zip((a.margin_top, a.margin_bottom, a.margin_left, a.margin_right),
                               self.margins):
            target.set(var.get())
        a.labels_per_page.set(int(self.per_page_var.get()))
        a.barcode_dpi.set(self.dpi_var.get())
        a.selected_only.set(self.selected_only.get())
        a.batch_mode.set(self.batch_mode.get())
        a.show_border.set(self.show_border.get())
        a.use_template.set(self.use_template.get())
        a.show_text.set(self.show_text.get())
        if self.preset_var.get() in LABEL_PRESETS:
            a.selected_preset.set(self.preset_var.get())
            a.settings.set("selected_preset", self.preset_var.get())

        a.save_current_settings()
        a.generator.load_settings()
        a.update_all()
        a.set_status("Настройки штрихкодов сохранены", 'success')
        logger.info("✅ Настройки штрихкодов сохранены")
