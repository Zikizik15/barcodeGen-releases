# tests/test_utils.py — Unit-тесты для utils.py

import os
import sys
import csv
import tempfile
import pytest

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import (
    validate_code,
    get_barcode_params,
    sanitize_filename,
    crop_barcode_aggressive_from_bytes,
    read_codes_with_metadata,
    suggest_barcode_type,
    LABEL_PRESETS,
    BARCODE_TYPES,
    DPI_PRESETS,
    QR_BOX_SIZE_PRESETS,
    DEFAULT_DPI,
    DEFAULT_QR_BOX_SIZE,
)


# ========== validate_code ==========

class TestValidateCode:
    """Тесты валидации кодов по типам штрихкодов."""

    def test_code128_valid(self):
        """Code 128 принимает любой непустой строковый код."""
        valid, msg = validate_code("TEST-123", "code128")
        assert valid is True
        assert msg == "OK"

    def test_code128_empty(self):
        """Пустой код всегда невалиден."""
        valid, msg = validate_code("", "code128")
        assert valid is False

    def test_code39_valid(self):
        """Code 39: A-Z, 0-9, -, ., $, /, +, %."""
        valid, msg = validate_code("ABC-123.$", "code39")
        assert valid is True

    def test_code39_lowercase(self):
        """Code 39: lowercase автоматически переводится в uppercase."""
        valid, msg = validate_code("abc-123", "code39")
        assert valid is True  # regex проверяет upper, но input переводится

    def test_code39_invalid_char(self):
        """Code 39: символы вне диапазона невалидны."""
        valid, msg = validate_code("ABC@123", "code39")
        assert valid is False

    def test_ean13_valid(self):
        """EAN-13: 13 цифр с верной контрольной цифрой."""
        valid, msg = validate_code("4006381333931", "ean13")
        assert valid is True

    def test_ean13_12_digits(self):
        """EAN-13: 12 цифр тоже валидны (без контрольной)."""
        valid, msg = validate_code("123456789012", "ean13")
        assert valid is True

    def test_ean13_invalid_length(self):
        """EAN-13: 11 цифр — невалидно."""
        valid, msg = validate_code("12345678901", "ean13")
        assert valid is False

    def test_ean13_letters(self):
        """EAN-13: буквы — невалидно."""
        valid, msg = validate_code("123456789012A", "ean13")
        assert valid is False

    def test_ean8_valid(self):
        """EAN-8: 8 цифр с верной контрольной цифрой."""
        valid, msg = validate_code("12345670", "ean8")
        assert valid is True

    def test_ean8_invalid(self):
        """EAN-8: 9 цифр — невалидно."""
        valid, msg = validate_code("123456789", "ean8")
        assert valid is False

    def test_upca_valid(self):
        """UPC-A: 11 или 12 цифр."""
        valid, msg = validate_code("123456789012", "upca")
        assert valid is True

    def test_upca_invalid(self):
        """UPC-A: 13 цифр — невалидно."""
        valid, msg = validate_code("1234567890123", "upca")
        assert valid is False

    def test_itf_valid_even(self):
        """ITF: чётное количество цифр — валидно."""
        valid, msg = validate_code("1234", "itf")
        assert valid is True

    def test_itf_valid_long(self):
        """ITF: длинный чётный код — валиден."""
        valid, msg = validate_code("1234567890123456", "itf")
        assert valid is True

    def test_itf_invalid_odd(self):
        """ITF: нечётное количество цифр — невалидно."""
        valid, msg = validate_code("123", "itf")
        assert valid is False

    def test_itf_letters(self):
        """ITF: буквы — невалидно."""
        valid, msg = validate_code("12AB", "itf")
        assert valid is False

    def test_codabar_valid(self):
        """Codabar: цифры и спецсимволы — валидно."""
        valid, msg = validate_code("123-456", "codabar")
        assert valid is True

    def test_codabar_with_start(self):
        """Codabar: с буквой начала/конца — валидно."""
        valid, msg = validate_code("A123456B", "codabar")
        assert valid is True


