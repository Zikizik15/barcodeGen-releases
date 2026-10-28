# utils.py - Вспомогательные функции и инструменты

import os
import io
import csv
import subprocess
import platform
import re
from PIL import Image, ImageOps


# ========== ПРЕСЕТЫ РАЗМЕРОВ ЭТИКЕТОК ==========
LABEL_PRESETS = {
    "25×15 мм (маленькая, для ценников)": ("25", "15"),
    "40×30 мм (средняя, для товаров)": ("40", "30"),
    "50×25 мм (для логистики)": ("50", "25"),
    "58×40 мм (стандарт для чеков)": ("58", "40"),
    "60×40 мм (евростандарт)": ("60", "40"),
    "70×50 мм (крупная, для коробок)": ("70", "50"),
    "76×51 мм (американский стандарт)": ("76", "51"),
    "100×70 мм (большая, для накладных)": ("100", "70"),
    "100×150 мм (очень большая)": ("100", "150"),
    "Dymo 30336 (9×50 мм)": ("9", "50"),
    "Dymo 450 (12×29 мм)": ("12", "29"),
    "Avery 5160 (63.5×25.4 мм)": ("63.5", "25.4"),
}

# ========== СЕТКА РАСКЛАДКИ ==========
GRID_MAP = {1: (1, 1), 2: (2, 1), 4: (2, 2), 6: (3, 2), 8: (4, 2), 9: (3, 3), 12: (4, 3)}
LABELS_PER_PAGE_OPTIONS = [1, 2, 4, 6, 8, 9, 12]

# ========== ТИПЫ ШТРИХКОДОВ ==========
BARCODE_TYPES = [
    ("code128", "📊 Code 128 (универсальный)"),
    ("code39", "🔢 Code 39"),
    ("ean13", "🛒 EAN-13 (розница)"),
    ("ean8", "🛒 EAN-8 (розница, короткий)"),
    ("upca", "🇺🇸 UPC-A (США/Канада)"),
    ("itf", "📦 ITF (Interleaved 2 of 5)"),
    ("codabar", "🏥 Codabar (мед./библиотеки)"),
]

# ========== ПРЕСЕТЫ DPI ==========
DPI_PRESETS = [
    ("300", "300 dpi — быстро, для черновиков и офисной печати"),
    ("600", "600 dpi — оптимально (по умолчанию), подходит для большинства термопринтеров"),
    ("900", "900 dpi — высокое качество, для термотрансферных принтеров 300 dpi"),
    ("1200", "1200 dpi — очень высокое, для промышленных принтеров"),
    ("2400", "2400 dpi — максимальное, для полиграфии (медленно, большие файлы)"),
]

DEFAULT_DPI = "600"

# ========== ПРЕСЕТЫ КАЧЕСТВА QR-КОДОВ ==========
# box_size определяет размер каждой "модульной клетки" QR-кода.
# Больше box_size → больше пикселей на единицу → выше качество при печати.
# Примерный DPI при печати на 58×40 мм: box_size=4 → ~300, 8 → ~600, 16 → ~1200
QR_BOX_SIZE_PRESETS = [
    ("4", "4 — быстро, ~300 dpi эквивалент"),
    ("8", "8 — стандарт, ~600 dpi (по умолчанию)"),
    ("12", "12 — высокое, ~900 dpi"),
    ("16", "16 — очень высокое, ~1200 dpi"),
    ("20", "20 — максимальное, ~1500 dpi"),
]

DEFAULT_QR_BOX_SIZE = "8"


# ========== ОТКРЫТИЕ PDF ==========
def open_pdf(filepath):
    """Открывает PDF в стандартном просмотрщике"""
    if platform.system() == "Windows":
        os.startfile(filepath)
    elif platform.system() == "Darwin":
        subprocess.run(["open", filepath])
    else:
        subprocess.run(["xdg-open", filepath])


# ========== ОЧИСТКА ИМЕНИ ФАЙЛА ==========
def sanitize_filename(code):
    """Очищает код для использования в имени файла"""
    return "".join(c if c.isalnum() else '_' for c in str(code)[:20])


# ========== ОБРЕЗКА ИЗОБРАЖЕНИЙ ==========
def crop_barcode_image(img_path):
    """Обрезает белые поля вокруг штрихкода"""
    try:
        img = Image.open(img_path)
        bbox = img.getbbox()
        if bbox:
            left, top, right, bottom = bbox
            left = max(0, left - 1)
            top = max(0, top - 1)
            right = min(img.width, right + 1)
            bottom = min(img.height, bottom + 1)
            cropped = img.crop((left, top, right, bottom))
            cropped.save(img_path)
        return img_path
    except Exception as e:
        print(f"Ошибка обрезки: {e}")
        return img_path


def _find_content_bbox(img, threshold=240):
    """Быстрый поиск границ непустого содержимого через PIL.getbbox()."""
    gray = img.convert('L')
    mask = gray.point(lambda p: 255 if p < threshold else 0)
    return mask.getbbox()


