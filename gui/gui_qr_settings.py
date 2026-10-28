# gui/gui_qr_settings.py - Окно настроек модуля «QR-паспорта»

import os
import shutil
import uuid
import tkinter as tk
from tkinter import filedialog

from . import theme as T
from .gui_widgets import SettingsWindow
from utils import QR_BOX_SIZE_PRESETS, DEFAULT_QR_BOX_SIZE
from logger import logger

FORMATS = {"text": "Текст", "json": "JSON"}
LOGO_MODES = {"none": "Нет", "drop": "Капля", "file": "Свой файл"}


def _box_hint(value):
    for v, desc in QR_BOX_SIZE_PRESETS:
        if v == value:
            return desc.split(" — ", 1)[-1].capitalize()
    return ""


class QRSettingsWindow(SettingsWindow):
    """Окно настроек только для QR-паспортов."""

    def __init__(self, master, qr_tab):
        self.qr_tab = qr_tab
        self.app = qr_tab.app
        s = self.app.settings
        self.qr_w = tk.StringVar(value=s.get("qr_label_width", "58"))
        self.qr_h = tk.StringVar(value=s.get("qr_label_height", "40"))
        self.qr_mt = tk.StringVar(value=s.get("qr_margin_top", "5"))
        self.qr_mb = tk.StringVar(value=s.get("qr_margin_bottom", "5"))
        self.qr_ml = tk.StringVar(value=s.get("qr_margin_left", "5"))
        self.qr_mr = tk.StringVar(value=s.get("qr_margin_right", "5"))
        self.qr_box_size = tk.StringVar(value=str(s.get("qr_box_size", DEFAULT_QR_BOX_SIZE)))
        self.qr_format = tk.StringVar(value=FORMATS.get(qr_tab.qr_format.get(), "Текст"))
        self.qr_show_border = tk.BooleanVar(value=s.get("qr_show_border", False))
        logo = s.get("qr_logo", "none") or "none"
        self.logo_path = logo if logo not in ("none", "drop") else ""
        self.logo_mode = tk.StringVar(value=LOGO_MODES["file" if self.logo_path else logo])

        super().__init__(master, "Настройки QR-паспортов",
                         "Не зависят от настроек штрихкодов", width=600, height=720)

    def build(self):
        size = self.section("Размер этикетки")
        self.number_fields(size, [("Ширина", self.qr_w), ("Высота", self.qr_h)])

        margins = self.section("Поля", "Расстояние от края этикетки до QR-кода")
        self.number_fields(margins, [("Сверху", self.qr_mt), ("Снизу", self.qr_mb),
                                     ("Слева", self.qr_ml), ("Справа", self.qr_mr)])

        quality = self.section("Качество QR", "Размер одной клетки QR-кода в пикселях")
        T.segmented(quality, [v for v, _ in QR_BOX_SIZE_PRESETS], variable=self.qr_box_size,
                    command=lambda v: self.box_hint.configure(text=_box_hint(v))
                    ).pack(anchor="w")
        self.box_hint = T.label(quality, _box_hint(self.qr_box_size.get()), size=12, color=T.TEXT_2)
        self.box_hint.pack(anchor="w", pady=(8, 0))

        fmt = self.section("Содержимое QR",
                           "Текст удобно читать телефоном, JSON — обрабатывать программой")
        T.segmented(fmt, list(FORMATS.values()), variable=self.qr_format).pack(anchor="w")

        logo = self.section("Логотип в центре QR",
                            "Код остаётся читаемым: включается максимальная коррекция ошибок")
        T.segmented(logo, list(LOGO_MODES.values()), variable=self.logo_mode,
                    command=self._on_logo_mode).pack(anchor="w")
        self.logo_label = T.label(logo, self._logo_caption(), size=12, color=T.TEXT_2)
        self.logo_label.pack(anchor="w", pady=(8, 0))

        extra = self.section("Дополнительно")
        T.switch(extra, "Рисовать рамку вокруг этикетки", self.qr_show_border).pack(anchor="w")

    def _logo_caption(self):
        if self.logo_mode.get() == LOGO_MODES["file"] and self.logo_path:
            return f"Файл: {os.path.basename(self.logo_path)}"
        if self.logo_mode.get() == LOGO_MODES["drop"]:
            return "Фирменная капля из бутылок"
        return "QR без логотипа"

    def _on_logo_mode(self, value):
        if value == LOGO_MODES["file"]:
            path = filedialog.askopenfilename(
                parent=self, title="Логотип для QR",
                filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif"), ("Все файлы", "*.*")])
            if path:
                # Копия в папку данных: исходный файл могут переместить или удалить
                from settings import APP_DATA_PATH
                assets = os.path.join(APP_DATA_PATH, "assets")
                os.makedirs(assets, exist_ok=True)
                dst = os.path.join(assets, f"qrlogo_{uuid.uuid4().hex[:8]}_{os.path.basename(path)}")
                shutil.copy(path, dst)
                self.logo_path = dst
            elif not self.logo_path:
                self.logo_mode.set(LOGO_MODES["none"])
        self.logo_label.configure(text=self._logo_caption())

    def apply(self):
        for var in (self.qr_w, self.qr_h):
            if float(var.get()) <= 0:
                raise ValueError("Ширина и высота должны быть больше 0")
        for var in (self.qr_mt, self.qr_mb, self.qr_ml, self.qr_mr):
            float(var.get())

        fmt = next((k for k, v in FORMATS.items() if v == self.qr_format.get()), "text")
        s = self.app.settings
        s.update({
            "qr_label_width": self.qr_w.get(),
            "qr_label_height": self.qr_h.get(),
            "qr_margin_top": self.qr_mt.get(),
            "qr_margin_bottom": self.qr_mb.get(),
            "qr_margin_left": self.qr_ml.get(),
            "qr_margin_right": self.qr_mr.get(),
            "qr_box_size": self.qr_box_size.get(),
            "qr_format": fmt,
            "qr_show_border": self.qr_show_border.get(),
            "qr_logo": {LOGO_MODES["none"]: "none", LOGO_MODES["drop"]: "drop"}.get(
                self.logo_mode.get(), self.logo_path or "none"),
        })

        self.qr_tab.qr_format.set(fmt)
        self.qr_tab.sync_format()
        self.app.set_status("Настройки QR сохранены", 'success')
        logger.info("✅ QR-настройки сохранены")