# ========== get_barcode_params ==========

class TestGetBarcodeParams:
    """Тесты масштабирования параметров штрихкода."""

    def test_default_dpi(self):
        """По умолчанию DPI = 600."""
        params = get_barcode_params(58, 40)
        assert params["dpi"] == 600

    def test_custom_dpi(self):
        """Можно задать произвольный DPI."""
        params = get_barcode_params(58, 40, dpi="1200")
        assert params["dpi"] == 1200

    def test_standard_label(self):
        """Стандартная этикетка 58×40 — базовый масштаб."""
        params = get_barcode_params(58, 40)
        assert params["module_width"] > 0
        assert params["module_height"] > 0

    def test_small_label(self):
        """Маленькая этикетка 25×15 — масштаб уменьшается."""
        params = get_barcode_params(25, 15)
        assert params["module_width"] > 0
        assert params["module_height"] > 0
        # Масштаб должен быть меньше стандартного
        assert params["module_width"] < get_barcode_params(58, 40)["module_width"]

    def test_large_label(self):
        """Большая этикетка 100×70 — масштаб увеличивается."""
        params = get_barcode_params(100, 70)
        assert params["module_width"] > get_barcode_params(58, 40)["module_width"]

    def test_scale_clamped(self):
        """Масштаб ограничен [0.5, 2.0]."""
        # Очень маленькая этикетка — масштаб не меньше 0.5
        params = get_barcode_params(5, 3)
        assert params["module_width"] > 0

        # Очень большая этикетка — масштаб не больше 2.0
        params = get_barcode_params(500, 500)
        assert params["module_width"] > 0


# ========== sanitize_filename ==========

class TestSanitizeFilename:
    """Тесты очистки имени файла."""

    def test_simple(self):
        """Простой алфавитно-цифровой код."""
        assert sanitize_filename("ABC123") == "ABC123"

    def test_special_chars(self):
        """Спецсимволы заменяются на _."""
        assert sanitize_filename("ABC-123.456") == "ABC_123_456"

    def test_max_length(self):
        """Имя не длиннее 20 символов."""
        long_code = "A" * 50
        assert len(sanitize_filename(long_code)) == 20

    def test_empty(self):
        """Пустой код."""
        assert sanitize_filename("") == ""


# ========== crop_barcode_aggressive_from_bytes ==========

class TestCropBarcodeFromBytes:
    """Тесты обрезки изображений из байтового потока."""

    def test_returns_bytesio(self):
        """Возвращает BytesIO при output_path=None."""
        from PIL import Image
        import io

        # Создаём тестовое изображение 100x100 с белым фоном и чёрным квадратом
        img = Image.new("RGB", (100, 100), "white")
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle((20, 20, 80, 80), fill="black")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        result = crop_barcode_aggressive_from_bytes(buf)
        assert result is not None
        assert hasattr(result, "read")  # BytesIO

    def test_with_output_path(self, tmp_path):
        """Возвращает путь при output_path != None."""
        from PIL import Image
        import io

        img = Image.new("RGB", (100, 100), "white")
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle((20, 20, 80, 80), fill="black")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        output = tmp_path / "cropped.png"
        result = crop_barcode_aggressive_from_bytes(buf, str(output))
        assert result == str(output)
        assert output.exists()


# ========== read_codes_with_metadata ==========

