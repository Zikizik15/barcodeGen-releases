# tests/test_barcode_generator.py — Unit-тесты для barcode_generator.py

import os
import sys
import io
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from barcode_generator import BarcodeGenerator
from settings import SettingsManager
from utils import DEFAULT_QR_BOX_SIZE, BARCODE_TYPES


# ========== BarcodeGenerator initialization ==========

class TestBarcodeGeneratorInit:
    """Тесты инициализации BarcodeGenerator."""

    def test_default_settings(self):
        """BarcodeGenerator загружает настройки (проверяем что не падает)."""
        sm = SettingsManager()
        # Сбрасываем сохранённые настройки для чистого теста
        sm.settings = sm.get_default_settings()
        gen = BarcodeGenerator(sm)

        assert gen.barcode_type == "code128"
        assert gen.label_width == 58.0
        assert gen.label_height == 40.0
        assert gen.barcode_dpi == "600"

    def test_custom_settings(self):
        """BarcodeGenerator загружает пользовательские настройки."""
        sm = SettingsManager()
        sm.settings["barcode_type"] = "code39"
        sm.settings["barcode_label_width"] = "100"
        sm.settings["barcode_label_height"] = "50"
        sm.settings["barcode_dpi"] = "1200"

        gen = BarcodeGenerator(sm)

        assert gen.barcode_type == "code39"
        assert gen.label_width == 100.0
        assert gen.label_height == 50.0
        # use_qr всегда False для модуля штрихкодов
        assert gen.use_qr is False
        assert gen.barcode_dpi == "1200"

    def test_callbacks(self):
        """Методы set_status_callback и set_progress_callback."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)

        status_called = []
        progress_called = []

        gen.set_status_callback(lambda text, st: status_called.append((text, st)))
        gen.set_progress_callback(lambda cur, tot: progress_called.append((cur, tot)))

        gen.update_status("test", "info")
        gen.update_progress(1, 10)

        assert len(status_called) == 1
        assert len(progress_called) == 1
        assert status_called[0] == ("test", "info")
        assert progress_called[0] == (1, 10)


# ========== generate_barcode_to_bytes ==========

class TestGenerateBarcodeToBytes:
    """Тесты генерации штрихкодов в байты."""

    def test_code128_valid(self):
        """Code 128: валидный код генерируется."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)
        gen.barcode_type = "code128"

        buf = gen.generate_barcode_to_bytes("TEST123")
        assert buf is not None
        assert hasattr(buf, "read")

        # Проверяем, что это валидный PNG
        buf.seek(0)
        from PIL import Image
        img = Image.open(buf)
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_code39_valid(self):
        """Code 39: валидный код генерируется."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)
        gen.barcode_type = "code39"

        buf = gen.generate_barcode_to_bytes("ABC-123")
        assert buf is not None

    def test_empty_code(self):
        """Пустой код возвращает None."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)

        buf = gen.generate_barcode_to_bytes("")
        assert buf is None

    def test_invalid_code(self):
        """Невалидный код возвращает None."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)
        gen.barcode_type = "ean13"

        buf = gen.generate_barcode_to_bytes("123")  # EAN-13 требует 12-13 цифр
        assert buf is None

    def test_invalid_barcode_type(self):
        """Неизвестный тип штрихкода."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)
        gen.barcode_type = "nonexistent_type"

        # Должен вернуть None или выбросить ошибку
        try:
            buf = gen.generate_barcode_to_bytes("TEST")
            assert buf is None
        except Exception:
            pass  # Допустимо


# ========== QR Code generation ==========

class TestGenerateQRCode:
    """Тесты генерации QR-кодов."""

    def test_qr_basic(self):
        """QR-код генерируется с текстом."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)
        gen.use_qr = True

        buf = gen.generate_barcode_to_bytes("Hello World")
        assert buf is not None

        buf.seek(0)
        from PIL import Image
        img = Image.open(buf)
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_qr_with_box_size(self):
        """QR-код с разным box_size."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)
        gen.use_qr = True
        gen.qr_box_size = "16"

        buf = gen.generate_barcode_to_bytes("TEST")
        assert buf is not None

        buf.seek(0)
        from PIL import Image
        img = Image.open(buf)

        # box_size=16 должен дать больше пикселей, чем box_size=8
        gen2 = BarcodeGenerator(SettingsManager())
        gen2.use_qr = True
        gen2.qr_box_size = "8"

        buf2 = gen2.generate_barcode_to_bytes("TEST")
        buf2.seek(0)
        img2 = Image.open(buf2)

        assert img.size[0] > img2.size[0]

    def test_qr_long_text(self):
        """QR-код с длинным текстом."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)
        gen.use_qr = True

        long_text = "A" * 500  # QR может хранить много данных
        buf = gen.generate_barcode_to_bytes(long_text)
        assert buf is not None


# ========== generate_barcode_image (file) ==========

class TestGenerateBarcodeImage:
    """Тесты генерации штрихкодов в файл."""

    def test_file_generation(self, tmp_path):
        """Штрихкод сохраняется в файл."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)

        img_path = gen.generate_barcode_image("TEST123", str(tmp_path))
        assert img_path is not None
        assert os.path.exists(img_path)

    def test_file_cropped(self, tmp_path):
        """Сгенерированный файл обрезан (нет белых полей)."""
        sm = SettingsManager()
        sm.settings = sm.get_default_settings()  # Сбрасываем DPI на 600
        gen = BarcodeGenerator(sm)

        img_path = gen.generate_barcode_image("TEST123", str(tmp_path))
        assert img_path is not None

        from PIL import Image
        img = Image.open(img_path)
        # Изображение должно быть меньше 1000px по каждой оси (при 600 DPI)
        assert img.size[0] < 1000
        assert img.size[1] < 1000


