# gui/gui_widgets.py - Кастомные виджеты для интерфейса (CustomTkinter)
#
# Новые экраны собираются из фабрик в gui/theme.py. Обёртки ниже
# сохраняют старый интерфейс использования (в т.ч. атрибут .frame
# для packing), чтобы внешний код, который на них опирается, не сломался.

import tkinter as tk
import customtkinter as ctk

from . import theme as T

# Старое имя подсказки — теперь это подсказка из темы
BalloonTooltip = T.Tooltip


class ModernButton(ctk.CTkButton):
    """Тонкая обёртка над CTkButton, совместимая по сигнатуре со старым
    ModernButton(parent, text, command, **kwargs). padx игнорируется,
    pady грубо конвертируется в высоту кнопки."""

    def __init__(self, parent, text="", command=None, **kwargs):
        kwargs.pop('padx', None)
        pady = kwargs.pop('pady', None)
        height = kwargs.pop('height', 40 if pady is None else 28 + int(pady))
        corner_radius = kwargs.pop('corner_radius', height // 2)
        font = kwargs.pop('font', T.font(13))

        super().__init__(
            parent, text=text, command=command,
            height=height, corner_radius=corner_radius, font=font,
            **kwargs
        )


class ModernEntry(ctk.CTkEntry):
    """Обёртка над CTkEntry. Старый код передавал width в символах
    (как у tk.Entry, например width=8) - конвертируем в пиксели."""

    def __init__(self, parent, **kwargs):
        width = kwargs.pop('width', None)
        if width is not None and width <= 60:
            width = max(64, int(width) * 11)
        kwargs['width'] = width if width else 140
        kwargs.setdefault('height', 40)
        kwargs.setdefault('font', T.font(13))
        super().__init__(parent, **kwargs)


class CustomRadiobutton:
    """Обёртка над CTkRadioButton: CustomRadiobutton(parent, text, variable, value, callback=None).
    Атрибут .frame - сам CTkRadioButton."""

    def __init__(self, parent, text, variable, value, callback=None):
        self.variable = variable
        self.value = value
        self.callback = callback
        self.frame = ctk.CTkRadioButton(
            parent, text=text, variable=variable, value=value,
            command=self._on_select, font=T.font(13),
        )
        self.frame.pack(anchor="w", pady=4)

    def _on_select(self):
        if self.callback:
            self.callback()


class CustomCheckbutton:
    """Обёртка над переключателем: CustomCheckbutton(parent, text, variable, callback=None)."""

    def __init__(self, parent, text, variable, callback=None):
        self.variable = variable
        self.callback = callback
        self.frame = T.switch(parent, text, variable, command=self._on_toggle)
        self.frame.pack(anchor="w", pady=6)

    def _on_toggle(self):
        if self.callback:
            self.callback()


class ContextMenu:
    """Контекстное меню (ПКМ) для текстового поля. Работает и с обычным
    tk.Text, и с CTkTextbox - у последнего методы get/insert/delete/tag_*
    и event_generate проброшены к внутреннему tk.Text."""

    def __init__(self, root, text_widget):
        self.root = root
        self.text_widget = text_widget
        self.menu = None
        self.create_menu()

    def create_menu(self):
        self.menu = tk.Menu(
            self.text_widget, tearoff=0,
            bg=T.SURFACE, fg=T.TEXT,
            activebackground=T.BLUE_SOFT, activeforeground=T.ROYAL,
            relief="flat", borderwidth=0, font=(T.FONT_UI, 10),
        )

        items = [
            ("Вырезать", self.cut), ("Копировать", self.copy),
            ("Вставить", self.paste), (None, None), ("Удалить", self.delete),
            (None, None), ("Выделить всё", self.select_all)
        ]

        for text, cmd in items:
            if text is None:
                self.menu.add_separator()
            else:
                self.menu.add_command(label=text, command=cmd)

        self.text_widget.bind("<Button-3>", self.show)
        self.root.bind("<Button-1>", lambda e: self.root.after(100, self.close), add="+")

    def show(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def close(self):
        try:
            self.menu.unpost()
        except Exception:
            pass

    def cut(self):
        self.text_widget.event_generate("<<Cut>>")
        self.close()

    def copy(self):
        self.text_widget.event_generate("<<Copy>>")
        self.close()

    def select_all(self):
        self.text_widget.tag_add('sel', '1.0', 'end')
        self.close()

    def paste(self):
        try:
            clip = self.root.clipboard_get()
        except Exception:
            self.close()
            return
        try:
            self.text_widget.delete("sel.first", "sel.last")
        except Exception:
            pass
        try:
            self.text_widget.insert("insert", clip)
        except Exception:
            pass
        self.close()

    def delete(self):
        try:
            self.text_widget.delete("sel.first", "sel.last")
        except Exception:
            pos = self.text_widget.index("insert")
            self.text_widget.delete(f"{pos} linestart", f"{pos} lineend +1c")
        self.close()


class SettingsWindow(ctk.CTkToplevel):
    """Каркас окна настроек: крупный заголовок, прокручиваемые карточки-секции,
    внизу «Отмена» и «Сохранить». Наследник строит секции в build() и
    применяет изменения в apply() — до нажатия «Сохранить» ничего не меняется."""

    def __init__(self, master, title_text, subtitle, width=620, height=720):
        super().__init__(master)
        T.setup_dialog(self, master, title_text, width, height)
        self.protocol("WM_DELETE_WINDOW", self._safe_close)
        self.bind("<Escape>", lambda e: self._safe_close())
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(26, 14))
        T.title(head, title_text, size=24).pack(anchor="w")
        T.label(head, subtitle, size=13, color=T.TEXT_2).pack(anchor="w", pady=(2, 0))

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=(20, 12))

        foot = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=0)
        foot.grid(row=2, column=0, sticky="ew")
        ctk.CTkFrame(foot, fg_color=T.BORDER, height=1, corner_radius=0).pack(side="top", fill="x")
        T.button(foot, "Сохранить", self._on_save, variant="primary", width=150
                 ).pack(side="right", padx=(8, 24), pady=14)
        T.button(foot, "Отмена", self._safe_close, variant="ghost", width=110
                 ).pack(side="right", pady=14)

        self._section_count = 0
        self.build()

    # --- для наследников ---
    def build(self):
        pass

    def apply(self):
        pass

    # --- строительные блоки ---
    def section(self, title_text, hint=None):
        """Карточка-секция с номером шага; возвращает внутренний фрейм для содержимого."""
        self._section_count += 1
        box = T.card(self.body)
        box.pack(fill="x", pady=(0, 12), padx=(0, 6))
        T.step_title(box, self._section_count, title_text).pack(anchor="w", padx=20, pady=(16, 0))
        if hint:
            T.label(box, hint, size=12, color=T.TEXT_2, justify="left",
                    wraplength=500).pack(anchor="w", padx=(58, 20), pady=(4, 0))
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=(12, 18))
        return inner

    @staticmethod
    def number_fields(parent, fields, suffix="мм"):
        """Ряд числовых полей: [(подпись, StringVar), ...]."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x")
        for i, (text, var) in enumerate(fields):
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", padx=(0 if i == 0 else 14, 0))
            T.field_label(col, f"{text}, {suffix}" if suffix else text).pack(anchor="w")
            T.entry(col, var, width=96).pack(anchor="w", pady=(4, 0))
        return row

    def _on_save(self):
        try:
            self.apply()
        except Exception as e:
            from logger import logger
            from tkinter import messagebox
            logger.error(f"Ошибка сохранения настроек: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}", parent=self)
            return
        self._safe_close()

    def _safe_close(self):
        """Закрывает окно и возвращает непрозрачность родителю (баг Windows)."""
        try:
            self.grab_release()
        except Exception:
            pass
        master = self.master
        try:
            self.destroy()
        except Exception:
            pass
        fix_transparency_after_close(master)


def fix_transparency_after_close(parent):
    """Принудительно сбрасывает прозрачность родительского окна.
    Баг customtkinter на Windows: transient-окно оставляет родителя
    'призрачным' после закрытия."""
    try:
        import sys
        if sys.platform == "win32":
            parent.attributes("-alpha", 1.0)
            parent.update_idletasks()
    except Exception:
        pass
