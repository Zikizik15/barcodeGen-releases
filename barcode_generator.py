# barcode_generator.py - Логика генерации штрихкодов и QR-кодов

import barcode
from barcode.writer import ImageWriter
import os
import tempfile
import uuid
import io
from PIL import Image

from utils import (
    crop_barcode_aggressive,
    crop_barcode_aggressive_from_bytes,
    sanitize_filename,
    validate_code,
    get_barcode_params,
    find_font_path,
    GRID_MAP,
    DEFAULT_QR_BOX_SIZE,
)

from logger import logger

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

REPORTLAB_AVAILABLE = False
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    REPORTLAB_AVAILABLE = True
except ImportError:
    pass


class BarcodeGenerator:
    """Класс для генерации штрихкодов и PDF"""

    def __init__(self, settings_manager):
        self.settings = settings_manager
        self.barcode_type = None
        self.label_width = None
        self.label_height = None
        self.margins = None
        self.show_border = False
        self.labels_per_page = 1
        self.use_qr = False
        self.selected_only = False
        self.batch_mode = False
        self.barcode_dpi = "600"
        self.qr_box_size = DEFAULT_QR_BOX_SIZE
        self.status_callback = None
        self.progress_callback = None
        self.load_settings()

    def load_settings(self):
        s = self.settings
        self.barcode_type = s.get("barcode_type", "code128")
        self.label_width = float(s.get("barcode_label_width", s.get("label_width", "58")))
        self.label_height = float(s.get("barcode_label_height", s.get("label_height", "40")))
        self.margins = [
            float(s.get("barcode_margin_top", s.get("margin_top", "5"))),
            float(s.get("barcode_margin_bottom", s.get("margin_bottom", "5"))),
            float(s.get("barcode_margin_left", s.get("margin_left", "5"))),
            float(s.get("barcode_margin_right", s.get("margin_right", "5"))),
        ]
        self.show_border = s.get("barcode_show_border", s.get("show_border", False))
        self.labels_per_page = s.get("barcode_labels_per_page", s.get("labels_per_page", 1))
        self.selected_only = s.get("barcode_selected_only", s.get("selected_only", False))
        self.batch_mode = s.get("barcode_batch_mode", s.get("batch_mode", False))
        self.barcode_dpi = s.get("barcode_dpi", "600")
        self.qr_box_size = s.get("qr_box_size", DEFAULT_QR_BOX_SIZE)
        self.show_text = s.get("barcode_show_text", True)
        self.use_template = s.get("barcode_use_template", True)
        # use_qr зафиксирован в False: модуль штрихкодов больше не умеет QR.
        self.use_qr = False

    def set_status_callback(self, callback):
        self.status_callback = callback

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def update_status(self, text, status_type='info'):
        if self.status_callback:
            self.status_callback(text, status_type)

    def update_progress(self, current, total):
        if self.progress_callback:
            self.progress_callback(current, total)

    def template_active(self):
        """Будет ли PDF штрихкодов собираться по сохранённому шаблону."""
        template = self.settings.get("label_template")
        return bool(self.use_template and template and template.get("elements"))

    def writer_options(self):
        """Параметры отрисовки штрихкода. Их нужно передавать прямо в
        write()/save(): python-barcode при отрисовке заменяет параметры,
        заданные через writer.set_options(), своими значениями по умолчанию."""
        params = get_barcode_params(self.label_width, self.label_height, dpi=self.barcode_dpi)
        return {
            'module_width': params['module_width'],
            'module_height': params['module_height'],
            'quiet_zone': 0.0,
            # В шаблоне код печатается отдельным текстовым элементом {code}
            'write_text': bool(self.show_text) and not self.template_active(),
            'dpi': params['dpi'],
        }

    def get_writer(self):
        writer = ImageWriter()
        font_path = find_font_path()
        if font_path:
            writer.font_path = font_path
        writer.set_options(self.writer_options())
        return writer

    def generate_single_barcode(self, code, as_bytes=True, temp_dir=None, force_qr=False):
        try:
            code_str = str(code).strip()
            if not code_str:
                return None

            use_qr = force_qr or self.use_qr

            # Если это QR-код — пропускаем валидацию по типу 1D-штрихкода
            if not use_qr:
                valid, msg = validate_code(code_str, self.barcode_type)
                if not valid:
                    self.update_status(f"⚠️ {msg}: {code_str}", 'error')
                    return None

            if use_qr and QRCODE_AVAILABLE:
                bs = int(self.qr_box_size)
                qr = qrcode.QRCode(version=None, box_size=bs, border=2)
                qr.add_data(code_str)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                if as_bytes:
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG", dpi=(96 * bs, 96 * bs))
                    buffer.seek(0)
                    return crop_barcode_aggressive_from_bytes(buffer)
                else:
                    safe_name = sanitize_filename(code_str)
                    path = os.path.join(temp_dir or tempfile.mkdtemp(), f"qr_{safe_name}_{uuid.uuid4().hex[:6]}.png")
                    img.save(path, format="PNG", dpi=(96 * bs, 96 * bs))
                    return crop_barcode_aggressive(path)

            writer = self.get_writer()
            barcode_class = barcode.get_barcode_class(self.barcode_type)

            if as_bytes:
                buffer = io.BytesIO()
                barcode_class(code_str, writer=writer).write(buffer, options=self.writer_options())
                buffer.seek(0)
                return crop_barcode_aggressive_from_bytes(buffer)
            else:
                safe_name = sanitize_filename(code_str)
                base_path = os.path.join(temp_dir or tempfile.mkdtemp(), f"barcode_{safe_name}_{uuid.uuid4().hex[:6]}")
                saved_path = barcode_class(code_str, writer=writer).save(base_path, options=self.writer_options())
                if saved_path and os.path.exists(saved_path):
                    return crop_barcode_aggressive(saved_path)
                return None
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return None

    def generate_barcode_to_bytes(self, code, force_qr=False):
        return self.generate_single_barcode(code, as_bytes=True, force_qr=force_qr)

    def generate_barcode_image(self, code, temp_dir, force_qr=False):
        return self.generate_single_barcode(code, as_bytes=False, temp_dir=temp_dir, force_qr=force_qr)

    def create_pdf(self, filename, barcode_images, metadata=None, use_template=None,
                   keep_aspect=False):
        """metadata — {код: {name, price, ...}} для плейсхолдеров шаблона.
        use_template=None — по настройке «Использовать сохранённый шаблон».
        keep_aspect — не растягивать картинку (нужно для QR-кодов)."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab не установлен")
        if use_template is None:
            use_template = self.template_active()
        if use_template:
            self._create_pdf_from_template(filename, barcode_images,
                                           self.settings.get("label_template"), metadata)
        else:
            self._create_pdf_default(filename, barcode_images, keep_aspect)

    def _create_pdf_default(self, filename, barcode_images, keep_aspect=False):
        scale = 2.83465
        page_w, page_h = self.label_width * scale, self.label_height * scale
        mt, mb, ml, mr = [m * scale for m in self.margins]
        labels_per_page = self.labels_per_page
        cols, rows = GRID_MAP.get(labels_per_page, (1, 1))
        c = canvas.Canvas(filename, pagesize=(page_w, page_h))
        for i, (code, img_path) in enumerate(barcode_images):
            if labels_per_page > 1:
                pos_in_page = i % labels_per_page
                if pos_in_page == 0 and i != 0:
                    c.showPage()
                col, row = pos_in_page % cols, pos_in_page // cols
                cell_w, cell_h = (page_w - ml - mr) / cols, (page_h - mt - mb) / rows
                x = ml + col * cell_w
                y = page_h - mt - (row + 1) * cell_h
                w, h = cell_w, cell_h
            else:
                if i > 0:
                    c.showPage()
                x, y = ml, mb
                w, h = page_w - ml - mr, page_h - mt - mb

            if self.show_border:
                c.rect(x, y, w, h, stroke=1, fill=0)
            try:
                img = ImageReader(img_path)
                img_w, img_h = w * 0.98, h * 0.95
                img_x = x + (w - img_w) / 2
                img_y = y + (h - img_h) / 2
                c.drawImage(img, img_x, img_y, width=img_w, height=img_h,
                            preserveAspectRatio=keep_aspect, anchor='c')
            except Exception as e:
                logger.error(f"Ошибка вставки: {e}")
        c.save()

    def _create_pdf_from_template(self, filename, barcode_images, template, metadata=None):
        scale = 2.83465
        label_w = template.get("label_width", self.label_width)
        label_h = template.get("label_height", self.label_height)
        page_w, page_h = label_w * scale, label_h * scale
        elements = template.get("elements", [])

        font_name = "Helvetica"
        font_path = find_font_path()
        if font_path:
            try:
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                pdfmetrics.registerFont(TTFont("CustomFont", font_path))
                font_name = "CustomFont"
            except Exception:
                pass

        c = canvas.Canvas(filename, pagesize=(page_w, page_h))
        meta_all = metadata if metadata is not None else (self.settings.get("codes_metadata", {}) or {})

        for i, (code, img_path) in enumerate(barcode_images):
            if i > 0:
                c.showPage()
            for el in elements:
                x = el["x"] * scale
                y_top = el["y"] * scale
                w = el["w"] * scale
                h = el["h"] * scale
                y = page_h - y_top - h

                if el["type"] == "barcode":
                    try:
                        img = ImageReader(img_path)
                        if self.use_qr:
                            c.drawImage(img, x, y, width=w, height=h,
                                        preserveAspectRatio=True, anchor='c')
                        else:
                            c.drawImage(img, x, y, width=w, height=h)
                    except Exception as e:
                        logger.error(f"Ошибка вставки штрихкода: {e}")
                elif el["type"] == "image":
                    src = el.get("src", "")
                    if src and os.path.exists(src):
                        try:
                            img_el = ImageReader(src)
                            c.drawImage(img_el, x, y, width=w, height=h,
                                        preserveAspectRatio=True, anchor='c', mask='auto')
                        except Exception as e:
                            logger.error(f"Ошибка вставки картинки: {e}")
                elif el["type"] == "text":
                    text = str(el.get("text", "")).replace("{code}", code)
                    meta = meta_all.get(code, {})
                    for key, value in meta.items():
                        text = text.replace("{" + key + "}", str(value))
                    font_size = el.get("font_size", 10)
                    try:
                        c.setFont(font_name, font_size)
                        c.drawCentredString(x + w / 2, y + h / 2 - font_size * 0.35, text)
                    except Exception:
                        pass
        c.save()

    def generate_zip_archive(self, codes, filename):
        import zipfile
        self.update_status("⏳ Генерация изображений...", 'warning')
        with tempfile.TemporaryDirectory() as temp_dir:
            image_files = []
            total = len(codes)
            for i, code in enumerate(codes):
                if self.progress_callback:
                    self.update_progress(i + 1, total)
                valid, _ = validate_code(code, self.barcode_type)
                if not valid:
                    continue
                img_path = self.generate_barcode_image(code, temp_dir)
                if img_path:
                    image_files.append((code, img_path))
            if not image_files:
                raise Exception("Не удалось сгенерировать изображения")
            self.write_zip(filename, image_files)
        return len(image_files)

    @staticmethod
    def write_zip(filename, image_files):
        """Складывает готовые картинки [(код, путь), ...] в ZIP-архив."""
        import zipfile
        used = set()
        with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for code, img_path in image_files:
                name = sanitize_filename(code)
                # Разные коды могут дать одинаковое имя файла — не перезаписываем
                unique, n = name, 2
                while unique in used:
                    unique, n = f"{name}_{n}", n + 1
                used.add(unique)
                zipf.write(img_path, f"{unique}.png")