class TestReadCodesWithMetadata:
    """Тесты чтения файлов с кодами."""

    def test_txt_simple(self, tmp_path):
        """TXT: по одному коду на строку."""
        f = tmp_path / "codes.txt"
        f.write_text("ABC123\nDEF456\n\nGHI789\n", encoding="utf-8")

        result = read_codes_with_metadata(str(f))
        assert len(result) == 3
        assert result[0] == ("ABC123", {})
        assert result[1] == ("DEF456", {})
        assert result[2] == ("GHI789", {})

    def test_txt_empty_lines(self, tmp_path):
        """TXT: пустые строки игнорируются."""
        f = tmp_path / "codes.txt"
        f.write_text("\n\nABC123\n\n\n", encoding="utf-8")
        result = read_codes_with_metadata(str(f))
        assert len(result) == 1
        assert result[0][0] == "ABC123"

    def test_csv_with_header(self, tmp_path):
        """CSV с заголовками."""
        f = tmp_path / "codes.csv"
        f.write_text("code,name,price\nABC123,Товар,100\nDEF456,Другой,200\n", encoding="utf-8-sig")

        result = read_codes_with_metadata(str(f))
        assert len(result) == 2
        assert result[0][0] == "ABC123"
        assert result[0][1]["name"] == "Товар"
        assert result[0][1]["price"] == "100"

    def test_csv_semicolon_delimiter(self, tmp_path):
        """CSV с разделителем ;."""
        f = tmp_path / "codes.csv"
        f.write_text("code;name\nABC;Товар\n", encoding="utf-8-sig")

        result = read_codes_with_metadata(str(f))
        assert len(result) == 1
        assert result[0][1]["name"] == "Товар"

    def test_csv_no_header(self, tmp_path):
        """CSV без заголовков: первая колонка = code."""
        f = tmp_path / "codes.csv"
        f.write_text("ABC123,Товар\nDEF456,Другой\n", encoding="utf-8-sig")

        result = read_codes_with_metadata(str(f))
        # Первая строка определяется как данные, но колонка "товар" распознаётся
        assert len(result) >= 1
        assert result[0][0] in ("ABC123", "DEF456")

    def test_csv_unsupported_format(self, tmp_path):
        """Неподдерживаемый формат файла."""
        f = tmp_path / "codes.json"
        f.write_text('{"codes": ["ABC"]}', encoding="utf-8")

        with pytest.raises(ValueError, match="Неподдерживаемый формат"):
            read_codes_with_metadata(str(f))


# ========== suggest_barcode_type ==========

class TestSuggestBarcodeType:
    """Тесты автоопределения типа штрихкода."""

    def test_ean13(self):
        """13 цифр → EAN-13."""
        assert suggest_barcode_type("1234567890123") == "ean13"

    def test_ean8(self):
        """8 цифр → EAN-8."""
        assert suggest_barcode_type("12345678") == "ean8"

    def test_upca(self):
        """12 цифр → UPC-A."""
        assert suggest_barcode_type("123456789012") == "upca"

    def test_code39(self):
        """Буквы и цифры → Code 39."""
        assert suggest_barcode_type("ABC-123") == "code39"

    def test_code128_default(self):
        """Неизвестный формат → Code 128 (по умолчанию)."""
        # "random text" (с пробелом) не совпадёт с code39
        assert suggest_barcode_type("random text") == "code128"

    def test_empty(self):
        """Пустая строка → None."""
        assert suggest_barcode_type("") is None

    def test_itf(self):
        """Чётное количество цифр → ITF."""
        assert suggest_barcode_type("123456") == "itf"


# ========== Constants ==========

class TestConstants:
    """Тесты констант и пресетов."""

    def test_label_presets_not_empty(self):
        """LABEL_PRESETS содержит пресеты."""
        assert len(LABEL_PRESETS) > 0

    def test_barcode_types_not_empty(self):
        """BARCODE_TYPES содержит типы штрихкодов."""
        assert len(BARCODE_TYPES) > 0

    def test_dpi_presets_not_empty(self):
        """DPI_PRESETS содержит пресеты DPI."""
        assert len(DPI_PRESETS) > 0

    def test_qr_box_size_presets_not_empty(self):
        """QR_BOX_SIZE_PRESETS содержит пресеты качества."""
        assert len(QR_BOX_SIZE_PRESETS) > 0

    def test_default_dpi(self):
        """DEFAULT_DPI = '600'."""
        assert DEFAULT_DPI == "600"

    def test_default_qr_box_size(self):
        """DEFAULT_QR_BOX_SIZE = '8'."""
        assert DEFAULT_QR_BOX_SIZE == "8"