def crop_barcode_aggressive(img_path):
    """Агрессивная обрезка - находит границы непустого содержимого по порогу"""
    try:
        img = Image.open(img_path)
        width, height = img.size
        bbox = _find_content_bbox(img)

        if bbox:
            left, top, right, bottom = bbox
            left = max(0, left - 1)
            top = max(0, top - 1)
            right = min(width, right + 2)
            bottom = min(height, bottom + 2)
            cropped = img.crop((left, top, right, bottom))
            cropped.save(img_path)
        return img_path
    except Exception as e:
        print(f"Ошибка обрезки: {e}")
        return img_path


def crop_barcode_aggressive_from_bytes(img_bytes, output_path=None):
    """Обрезка изображения из байтового потока по порогу"""
    try:
        img = Image.open(img_bytes)
        width, height = img.size
        bbox = _find_content_bbox(img)

        if bbox:
            left, top, right, bottom = bbox
            left = max(0, left - 1)
            top = max(0, top - 1)
            right = min(width, right + 2)
            bottom = min(height, bottom + 2)
            cropped = img.crop((left, top, right, bottom))
        else:
            cropped = img

        if output_path:
            cropped.save(output_path)
            return output_path
        else:
            buffer = io.BytesIO()
            cropped.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer
    except Exception as e:
        print(f"Ошибка обрезки: {e}")
        if output_path:
            return output_path
        return img_bytes


# ========== ПАРАМЕТРЫ ШТРИХКОДА ==========
def get_barcode_params(label_w_mm, label_h_mm, dpi=None):
    """Возвращает параметры штрихкода под размер этикетки и выбранный DPI.

    dpi по умолчанию — 600 (оптимально для большинства термопринтеров).
    Больше dpi → чётче картинка при растягивании, но больше размер и время.
    """
    base_w, base_h = 58, 40
    base_module_w, base_module_h = 0.25, 10.0

    scale = min(label_w_mm / base_w, label_h_mm / base_h)
    scale = max(0.5, min(2.0, scale))

    if dpi is None:
        dpi = DEFAULT_DPI
    try:
        dpi_int = int(dpi)
    except (ValueError, TypeError):
        dpi_int = int(DEFAULT_DPI)

    return {
        'module_width': base_module_w * scale,
        'module_height': base_module_h * scale,
        'dpi': dpi_int,
    }


# ========== ПОИСК ШРИФТА ==========
def find_font_path():
    """Поиск системного шрифта"""
    font_paths = [
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf',
        'C:/Windows/Fonts/Arial.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ]
    for font_path in font_paths:
        if os.path.exists(font_path):
            return font_path
    return None


# ========== ПРОВЕРКА КОДА ==========
def validate_code(code, barcode_type):
    """Проверка кода на соответствие типу штрихкода"""
    code_str = str(code).strip()
    if not code_str:
        return False, "Пустой код"

    if barcode_type == "code39":
        if not re.match(r'^[A-Z0-9\-\.\$\/\+\%]+$', code_str.upper()):
            return False, "Code 39: только A-Z, 0-9, -, ., $, /, +, %"
    elif barcode_type == "ean13":
        if not re.match(r'^\d{12,13}$', code_str):
            return False, "EAN-13: код должен состоять из 12 или 13 цифр"
    elif barcode_type == "ean8":
        if not re.match(r'^\d{7,8}$', code_str):
            return False, "EAN-8: код должен состоять из 7 или 8 цифр"
    elif barcode_type == "upca":
        if not re.match(r'^\d{11,12}$', code_str):
            return False, "UPC-A: код должен состоять из 11 или 12 цифр"
    elif barcode_type == "itf":
        if not re.match(r'^\d+$', code_str):
            return False, "ITF: только цифры"
        if len(code_str) % 2 != 0:
            return False, "ITF: нужно чётное количество цифр (можно добавить 0 спереди)"
    elif barcode_type == "codabar":
        if not re.match(r'^[A-Da-d]?[0-9\-\$\:\/\.\+]+[A-Da-d]?$', code_str):
            return False, "Codabar: цифры и -,$,:,/,.,+ (можно с буквой A-D по краям)"
    elif barcode_type == "code128":
        if not all(32 <= ord(c) <= 126 for c in code_str):
            return False, "Code 128: только ASCII-символы (32-126)"

    return True, "OK"


# ========== ПРЯМАЯ ПЕЧАТЬ ==========
def print_pdf(filepath):
    """Отправляет PDF на печать без диалога сохранения.

    На Windows использует системный print verb через ShellExecuteW,
    на macOS/Linux — утилиту lp."""
    try:
        if platform.system() == "Windows":
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "print", filepath, None, None, 1)
            return True, "Отправлено на принтер по умолчанию"
        elif platform.system() == "Darwin":
            subprocess.run(["lp", filepath], check=True)
            return True, "Отправлено на принтер"
        else:
            subprocess.run(["lp", filepath], check=True)
            return True, "Отправлено на принтер"
    except FileNotFoundError:
        return False, "Система печати не найдена"
    except subprocess.CalledProcessError as e:
        return False, f"Ошибка печати: {e}"
    except Exception as e:
        return False, f"Ошибка: {e}"


