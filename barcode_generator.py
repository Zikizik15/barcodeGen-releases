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
    make_qr_image,
    GRID_MAP,
    DEFAULT_QR_BOX_SIZE,
)

from logger import logger

try:
    import qrcode  # noqa: F401 — только проверка, что библиотека установлена
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

MM = 2.83465  # пунктов PDF в одном миллиметре

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
        self.qr_logo = None  # PIL-картинка логотипа для центра QR (задаёт вкладка QR)
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
                img = make_qr_image(code_str, bs, logo=self.qr_logo)

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

    # ========== РАСКЛАДКА СТРАНИЦ ==========
    # Одна раскладка на всё: по ней рисуется и PDF (draw_pdf), и картинка
    # предпросмотра (render_page_image) — поэтому они не расходятся.
    # Координаты в миллиметрах от левого верхнего угла страницы.
    # Операции: ("image", путь, x, y, w, h, сохранять_пропорции)
    #           ("text", текст, центр_x, центр_y, кегль_pt)
    #           ("rect", x, y, w, h)

    def layout_pages(self, barcode_images, metadata=None, use_template=None, keep_aspect=False):
        """Возвращает (ширина_мм, высота_мм, [страница = [операции]])."""
        if use_template is None:
            use_template = self.template_active()
        try:
            per_page = int(self.labels_per_page)
        except (TypeError, ValueError):
            per_page = 1
        if per_page not in GRID_MAP:
            per_page = 1
        cols, rows = GRID_MAP[per_page]
        template = self.settings.get("label_template") if use_template else None
        meta_all = metadata if metadata is not None else (self.settings.get("codes_metadata", {}) or {})

        if template and per_page == 1:
            # Одна этикетка по шаблону: страница = размер шаблона, поля задаёт сам шаблон
            page_w = float(template.get("label_width", self.label_width))
            page_h = float(template.get("label_height", self.label_height))
            cells = [(0.0, 0.0, page_w, page_h)]
        else:
            page_w, page_h = self.label_width, self.label_height
            mt, mb, ml, mr = self.margins
            cell_w = (page_w - ml - mr) / cols
            cell_h = (page_h - mt - mb) / rows
            cells = [(ml + (i % cols) * cell_w, mt + (i // cols) * cell_h, cell_w, cell_h)
                     for i in range(per_page)]

        pages = []
        for i, (code, img_path) in enumerate(barcode_images):
            if i % per_page == 0:
                pages.append([])
            ops = pages[-1]
            x, y, w, h = cells[i % per_page]
            if self.show_border:
                ops.append(("rect", x, y, w, h))
            if template:
                ops.extend(self._template_ops(template, code, img_path, (x, y, w, h),
                                              meta_all.get(code, {}), keep_aspect))
            else:
                img_w, img_h = w * 0.98, h * 0.95
                ops.append(("image", img_path, x + (w - img_w) / 2, y + (h - img_h) / 2,
                            img_w, img_h, keep_aspect))
        return page_w, page_h, pages

    @staticmethod
    def _template_ops(template, code, img_path, cell, meta, keep_aspect):
        """Элементы шаблона, вписанные в ячейку с сохранением пропорций шаблона."""
        cx, cy, cw, ch = cell
        tw = float(template.get("label_width", cw)) or cw
        th = float(template.get("label_height", ch)) or ch
        k = min(cw / tw, ch / th)
        ox, oy = cx + (cw - tw * k) / 2, cy + (ch - th * k) / 2
        ops = []
        for el in template.get("elements", []):
            x, y = ox + el["x"] * k, oy + el["y"] * k
            w, h = el["w"] * k, el["h"] * k
            if el["type"] == "barcode":
                ops.append(("image", img_path, x, y, w, h, keep_aspect))
            elif el["type"] == "image":
                src = el.get("src", "")
                if src and os.path.exists(src):
                    ops.append(("image", src, x, y, w, h, True))
            elif el["type"] == "text":
                text = str(el.get("text", "")).replace("{code}", code)
                for key, value in meta.items():
                    text = text.replace("{" + key + "}", str(value))
                ops.append(("text", text, x + w / 2, y + h / 2, el.get("font_size", 10) * k))
        return ops

    def create_pdf(self, filename, barcode_images, metadata=None, use_template=None,
                   keep_aspect=False):
        """metadata — {код: {name, price, ...}} для плейсхолдеров шаблона.
        use_template=None — по настройке «Использовать сохранённый шаблон».
        keep_aspect — не растягивать картинку (нужно для QR-кодов)."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab не установлен")
        page_w, page_h, pages = self.layout_pages(barcode_images, metadata, use_template, keep_aspect)
        self.draw_pdf(filename, page_w, page_h, pages)

    @staticmethod
    def _pdf_font():
        """Шрифт с кириллицей для текста шаблона (Helvetica её не умеет)."""
        font_path = find_font_path()
        if font_path:
            try:
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                if "CustomFont" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("CustomFont", font_path))
                return "CustomFont"
            except Exception:
                pass
        return "Helvetica"

    def draw_pdf(self, filename, page_w, page_h, pages):
        c = canvas.Canvas(filename, pagesize=(page_w * MM, page_h * MM))
        font_name = self._pdf_font()
        images = {}
        for n, ops in enumerate(pages):
            if n:
                c.showPage()
            for op in ops:
                try:
                    if op[0] == "image":
                        _, path, x, y, w, h, keep = op
                        if path not in images:
                            images[path] = ImageReader(path)
                        c.drawImage(images[path], x * MM, (page_h - y - h) * MM, width=w * MM,
                                    height=h * MM, preserveAspectRatio=keep, anchor='c', mask='auto')
                    elif op[0] == "text":
                        _, text, cx, cy, size = op
                        c.setFont(font_name, size)
                        c.drawCentredString(cx * MM, (page_h - cy) * MM - size * 0.35, text)
                    elif op[0] == "rect":
                        _, x, y, w, h = op
                        c.rect(x * MM, (page_h - y - h) * MM, w * MM, h * MM, stroke=1, fill=0)
                except Exception as e:
                    logger.error(f"Ошибка отрисовки элемента {op[0]}: {e}")
        c.save()

    @staticmethod
    def render_page_image(page_w, page_h, ops, px_per_mm=8.0):
        """Та же страница, что в PDF, но картинкой — для предпросмотра."""
        from PIL import ImageDraw, ImageFont
        k = px_per_mm
        page = Image.new("RGB", (max(1, round(page_w * k)), max(1, round(page_h * k))), "white")
        draw = ImageDraw.Draw(page)
        font_path = find_font_path()
        for op in ops:
            try:
                if op[0] == "image":
                    _, path, x, y, w, h, keep = op
                    src = Image.open(path).convert("RGBA")
                    bw, bh = max(1, round(w * k)), max(1, round(h * k))
                    if keep:
                        s = min(bw / src.width, bh / src.height)
                        fit = src.resize((max(1, round(src.width * s)), max(1, round(src.height * s))),
                                         Image.LANCZOS)
                        px, py = round(x * k + (bw - fit.width) / 2), round(y * k + (bh - fit.height) / 2)
                    else:
                        fit = src.resize((bw, bh), Image.LANCZOS)
                        px, py = round(x * k), round(y * k)
                    page.paste(fit, (px, py), fit)
                elif op[0] == "text":
                    _, text, cx, cy, size = op
                    size_px = max(4, round(size / MM * k))
                    try:
                        fnt = ImageFont.truetype(font_path, size_px) if font_path else ImageFont.load_default()
                    except Exception:
                        fnt = ImageFont.load_default()
                    baseline = (cy + size * 0.35 / MM) * k
                    draw.text((cx * k, baseline), text, fill="black", font=fnt, anchor="ms")
                elif op[0] == "rect":
                    _, x, y, w, h = op
                    draw.rectangle([x * k, y * k, (x + w) * k, (y + h) * k], outline="black",
                                   width=max(1, round(k * 0.35)))
            except Exception as e:
                logger.error(f"Предпросмотр: ошибка отрисовки {op[0]}: {e}")
        return page

    def generate_zip_archive(self, codes, filename):
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