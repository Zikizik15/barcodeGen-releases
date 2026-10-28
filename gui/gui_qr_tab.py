# gui/gui_qr_tab.py - Вкладка "QR-паспорт"
#
# Пользователь заполняет ФИО / комплект / дату выдачи, на выходе получает
# QR-код, который при сканировании выдаёт читаемый текст:
#
#   ФИО: Иванов Иван Иванович
#   Комплект: Куртка, Ботинки, Перчатки
#   Дата выдачи: 2024-05-15

import os
import csv
import tempfile
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from . import theme as T
from logger import logger
from utils import open_pdf, DEFAULT_QR_BOX_SIZE

PREVIEW_SIZE = 210
FORMAT_LABELS = {"text": "Текст", "json": "JSON"}


def build_qr_text(record):
    """Человекочитаемый текст для QR."""
    lines = []
    if record.get("fio"):
        lines.append(f"ФИО: {record['fio']}")
    if record.get("kit"):
        lines.append(f"{record['kit']}")
    if record.get("date"):
        lines.append(f"Дата: {record['date']}")
    return "\n".join(lines)


def build_qr_payload(record, fmt="text"):
    if fmt == "json":
        import json
        return json.dumps({
            "fio": record.get("fio", ""),
            "kit": record.get("kit", ""),
            "date": record.get("date", ""),
        }, ensure_ascii=False)
    return build_qr_text(record)


def _plural_records(n):
    m = n % 100
    if 11 <= m <= 19:
        return "записей"
    m %= 10
    return "запись" if m == 1 else "записи" if 2 <= m <= 4 else "записей"