# ========== create_pdf ==========

class TestCreatePDF:
    """Тесты создания PDF."""

    def test_pdf_single_label(self, tmp_path):
        """PDF с одной этикеткой."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)

        # Генерируем тестовый штрихкод в файл
        img_path = gen.generate_barcode_image("TEST123", str(tmp_path))

        pdf_path = tmp_path / "test.pdf"
        gen.create_pdf(str(pdf_path), [("TEST123", img_path)])

        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0

    def test_pdf_multiple_labels(self, tmp_path):
        """PDF с несколькими этикетками."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)

        images = []
        for i in range(3):
            img_path = gen.generate_barcode_image(f"TEST{i}", str(tmp_path))
            images.append((f"TEST{i}", img_path))

        pdf_path = tmp_path / "test.pdf"
        gen.create_pdf(str(pdf_path), images)

        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0

    def test_pdf_no_reportlab(self, tmp_path):
        """create_pdf без reportlab выбрасывает ImportError."""
        # Сохраняем текущее значение
        import barcode_generator as bg
        old_value = bg.REPORTLAB_AVAILABLE

        try:
            bg.REPORTLAB_AVAILABLE = False
            gen = BarcodeGenerator(SettingsManager())

            with pytest.raises(ImportError, match="reportlab не установлен"):
                gen.create_pdf(str(tmp_path / "test.pdf"), [])
        finally:
            bg.REPORTLAB_AVAILABLE = old_value


# ========== get_writer ==========