# ========== QA ПРОВЕРКА ШТРИХКОДА ==========
def verify_barcode_image(img_path, expected_code):
    """Проверяет, что штрихкод на картинке читается сканером и совпадает с ожидаемым.

    Возвращает (success: bool | None, decoded: str, message: str).
    success=None означает, что pyzbar не установлен.

    Важно: pyzbar/zbar требует белую рамку вокруг штрихкода, а наш генератор
    специально обрезает картинку вплотную (quiet_zone=0) — поэтому перед
    распознаванием искусственно добавляем белую рамку 20px.
    """
    try:
        from pyzbar.pyzbar import decode

        img = Image.open(img_path).convert('RGB')
        img = ImageOps.expand(img, border=20, fill='white')

        results = decode(img)
        if not results:
            return False, "", "Штрихкод не распознан сканером"

        decoded = results[0].data.decode('utf-8', errors='replace')
        if decoded == expected_code:
            return True, decoded, "OK"
        else:
            return False, decoded, f"Распознан как '{decoded}', а ожидался '{expected_code}'"

    except ImportError:
        return None, "", "pyzbar не установлен — QA недоступен"
    except Exception as e:
        return False, "", f"Ошибка проверки: {e}"


# ========== ЧТЕНИЕ ФАЙЛОВ С МЕТАДАННЫМИ ==========
def read_codes_with_metadata(filepath):
    """Читает файл с кодами и метаданными.

    Поддерживает:
      - .txt:  только коды (по одному на строку)
      - .csv:  code, name, price, ... (первая строка — заголовки, опционально)
      - .xlsx: то же самое через openpyxl

    Возвращает список кортежей: [(code, {name, price, ...}), ...]
    """
    ext = os.path.splitext(filepath)[1].lower()
    result = []

    if ext == ".txt":
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                code = line.strip()
                if code:
                    result.append((code, {}))
        return result

    if ext == ".csv":
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            sample = f.read(1024)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
            except csv.Error:
                dialect = csv.excel
            reader = csv.reader(f, dialect)
            rows = [row for row in reader if any(cell.strip() for cell in row)]

        return _parse_rows(rows)

    if ext == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ImportError("Для чтения Excel установите openpyxl: pip install openpyxl")

        wb = load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            if row and any(cell is not None and str(cell).strip() for cell in row):
                rows.append([str(cell) if cell is not None else "" for cell in row])
        wb.close()

        return _parse_rows(rows)

    raise ValueError(f"Неподдерживаемый формат файла: {ext}")


def _parse_rows(rows):
    """Общий парсер строк CSV/XLSX.
    Определяет, где заголовок, где колонка кода, и собирает метаданные."""
    if not rows:
        return []

    first = rows[0]
    has_header = any(
        cell.strip() and not cell.strip().replace('.', '').replace(',', '').isdigit()
        for cell in first
    )

    if has_header:
        headers = [h.strip().lower() for h in first]
        data_rows = rows[1:]
    else:
        headers = ["code", "name", "price"][:len(first)]
        data_rows = rows

    # Ищем колонку кода среди типовых названий
    code_idx = 0
    for key in ("code", "код", "barcode", "штрихкод", "sku", "артикул"):
        if key in headers:
            code_idx = headers.index(key)
            break

    result = []
    for row in data_rows:
        if not row or code_idx >= len(row) or not row[code_idx].strip():
            continue
        code = row[code_idx].strip()
        meta = {}
        for i, val in enumerate(row):
            if i == code_idx:
                continue
            if i < len(headers) and val.strip():
                meta[headers[i]] = val.strip()
        result.append((code, meta))

    return result


# ========== АВТООПРЕДЕЛЕНИЕ ТИПА ШТРИХКОДА ==========
def suggest_barcode_type(code):
    """Предлагает подходящий тип ШК по формату кода.
    Используется для подсказки пользователю: «13 цифр — возможно, EAN-13»."""
    code_str = str(code).strip()
    if not code_str:
        return None

    if re.match(r'^\d{13}$', code_str):
        return "ean13"
    if re.match(r'^\d{8}$', code_str):
        return "ean8"
    if re.match(r'^\d{12}$', code_str):
        return "upca"
    if re.match(r'^[A-Z0-9\-\.\$\/\+\%]+$', code_str.upper()):
        if re.match(r'^\d+$', code_str) and len(code_str) % 2 == 0 and len(code_str) >= 6:
            return "itf"
        return "code39"
    return "code128"