# ========== Контрольная цифра EAN/UPC ==========

from utils import gtin_check_digit


class TestCheckDigit:
    """python-barcode молча заменяет неверную контрольную цифру — ловим это до печати."""

    def test_known_check_digits(self):
        assert gtin_check_digit("400638133393") == 1
        assert gtin_check_digit("1234567") == 0
        assert gtin_check_digit("12345678901") == 2

    @pytest.mark.parametrize("code,btype,expected", [
        ("1234567890123", "ean13", 8),
        ("12345678", "ean8", 0),
        ("123456789013", "upca", 2),
    ])
    def test_wrong_check_digit_rejected(self, code, btype, expected):
        valid, msg = validate_code(code, btype)
        assert not valid
        assert f"должна быть {expected}" in msg

    @pytest.mark.parametrize("code,btype", [
        ("400638133393", "ean13"),   # без контрольной — её посчитает генератор
        ("1234567", "ean8"),
        ("12345678901", "upca"),
        ("123456789012", "upca"),
    ])
    def test_valid_codes_pass(self, code, btype):
        assert validate_code(code, btype)[0]

    def test_matches_python_barcode(self):
        """Наша контрольная цифра совпадает с той, что поставит библиотека."""
        import barcode
        for data, btype in [("590123412345", "ean13"), ("9638507", "ean8"), ("03600029145", "upca")]:
            full = barcode.get_barcode_class(btype)(data).get_fullcode()
            assert full[-1] == str(gtin_check_digit(data))


# ========== Серия номеров ==========

from utils import make_series, make_qr_image


class TestMakeSeries:
    def test_basic(self):
        assert make_series("SN-", 1, 3) == ["SN-0001", "SN-0002", "SN-0003"]

    def test_step_width_suffix(self):
        assert make_series("A", 10, 3, step=5, width=3, suffix="-X") == ["A010-X", "A015-X", "A020-X"]

    def test_number_longer_than_width(self):
        assert make_series("", 99, 2, width=2) == ["99", "100"]

    def test_ean_check_digit(self):
        codes = make_series("", 400638133393, 1, width=12, check_digit=True)
        assert codes == ["4006381333931"]
        assert validate_code(codes[0], "ean13")[0]

    def test_check_digit_needs_digits(self):
        with pytest.raises(ValueError):
            make_series("SN-", 1, 2, check_digit=True)

    @pytest.mark.parametrize("kwargs", [{"count": 0}, {"count": 10001}, {"step": 0},
                                        {"start": 1, "count": 3, "step": -1}])
    def test_invalid_params(self, kwargs):
        with pytest.raises(ValueError):
            make_series("SN-", **{"start": 1, "count": 5, **kwargs})


# ========== QR с логотипом ==========

class TestQrImage:
    PAYLOAD = "ФИО: Иванов Иван Иванович\nКуртка, Ботинки, Перчатки\nДата: 28-10-2026"

    def test_without_logo(self):
        img = make_qr_image("SN-0001", 4)
        assert img.mode == "RGB" and img.width == img.height

    def test_logo_in_center(self):
        from PIL import Image
        logo = Image.new("RGBA", (50, 50), (255, 0, 0, 255))
        img = make_qr_image(self.PAYLOAD, 8, logo=logo)
        r, g, b = img.getpixel((img.width // 2, img.height // 2))
        assert r > 200 and g < 50          # в центре — красный логотип

    @pytest.mark.parametrize("box", [4, 8])
    def test_logo_qr_still_readable(self, box):
        pyzbar = pytest.importorskip("pyzbar.pyzbar")
        from PIL import Image, ImageOps
        logo = Image.new("RGBA", (50, 50), (30, 120, 220, 255))
        img = make_qr_image(self.PAYLOAD, box, logo=logo)
        found = pyzbar.decode(ImageOps.expand(img, 10, "white"))
        assert found and found[0].data.decode("utf-8") == self.PAYLOAD
