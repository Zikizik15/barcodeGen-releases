# utils.py - Вспомогательные функции и инструменты

import os
import io
import csv
import subprocess
import platform
import re
import sys
import struct
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
def find_font_path(family=None):
    """Поиск системного шрифта.

    family — имя семейства из list_fonts(). Если оно задано и найден его
    файл — вернёт его; иначе (или если не найден) — запасной список системных
    шрифтов, как раньше.
    """
    if family:
        path = find_font_path_by_family(family)
        if path:
            return path
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


# ========== ВЫБОР ШРИФТА ДЛЯ ПОДПИСИ ПОД ШТРИХКОДОМ ==========
# Пользователь выбирает семейство из встроенного Montserrat и системных
# шрифтов. Семейство определяется по name-таблице OpenType (без загрузки
# всего файла в PIL — список строится быстро даже на Windows с ~400 шрифтами).

BARCODE_FONT_DEFAULT = "Montserrat"


def _project_root():
    """Корень приложения — рядом с ним лежит папка fonts/."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _font_search_dirs():
    """Каталоги, в которых ищем шрифты для выбора подписи."""
    dirs = [os.path.join(_project_root(), "fonts")]
    if os.name == "nt":
        windir = os.environ.get("WINDIR")
        if windir:
            dirs.append(os.path.join(windir, "Fonts"))
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
    elif sys.platform == "darwin":
        dirs += ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental",
                 "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
    else:
        dirs += ["/usr/share/fonts", "/usr/local/share/fonts",
                 os.path.expanduser("~/.fonts"), os.path.expanduser("~/.local/share/fonts")]
    return [d for d in dirs if d and os.path.isdir(d)]


def _font_files(dirs):
    """Все файлы шрифтов (.ttf/.otf/.ttc) в каталогах."""
    for directory in dirs:
        for root, _, files in os.walk(directory):
            for fn in files:
                if fn.lower().endswith((".ttf", ".otf", ".ttc")):
                    yield os.path.join(root, fn)


def _family_from_name_table(data):
    """Читает name-таблицу OpenType и возвращает имя семейства (nameID 1),
    либо typographic family (nameID 16), если обычного имени нет."""
    if len(data) < 10:
        return None
    try:
        count = struct.unpack(">H", data[2:4])[0]
        str_off = struct.unpack(">H", data[4:6])[0]
    except Exception:
        return None
    fallback = None
    for i in range(count):
        rec = data[6 + i * 12: 6 + i * 12 + 12]
        if len(rec) < 12:
            break
        try:
            pid, eid, lid, nid, length, offset = struct.unpack(">HHHHHH", rec)
        except Exception:
            break
        if nid not in (1, 16):
            continue
        # Учитываем записи: Windows (3), Unicode (0) и Mac (1)
        if pid == 3:
            if lid not in (0x409, 0):
                continue
            codec = "utf-16-be"
        elif pid in (0, 1):
            if lid != 0:
                continue
            codec = "utf-16-be" if pid == 0 else "mac_roman"
        else:
            continue
        raw = data[str_off + offset: str_off + offset + length]
        try:
            name = raw.decode(codec, errors="ignore").strip("\x00 \t")
        except Exception:
            continue
        if not name:
            continue
        if nid == 1:
            return name
        if fallback is None:
            fallback = name
    return fallback


def _font_family_from_file(path):
    """Имя семейства шрифта через быстрый разбор name-таблицы (без PIL)."""
    try:
        with open(path, "rb") as f:
            head = f.read(12)
            if head[:4] == b"ttcf":  # коллекция .ttc — берём первый шрифт
                num_fonts = struct.unpack(">I", head[8:12])[0]
                if not num_fonts:
                    return None
                f.seek(12)
                first_offset = struct.unpack(">I", f.read(4))[0]
                f.seek(first_offset)
                head = f.read(12)
            if len(head) < 6:
                return None
            num_tables = struct.unpack(">H", head[4:6])[0]
            records = f.read(num_tables * 16)
            name_off = name_len = None
            for i in range(num_tables):
                rec = records[i * 16: i * 16 + 16]
                if len(rec) < 16:
                    break
                tag, _checksum, off, ln = struct.unpack(">4sIII", rec)
                if tag == b"name":
                    name_off, name_len = off, ln
                    break
            if name_off is None:
                return None
            f.seek(name_off)
            data = f.read(min(name_len, 65536))
    except Exception:
        return None
    return _family_from_name_table(data)


_fonts_list_cache = None


def list_fonts(force=False):
    """[(семейство, путь), ...] — все найденные шрифты, Montserrat первым.

    Результат кэшируется: дорогое сканирование каталогов выполняется один раз.
    """
    global _fonts_list_cache
    if _fonts_list_cache is not None and not force:
        return _fonts_list_cache
    bundled_dir = os.path.normcase(os.path.join(_project_root(), "fonts"))
    seen = {}
    for path in _font_files(_font_search_dirs()):
        family = _font_family_from_file(path)
        if not family:
            continue
        # Все веса встроенного Montserrat-*.ttf дают одно семейство
        if os.path.normcase(os.path.dirname(path)) == bundled_dir:
            family = BARCODE_FONT_DEFAULT
        key = family.casefold()
        if key not in seen:
            seen[key] = (family, path)
    result = sorted(seen.values(),
                    key=lambda item: (item[0].casefold() != BARCODE_FONT_DEFAULT.casefold(),
                                      item[0].casefold()))
    _fonts_list_cache = result
    return result


def find_font_path_by_family(family):
    """Путь к файлу выбранного семейства или None, если шрифт не найден."""
    family = (family or "").strip()
    if not family:
        return None
    target = family.casefold()
    for name, path in list_fonts():
        if name.casefold() == target:
            return path
    return None


# ========== ПРОВЕРКА КОДА ==========
# EAN-13, EAN-8 и UPC-A: длина без контрольной цифры
_GTIN_DATA_LEN = {"ean13": 12, "ean8": 7, "upca": 11}


def gtin_check_digit(digits):
    """Контрольная цифра EAN/UPC: справа налево веса 3, 1, 3, 1, …"""
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10


def _check_gtin(code_str, barcode_type, name):
    """Если код введён вместе с контрольной цифрой — она должна быть верной.
    Иначе python-barcode молча заменит её, и на этикетке окажется другой код."""
    data_len = _GTIN_DATA_LEN[barcode_type]
    if len(code_str) == data_len + 1:
        expected = gtin_check_digit(code_str[:data_len])
        if int(code_str[-1]) != expected:
            return False, f"{name}: неверная контрольная цифра — последней должна быть {expected}"
    return True, "OK"


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
        return _check_gtin(code_str, barcode_type, "EAN-13")
    elif barcode_type == "ean8":
        if not re.match(r'^\d{7,8}$', code_str):
            return False, "EAN-8: код должен состоять из 7 или 8 цифр"
        return _check_gtin(code_str, barcode_type, "EAN-8")
    elif barcode_type == "upca":
        if not re.match(r'^\d{11,12}$', code_str):
            return False, "UPC-A: код должен состоять из 11 или 12 цифр"
        return _check_gtin(code_str, barcode_type, "UPC-A")
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

# ========== СЕРИЯ НОМЕРОВ ==========
MAX_SERIES = 10000


def make_series(prefix="", start=1, count=10, step=1, width=4, suffix="", check_digit=False):
    """Последовательные коды: make_series("SN-", 1, 3) → SN-0001, SN-0002, SN-0003.
    width — минимальное число цифр (дополняется нулями слева).
    check_digit — дописать контрольную цифру EAN/UPC (номер должен быть из цифр)."""
    if count < 1 or count > MAX_SERIES:
        raise ValueError(f"Количество — от 1 до {MAX_SERIES}")
    if step == 0:
        raise ValueError("Шаг не может быть нулевым")
    codes = []
    for i in range(count):
        n = start + i * step
        if n < 0:
            raise ValueError("Номер получился отрицательным — уменьшите шаг или количество")
        code = f"{prefix}{n:0{max(1, width)}d}{suffix}"
        if check_digit:
            if not code.isdigit():
                raise ValueError("Для контрольной цифры код должен состоять только из цифр")
            code += str(gtin_check_digit(code))
        codes.append(code)
    return codes


# ========== QR-КОД ==========
def make_qr_image(data, box_size=8, logo=None, border=2):
    """QR-код как картинка PIL. С логотипом включается коррекция ошибок H
    (до 30% кода можно закрыть), логотип ставится в центр на белую подложку."""
    import qrcode
    from PIL import ImageDraw

    qr = qrcode.QRCode(
        version=None, box_size=int(box_size), border=border,
        error_correction=qrcode.constants.ERROR_CORRECT_H if logo is not None
        else qrcode.constants.ERROR_CORRECT_M,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    if logo is None:
        return img

    # Подложка ~24% ширины: это заметно меньше допустимых 30% потерь
    side = int(img.width * 0.24)
    pad = max(2, side // 10)
    badge = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ImageDraw.Draw(badge).rounded_rectangle([0, 0, side - 1, side - 1],
                                            radius=side // 5, fill="white")
    mark = logo.convert("RGBA")
    k = min((side - 2 * pad) / mark.width, (side - 2 * pad) / mark.height)
    mark = mark.resize((max(1, int(mark.width * k)), max(1, int(mark.height * k))), Image.LANCZOS)
    badge.alpha_composite(mark, ((side - mark.width) // 2, (side - mark.height) // 2))
    img.paste(badge, ((img.width - side) // 2, (img.height - side) // 2), badge)
    return img