class QRPassportTab:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.records = list(app.settings.get("qr_records", []) or [])
        self.qr_format = ctk.StringVar(value=app.settings.get("qr_format", "text"))
        self._preview_image = None
        self._build_ui()
        self.refresh_list()
        self.refresh_preview()

    # ================= UI =================
    def _build_ui(self):
        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_rowconfigure(1, weight=1)

        # ===== Хедер вкладки =====
        header = ctk.CTkFrame(self.parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=36, pady=(28, 0))

        T.overline(header, "QR-паспорта").pack(anchor="w")
        T.title(header, "Список паспортов").pack(anchor="w")

        chips = ctk.CTkFrame(header, fg_color="transparent")
        chips.pack(anchor="w", pady=(6, 0))
        self.meta_chips = [T.chip(chips, "", strong=(i == 0)) for i in range(3)]
        for c in self.meta_chips:
            c.pack(side="left", padx=(0, 6))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(fill="x", pady=(18, 0))

        T.button(actions, "Создать PDF", self.export_pdf, variant="primary",
                 height=50, width=210, icon_name="play").pack(side="left")
        T.button(actions, "Импорт CSV", self.import_csv, height=50, width=150
                 ).pack(side="left", padx=(10, 0))
        T.button(actions, "Экспорт CSV", self.export_csv, height=50, width=150
                 ).pack(side="left", padx=(10, 0))
        T.icon_button(actions, "settings", self.show_qr_settings, size=50,
                      tooltip="Настройки QR: размер этикетки, отступы, качество"
                      ).pack(side="left", padx=(10, 0))

        # ===== Контент: слева форма и список, справа предпросмотр =====
        body = ctk.CTkFrame(self.parent, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=36, pady=(24, 24))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        self._build_form(body)
        self._build_list(body)
        self._build_preview(body)

    def _build_form(self, parent):
        form = T.card(parent)
        form.grid(row=0, column=0, sticky="ew")
        form.grid_columnconfigure(0, weight=1)

        T.section_title(form, "Новая запись").grid(row=0, column=0, columnspan=2,
                                                    sticky="w", padx=22, pady=(18, 10))

        T.step_title(form, 1, "ФИО", size=12).grid(row=1, column=0, sticky="w", padx=(22, 0))
        T.step_title(form, 2, "Дата выдачи", size=12).grid(row=1, column=1, sticky="w", padx=(12, 22))

        self.entry_fio = T.entry(form, placeholder="Иванов Иван Иванович")
        self.entry_fio.grid(row=2, column=0, sticky="ew", padx=(22, 0), pady=(4, 12))
        self.entry_fio.bind("<KeyRelease>", lambda e: self.refresh_preview())

        date_row = ctk.CTkFrame(form, fg_color="transparent")
        date_row.grid(row=2, column=1, sticky="w", padx=(12, 22), pady=(4, 12))
        self.entry_date = T.entry(date_row, width=130)
        self.entry_date.pack(side="left")
        self.entry_date.insert(0, datetime.now().strftime("%d-%m-%Y"))
        self.entry_date.bind("<KeyRelease>", lambda e: self.refresh_preview())
        T.button(date_row, "Сегодня", self._set_today, width=90
                 ).pack(side="left", padx=(8, 0))

        T.step_title(form, 3, "Данные: комплект, номер, что угодно", size=12
                     ).grid(row=3, column=0, columnspan=2, sticky="w", padx=22)
        self.text_kit = ctk.CTkTextbox(form, height=58, fg_color=T.SURFACE_2,
                                       corner_radius=12, border_width=0,
                                       font=T.font(13), border_spacing=8)
        self.text_kit.grid(row=4, column=0, columnspan=2, sticky="ew", padx=22, pady=(4, 14))
        self.text_kit._textbox.configure(insertbackground=T.TEXT)
        self.text_kit.bind("<KeyRelease>", lambda e: self.refresh_preview())

        T.button(form, "Добавить запись", self.add_record, variant="inverse",
                 width=180, icon_name="plus"
                 ).grid(row=5, column=0, columnspan=2, sticky="e", padx=22, pady=(0, 18))

    def _set_today(self):
        self.entry_date.delete(0, "end")
        self.entry_date.insert(0, datetime.now().strftime("%d-%m-%Y"))
        self.refresh_preview()

    def _build_list(self, parent):
        box = T.card(parent)
        box.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(box, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=22, pady=(16, 6))
        T.section_title(head, "Записи").pack(side="left")
        self.count_label = T.label(head, "", size=13, color=T.TEXT_2)
        self.count_label.pack(side="left", padx=(10, 0))
        T.button(head, "Очистить все", self.clear_all, variant="ghost", height=32
                 ).pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(box, fg_color="transparent", height=120)
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 10))

    def _build_preview(self, parent):
        side = T.card(parent, width=300)
        side.grid(row=0, column=1, rowspan=2, sticky="ns", padx=(16, 0))
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(4, weight=1)

        T.section_title(side, "Предпросмотр").grid(row=0, column=0, sticky="w",
                                                    padx=22, pady=(18, 10))

        self.format_display = ctk.StringVar(value=FORMAT_LABELS.get(self.qr_format.get(), "Текст"))
        T.segmented(side, list(FORMAT_LABELS.values()), variable=self.format_display,
                    command=self._on_format_change
                    ).grid(row=1, column=0, sticky="ew", padx=22)

        tile = ctk.CTkFrame(side, fg_color=T.PAPER, corner_radius=16, border_width=2,
                            border_color=T.BORDER,
                            width=PREVIEW_SIZE + 24, height=PREVIEW_SIZE + 24)
        tile.grid(row=2, column=0, pady=(16, 14))
        tile.grid_propagate(False)
        tile.pack_propagate(False)
        self.preview_label = ctk.CTkLabel(tile, text="", fg_color=T.PAPER,
                                          text_color="#8A8A92", font=T.font(12),
                                          wraplength=PREVIEW_SIZE - 20)
        self.preview_label.place(relx=0.5, rely=0.5, anchor="center")

        T.field_label(side, "Что увидит сканер").grid(row=3, column=0, sticky="w", padx=22)
        self.payload_box = ctk.CTkTextbox(side, fg_color=T.SURFACE_2, corner_radius=12,
                                          border_width=0, font=T.font(12, mono=True),
                                          text_color=T.TEXT_2, border_spacing=8)
        self.payload_box.grid(row=4, column=0, sticky="nsew", padx=22, pady=(4, 20))

    # ================= ЛОГИКА =================
    def _current_record(self):
        return {
            "fio": self.entry_fio.get().strip(),
            "kit": self.text_kit.get("1.0", "end").strip(),
            "date": self.entry_date.get().strip(),
        }

    def _on_format_change(self, display_value):
        for key, label in FORMAT_LABELS.items():
            if label == display_value:
                self.qr_format.set(key)
        self.app.settings.set("qr_format", self.qr_format.get())
        self.refresh_preview()
        self.update_meta()

    def sync_format(self):
        """Вызывается окном настроек после сохранения."""
        self.format_display.set(FORMAT_LABELS.get(self.qr_format.get(), "Текст"))
        self.refresh_preview()
        self.update_meta()

    def update_meta(self):
        s = self.app.settings
        n = len(self.records)
        parts = [
            f"{n} {_plural_records(n)}",
            FORMAT_LABELS.get(self.qr_format.get(), "Текст"),
            f"{s.get('qr_label_width', '58')}×{s.get('qr_label_height', '40')} мм",
        ]
        for chip, text in zip(self.meta_chips, parts):
            chip.configure(text=text.upper())
        self.count_label.configure(text=str(n) if n else "")

    def refresh_preview(self):
        record = self._current_record()
        payload = build_qr_payload(record, self.qr_format.get())

        self.payload_box.configure(state="normal")
        self.payload_box.delete("1.0", "end")
        self.payload_box.insert("1.0", payload or "Пока пусто")
        self.payload_box.configure(state="disabled")

        if not any(record.values()):
            self.preview_label.configure(image=None, text="Заполните форму —\nздесь появится QR-код")
            self._preview_image = None
            return

        try:
            import qrcode
            bs = int(self.app.settings.get("qr_box_size", DEFAULT_QR_BOX_SIZE))
            qr = qrcode.QRCode(version=None, box_size=bs, border=1)
            qr.add_data(payload)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            self._preview_image = ctk.CTkImage(light_image=img, dark_image=img,
                                               size=(PREVIEW_SIZE, PREVIEW_SIZE))
            self.preview_label.configure(image=self._preview_image, text="")
        except Exception as e:
            logger.warning(f"QR preview error: {e}")
            self.preview_label.configure(image=None, text="Ошибка QR")

    def show_qr_settings(self):
        """Открывает окно настроек модуля «QR-паспорта»."""
        from .gui_qr_settings import QRSettingsWindow
        QRSettingsWindow(self.app.root, self)

    def add_record(self):
        record = self._current_record()
        if not record["fio"]:
            messagebox.showwarning("Внимание", "Укажите ФИО")
            return
        if not record["kit"]:
            messagebox.showwarning("Внимание", "Заполните поле «Данные»")
            return
        if not record["date"]:
            messagebox.showwarning("Внимание", "Укажите дату выдачи")
            return

        self.records.append(record)
        self._persist()
        self.refresh_list()
        self.entry_fio.delete(0, "end")
        self.text_kit.delete("1.0", "end")
        self.refresh_preview()
        self.entry_fio.focus_set()
        self.app.set_status(f"Добавлена запись: {record['fio']}", 'success')
        logger.info(f"Добавлена QR-запись: {record['fio']}")

    def _persist(self):
        self.app.settings.set("qr_records", self.records)
        self.app.settings.set("qr_format", self.qr_format.get())

    def refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()

        self.update_meta()

        if not self.records:
            T.label(self.list_frame, "Пока нет записей — добавьте первую в форме выше",
                    size=13, color=T.TEXT_3).pack(pady=24)
            return

        for i, rec in enumerate(self.records):
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent", corner_radius=12)
            row.pack(fill="x", pady=1)
            row.grid_columnconfigure(1, weight=1)

            T.label(row, str(i + 1), size=13, color=T.TEXT_3, width=30
                    ).grid(row=0, column=0, rowspan=2, padx=(8, 6))
            T.label(row, rec.get("fio", "—"), size=14, weight="bold", anchor="w"
                    ).grid(row=0, column=1, sticky="w", pady=(8, 0))
            kit = (rec.get("kit", "") or "").replace("\n", ", ")
            if len(kit) > 70:
                kit = kit[:70] + "…"
            T.label(row, f"{kit}  ·  {rec.get('date', '')}", size=12, color=T.TEXT_2, anchor="w"
                    ).grid(row=1, column=1, sticky="w", pady=(0, 8))

            ctk.CTkButton(row, text="✕", width=32, height=32, corner_radius=16,
                          fg_color="transparent", hover_color=T.ERROR_BG,
                          text_color=T.TEXT_3, font=T.font(13),
                          command=lambda idx=i: self.delete_record(idx)
                          ).grid(row=0, column=2, rowspan=2, padx=8)
            T.bind_hover(row, "transparent", T.SURFACE_2)

    def delete_record(self, idx):
        if 0 <= idx < len(self.records):
            del self.records[idx]
            self._persist()
            self.refresh_list()

    def clear_all(self):
        if not self.records:
            return
        if messagebox.askyesno("Подтверждение", "Удалить все записи?"):
            self.records.clear()
            self._persist()
            self.refresh_list()

    # ================= ЭКСПОРТ =================
    def export_csv(self):
        if not self.records:
            messagebox.showwarning("Внимание", "Нет записей")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV", "*.csv")],
                                             initialfile="qr_passports.csv")
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["fio", "kit", "date"])
            for r in self.records:
                w.writerow([r.get("fio", ""),
                            (r.get("kit", "") or "").replace("\n", ", "),
                            r.get("date", "")])
        messagebox.showinfo("Готово", f"Сохранено: {path}")

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"),
                                                      ("Все файлы", "*.*")])
        if not path:
            return
        try:
            from utils import read_codes_with_metadata
            rows = read_codes_with_metadata(path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{e}")
            return

        added = 0
        for code, meta in rows:
            fio = meta.get("fio") or meta.get("фио") or meta.get("name") or code
            kit = meta.get("kit") or meta.get("комплект") or ""
            date = meta.get("date") or meta.get("дата") or ""
            if fio:
                self.records.append({"fio": fio, "kit": kit, "date": date})
                added += 1

        self._persist()
        self.refresh_list()
        messagebox.showinfo("Готово", f"Добавлено записей: {added}")

    def export_pdf(self):
        if not self.records:
            messagebox.showwarning("Внимание", "Нет записей")
            return

        path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                             filetypes=[("PDF", "*.pdf")],
                                             initialfile="qr_passports.pdf")
        if not path:
            return

        # ===== Применяем QR-настройки к генератору =====
        try:
            qr_w = float(self.app.settings.get("qr_label_width", "58"))
            qr_h = float(self.app.settings.get("qr_label_height", "40"))
            qr_mt = float(self.app.settings.get("qr_margin_top", "5"))
            qr_mb = float(self.app.settings.get("qr_margin_bottom", "5"))
            qr_ml = float(self.app.settings.get("qr_margin_left", "5"))
            qr_mr = float(self.app.settings.get("qr_margin_right", "5"))
            qr_show_border = bool(self.app.settings.get("qr_show_border", False))
            qr_box_size = self.app.settings.get("qr_box_size", "8")
        except (ValueError, TypeError) as e:
            messagebox.showerror("Ошибка", f"Некорректные QR-настройки:\n{e}")
            return

        gen = self.app.generator
        prev_state = {
            "label_width": gen.label_width,
            "label_height": gen.label_height,
            "margins": list(gen.margins),
            "show_border": gen.show_border,
            "labels_per_page": gen.labels_per_page,
            "qr_box_size": gen.qr_box_size,
            "barcode_dpi": gen.barcode_dpi,
        }

        gen.label_width = qr_w
        gen.label_height = qr_h
        gen.margins = [qr_mt, qr_mb, qr_ml, qr_mr]
        gen.show_border = qr_show_border
        gen.labels_per_page = 1
        gen.qr_box_size = qr_box_size

        try:
            with tempfile.TemporaryDirectory() as tmp:
                barcode_images = []
                for i, rec in enumerate(self.records):
                    payload = build_qr_payload(rec, self.qr_format.get())
                    if not payload:
                        continue

                    buf = gen.generate_barcode_to_bytes(payload, force_qr=True)
                    if not buf:
                        logger.warning(f"QR не сгенерирован для {rec.get('fio')}")
                        continue
                    buf.seek(0)
                    img_path = os.path.join(tmp, f"qr_{i}.png")
                    with open(img_path, "wb") as f:
                        f.write(buf.read())
                    barcode_images.append((payload, img_path))

                if not barcode_images:
                    messagebox.showerror("Ошибка", "Не удалось сгенерировать QR")
                    return

                # Шаблон этикетки рассчитан на штрихкоды (свой размер, растянутая
                # картинка) — QR-паспорта печатаются по своим настройкам, без
                # искажения пропорций QR-кода.
                gen.create_pdf(path, barcode_images, use_template=False, keep_aspect=True)

            self.app.settings.add_history(path, len(barcode_images),
                                            "qr-passport",
                                            f"{qr_w}×{qr_h}")
            self.app.load_history()
            self.app.set_status(f"PDF создан: {os.path.basename(path)}", 'success')
            logger.info(f"QR-PDF создан: {path} ({len(barcode_images)} шт.)")

            if messagebox.askyesno("Готово", f"PDF создан!\n{path}\n\nОткрыть?"):
                open_pdf(path)
        except Exception as e:
            logger.error(f"Ошибка экспорта QR-PDF: {e}")
            messagebox.showerror("Ошибка", f"Не удалось создать PDF:\n{e}")
        finally:
            # Возвращаем настройки штрихкодов обратно
            try:
                gen.label_width = prev_state["label_width"]
                gen.label_height = prev_state["label_height"]
                gen.margins = prev_state["margins"]
                gen.show_border = prev_state["show_border"]
                gen.labels_per_page = prev_state["labels_per_page"]
                gen.qr_box_size = prev_state["qr_box_size"]
                gen.barcode_dpi = prev_state["barcode_dpi"]
            except Exception:
                pass