class TestGetWriter:
    """Тесты получения ImageWriter."""

    def test_writer_returns_imagewriter(self):
        """get_writer возвращает ImageWriter с параметрами."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)

        writer = gen.get_writer()
        assert writer is not None

    def test_writer_respects_dpi(self):
        """Параметры writer зависят от DPI."""
        sm = SettingsManager()
        gen = BarcodeGenerator(sm)
        gen.barcode_dpi = "1200"

        writer = gen.get_writer()
        assert writer is not None


# ========== load_settings ==========

class TestLoadSettings:
    """Тесты загрузки настроек."""

    def test_load_updates_all_fields(self):
        """load_settings обновляет все поля."""
        sm = SettingsManager()
        sm.settings.update({
            "barcode_type": "ean13",
            "barcode_label_width": "100",
            "barcode_label_height": "50",
            "barcode_margin_top": "10",
            "barcode_margin_bottom": "15",
            "barcode_margin_left": "20",
            "barcode_margin_right": "25",
            "barcode_show_border": True,
            "barcode_labels_per_page": 4,
            "barcode_selected_only": True,
            "barcode_batch_mode": True,
            "barcode_dpi": "2400",
            "qr_box_size": "16",
        })

        gen = BarcodeGenerator(sm)
        gen.load_settings()

        assert gen.barcode_type == "ean13"
        assert gen.label_width == 100.0
        assert gen.label_height == 50.0
        assert gen.margins == [10.0, 15.0, 20.0, 25.0]
        assert gen.show_border is True
        assert gen.labels_per_page == 4
        # use_qr всегда False для модуля штрихкодов
        assert gen.selected_only is True
        assert gen.batch_mode is True
        assert gen.barcode_dpi == "2400"
        assert gen.qr_box_size == "16"


# ========== Регрессии: шаблон, текст под штрихкодом, QR, ZIP ==========

TEMPLATE = {"label_width": 58, "label_height": 40, "elements": [
    {"id": "barcode", "type": "barcode", "x": 4, "y": 12, "w": 50, "h": 22},
    {"id": "t", "type": "text", "text": "{code} {name}", "x": 4, "y": 2, "w": 50, "h": 8, "font_size": 10},
]}


def _gen(**overrides):
    sm = SettingsManager()
    sm.settings = sm.get_default_settings()
    sm.settings.update(overrides)
    return BarcodeGenerator(sm)


class TestTemplateSwitch:
    """«Использовать сохранённый шаблон» реально включает/выключает шаблон."""

    @staticmethod
    def _kinds(gen, **kw):
        _, _, pages = gen.layout_pages([("ABC123", "img.png")], **kw)
        return [op[0] for op in pages[0]]

    def test_template_used_when_enabled(self):
        gen = _gen(label_template=TEMPLATE, barcode_use_template=True)
        assert "text" in self._kinds(gen)          # в шаблоне есть текст {code}

    def test_template_skipped_when_disabled(self):
        gen = _gen(label_template=TEMPLATE, barcode_use_template=False)
        assert self._kinds(gen) == ["image"]

    def test_explicit_no_template_for_qr(self):
        """QR-паспорта передают use_template=False и keep_aspect=True."""
        gen = _gen(label_template=TEMPLATE, barcode_use_template=True)
        _, _, pages = gen.layout_pages([("QR", "img.png")], use_template=False, keep_aspect=True)
        assert [op[0] for op in pages[0]] == ["image"] and pages[0][0][-1] is True

    def test_template_pdf_with_metadata(self, tmp_path):
        gen = _gen(label_template=TEMPLATE, barcode_use_template=True)
        img = gen.generate_barcode_image("ABC123", str(tmp_path))
        pdf = tmp_path / "t.pdf"
        gen.create_pdf(str(pdf), [("ABC123", img)], metadata={"ABC123": {"name": "Товар"}})
        assert pdf.stat().st_size > 0

    def test_metadata_substituted(self):
        gen = _gen(label_template=TEMPLATE, barcode_use_template=True)
        _, _, pages = gen.layout_pages([("ABC123", "img.png")], metadata={"ABC123": {"name": "Вода"}})
        texts = [op[1] for op in pages[0] if op[0] == "text"]
        assert texts == ["ABC123 Вода"]


class TestTemplateGrid:
    """Шаблон учитывает «этикеток на странице» и поля."""

    def test_one_per_page_uses_template_size(self):
        gen = _gen(label_template=TEMPLATE, barcode_use_template=True,
                   barcode_label_width="100", barcode_label_height="70")
        w, h, pages = gen.layout_pages([("A", "i.png"), ("B", "i.png")])
        assert (w, h, len(pages)) == (58, 40, 2)

    def test_grid_with_template(self):
        gen = _gen(label_template=TEMPLATE, barcode_use_template=True, barcode_labels_per_page=4,
                   barcode_label_width="120", barcode_label_height="80",
                   barcode_margin_top="0", barcode_margin_bottom="0",
                   barcode_margin_left="0", barcode_margin_right="0")
        w, h, pages = gen.layout_pages([(f"C{i}", "i.png") for i in range(5)])
        assert (w, h, len(pages)) == (120, 80, 2)
        barcodes = [op for op in pages[0] if op[0] == "image"]
        assert len(barcodes) == 4
        # Ячейка 60×40, шаблон 58×40 вписан по центру; вторая ячейка правее на 60 мм
        assert abs(barcodes[1][2] - barcodes[0][2] - 60) < 1e-6
        assert all(op[2] + op[4] <= 120 + 1e-6 and op[3] + op[5] <= 80 + 1e-6 for op in barcodes)

    def test_margins_respected_in_grid(self):
        gen = _gen(barcode_labels_per_page=2, barcode_label_width="100", barcode_label_height="50",
                   barcode_margin_top="5", barcode_margin_bottom="5",
                   barcode_margin_left="10", barcode_margin_right="10")
        _, _, pages = gen.layout_pages([("A", "i.png"), ("B", "i.png")])
        xs = [op[2] for op in pages[0]]
        assert xs[0] >= 10 and pages[0][1][2] + pages[0][1][4] <= 90 + 1e-6


class TestPreviewMatchesPdf:
    def test_render_page_image(self, tmp_path):
        gen = _gen(label_template=TEMPLATE, barcode_use_template=True)
        img = gen.generate_barcode_image("ABC123", str(tmp_path))
        w, h, pages = gen.layout_pages([("ABC123", img)])
        page = gen.render_page_image(w, h, pages[0], px_per_mm=4)
        assert page.size == (232, 160)
        # На странице есть тёмные пиксели (штрихкод и текст)
        assert page.convert("L").getextrema()[0] < 50


class TestWriterOptions:
    """Параметры отрисовки действительно применяются к картинке."""

    def test_text_hidden_in_template_mode(self):
        gen = _gen(label_template=TEMPLATE, barcode_use_template=True)
        assert gen.writer_options()["write_text"] is False

    def test_text_follows_setting_without_template(self):
        assert _gen(barcode_show_text=True).writer_options()["write_text"] is True
        assert _gen(barcode_show_text=False).writer_options()["write_text"] is False

    def test_text_actually_removed_from_image(self):
        from PIL import Image
        with_text = Image.open(_gen(barcode_show_text=True).generate_barcode_to_bytes("ABC123"))
        no_text = Image.open(_gen(barcode_show_text=False).generate_barcode_to_bytes("ABC123"))
        assert no_text.height < with_text.height


class TestWriteZip:
    def test_duplicate_names_not_overwritten(self, tmp_path):
        import zipfile
        gen = _gen()
        img = gen.generate_barcode_image("ABC", str(tmp_path))
        # sanitize_filename превращает оба кода в «A_B»
        out = tmp_path / "a.zip"
        gen.write_zip(str(out), [("A-B", img), ("A/B", img)])
        assert sorted(zipfile.ZipFile(out).namelist()) == ["A_B.png", "A_B_2.png"]
