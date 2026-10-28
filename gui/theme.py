# gui/theme.py - Единая дизайн-система приложения
#
# Стиль — как у фирменных панелей водоматов: белые карточки с голубой
# обводкой, тёмно-синие заголовки КАПСОМ (Montserrat Black), нумерованные
# шаги в синих квадратах, яркие кнопки по смыслу (зелёная — старт,
# синяя — просмотр, красная — удалить), чёрный «дисплей» внизу и
# логотип-мозаика из разноцветных бутылок со знаком переработки.
#
# Все окна берут цвета, шрифты и готовые виджеты только отсюда —
# чтобы поменять внешний вид, достаточно поправить этот файл.

import os
import sys
import math
import random
import tkinter as tk
import customtkinter as ctk
from customtkinter import ThemeManager

# ========== ФИРМЕННЫЕ ЦВЕТА ==========
NAVY = "#1B2A5E"           # заголовки
NAVY_HOVER = "#2B3D7C"
ROYAL = "#22409A"          # сайдбар, номера шагов
ROYAL_HOVER = "#2D4FB3"
BLUE = "#1E88E5"           # вторая по важности кнопка
BLUE_HOVER = "#1673C6"
BLUE_SOFT = "#E3EEFC"      # светло-голубые плашки
GREEN = "#38B24A"          # «Старт» — главное действие
GREEN_HOVER = "#2E9A3F"
RED = "#E2302F"            # «Стоп» — удаление, ошибки
YELLOW = "#F7B52C"         # активный пункт меню, подсветка
DISPLAY = "#1D1D1F"        # чёрная панель-«дисплей»

# ========== РОЛИ ЦВЕТОВ ==========
BG = "#F2F5FA"             # фон окна
SURFACE = "#FFFFFF"        # карточки
SURFACE_2 = "#EDF1F8"      # поля ввода, вторичные кнопки
SURFACE_HOVER = "#DDE5F2"
BORDER = "#D3DDEE"         # голубоватая обводка карточек

TEXT = NAVY
TEXT_2 = "#56648A"         # подписи, мета-информация
TEXT_3 = "#98A2BB"         # плейсхолдеры, неактивное

ACCENT = GREEN
ACCENT_HOVER = GREEN_HOVER
ON_ACCENT = "#FFFFFF"      # текст на цветных кнопках

SIDEBAR = ROYAL
SIDEBAR_TEXT = "#FFFFFF"
SIDEBAR_TEXT_2 = "#C3CEEF"
SIDEBAR_HOVER = ROYAL_HOVER

SUCCESS = GREEN
WARNING = YELLOW
ERROR = RED
ERROR_BG = "#FDE5E5"
ERROR_HOVER = "#F9CDCD"

HIGHLIGHT_BG = "#FDEAB3"   # подсветка найденного при поиске
INVALID_BG = "#FDE5E5"     # подсветка строк с ошибкой
SELECTION_BG = "#CFE2FA"

PAPER = "#FFFFFF"          # «бумага» в предпросмотре и редакторе
CANVAS_BG = "#E6EBF4"      # фон под листом этикетки
PAPER_SHADOW = "#C5CEDF"

# Цвета «бутылок» для логотипа-мозаики
MOSAIC_COLORS = ["#1E88E5", "#1565C0", "#64B5F6", "#38B24A", "#7CB342", "#2E7D32",
                 "#E2302F", "#F7B52C", "#FB8C00", "#8E24AA", "#00ACC1", "#D81B60",
                 "#3949AB", "#90CAF9", "#FFD54F"]


# ========== ШРИФТЫ ==========
def _base_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _register_fonts():
    """Подключает Montserrat из папки fonts/ только для этого процесса
    (в систему ничего не устанавливается). True — если получилось."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        fonts_dir = os.path.join(_base_dir(), "fonts")
        loaded = 0
        for name in ("Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"):
            path = os.path.join(fonts_dir, f"Montserrat-{name}.ttf")
            # 0x10 = FR_PRIVATE
            if os.path.exists(path) and ctypes.windll.gdi32.AddFontResourceExW(path, 0x10, 0):
                loaded += 1
        return loaded == 6
    except Exception:
        return False


_MONTSERRAT = _register_fonts()

if _MONTSERRAT:
    FONT_UI = "Montserrat"
    _WEIGHTS = {
        "normal": ("Montserrat Medium", "normal"),
        "semibold": ("Montserrat SemiBold", "normal"),
        "bold": ("Montserrat", "bold"),
        "extrabold": ("Montserrat ExtraBold", "normal"),
        "black": ("Montserrat Black", "normal"),
    }
elif sys.platform == "win32":
    FONT_UI = "Segoe UI"
    _WEIGHTS = {
        "normal": ("Segoe UI", "normal"),
        "semibold": ("Segoe UI Semibold", "normal"),
        "bold": ("Segoe UI", "bold"),
        "extrabold": ("Segoe UI", "bold"),
        "black": ("Segoe UI Black", "normal"),
    }
else:
    FONT_UI = "SF Pro Text" if sys.platform == "darwin" else "Ubuntu"
    _WEIGHTS = {w: (FONT_UI, "normal" if w in ("normal", "semibold") else "bold")
                for w in ("normal", "semibold", "bold", "extrabold", "black")}

FONT_MONO = {"win32": "Consolas", "darwin": "Menlo"}.get(sys.platform, "DejaVu Sans Mono")

_font_cache = {}


def font(size=13, weight="normal", mono=False):
    """CTkFont из кэша. weight: normal | semibold | bold | extrabold | black."""
    key = (size, weight, mono)
    if key not in _font_cache:
        if mono:
            family, w = FONT_MONO, ("bold" if weight != "normal" else "normal")
        else:
            family, w = _WEIGHTS.get(weight, _WEIGHTS["normal"])
        _font_cache[key] = ctk.CTkFont(family=family, size=size, weight=w)
    return _font_cache[key]


# ========== ТЕМА CUSTOMTKINTER ==========
def _pair(c):
    return [c, c]


def apply_theme():
    """Светлый режим и цвета по умолчанию для всех CTk-виджетов,
    включая системные диалоги (CTkInputDialog), скроллбары и выпадающие меню."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    t = ThemeManager.theme
    t["CTk"]["fg_color"] = _pair(BG)
    t["CTkToplevel"]["fg_color"] = _pair(BG)
    t["CTkFrame"].update(fg_color=_pair(SURFACE), top_fg_color=_pair(SURFACE_2),
                         border_color=_pair(BORDER), corner_radius=16)
    t["CTkButton"].update(fg_color=_pair(SURFACE_2), hover_color=_pair(SURFACE_HOVER),
                          text_color=_pair(TEXT), text_color_disabled=_pair(TEXT_3),
                          border_color=_pair(BORDER), corner_radius=20)
    t["CTkLabel"].update(text_color=_pair(TEXT))
    t["CTkEntry"].update(fg_color=_pair(SURFACE_2), border_color=_pair(SURFACE_2),
                         text_color=_pair(TEXT), placeholder_text_color=_pair(TEXT_3),
                         corner_radius=12, border_width=1)
    t["CTkTextbox"].update(fg_color=_pair(SURFACE), border_color=_pair(BORDER),
                           text_color=_pair(TEXT), corner_radius=16,
                           scrollbar_button_color=_pair(SURFACE_HOVER),
                           scrollbar_button_hover_color=_pair(TEXT_3))
    t["CTkCheckBox"].update(fg_color=_pair(GREEN), hover_color=_pair(GREEN_HOVER),
                            border_color=_pair(TEXT_3), checkmark_color=_pair(ON_ACCENT),
                            text_color=_pair(TEXT), corner_radius=6, border_width=2)
    t["CTkSwitch"].update(fg_color=_pair(SURFACE_HOVER), progress_color=_pair(GREEN),
                          button_color=_pair(SURFACE), button_hover_color=_pair(SURFACE),
                          text_color=_pair(TEXT))
    t["CTkRadioButton"].update(fg_color=_pair(ROYAL), hover_color=_pair(ROYAL_HOVER),
                               border_color=_pair(TEXT_3), text_color=_pair(TEXT))
    t["CTkProgressBar"].update(fg_color=_pair(SURFACE_2), progress_color=_pair(GREEN))
    t["CTkOptionMenu"].update(fg_color=_pair(SURFACE_2), button_color=_pair(SURFACE_2),
                              button_hover_color=_pair(SURFACE_HOVER),
                              text_color=_pair(TEXT), corner_radius=12)
    t["CTkComboBox"].update(fg_color=_pair(SURFACE_2), border_color=_pair(SURFACE_2),
                            button_color=_pair(SURFACE_2), button_hover_color=_pair(SURFACE_HOVER),
                            text_color=_pair(TEXT))
    t["CTkScrollbar"].update(button_color=_pair(SURFACE_HOVER),
                             button_hover_color=_pair(TEXT_3))
    t["CTkSegmentedButton"].update(fg_color=_pair(SURFACE_2), selected_color=_pair(ROYAL),
                                   selected_hover_color=_pair(ROYAL_HOVER),
                                   unselected_color=_pair(SURFACE_2),
                                   unselected_hover_color=_pair(SURFACE_HOVER),
                                   text_color=_pair(TEXT), corner_radius=12, border_width=3)
    t["CTkScrollableFrame"].update(label_fg_color=_pair(SURFACE))
    t["DropdownMenu"].update(fg_color=_pair(SURFACE), hover_color=_pair(SURFACE_2),
                             text_color=_pair(TEXT))
    t["CTkFont"].update(family=_WEIGHTS["normal"][0], size=13)


def fit_to_screen(window, width, height, min_width=900, min_height=600):
    """Размер окна, который гарантированно помещается на экран, по центру."""
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    w = min(width, sw - 60)
    h = min(height, sh - 100)
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2 - 20)
    window.geometry(f"{w}x{h}+{x}+{y}")
    window.minsize(min(min_width, w), min(min_height, h))


def app_icon_path():
    """Путь к logo.ico — и при запуске из исходников, и в собранном exe."""
    path = os.path.join(_base_dir(), "logo.ico")
    return path if os.path.exists(path) else None


def setup_dialog(window, parent, title_text, width, height, modal=True, resizable=True):
    """Общая настройка диалогового окна: заголовок, фон, иконка, позиция, модальность."""
    window.title(title_text)
    window.configure(fg_color=BG)
    window.transient(parent)
    center_on(window, parent, width, height)
    if not resizable:
        window.resizable(False, False)
    icon_path = app_icon_path()
    if icon_path and sys.platform == "win32":
        # CTkToplevel через 200 мс ставит свою иконку, если мы не поставили раньше
        try:
            window.iconbitmap(icon_path)
        except Exception:
            pass
        window.after(250, lambda: _safe_iconbitmap(window, icon_path))
    if modal:
        window.after(100, lambda: _safe_grab(window))
    return window


def _safe_iconbitmap(window, path):
    try:
        if window.winfo_exists():
            window.iconbitmap(path)
    except Exception:
        pass


def _safe_grab(window):
    try:
        if window.winfo_exists():
            window.grab_set()
    except Exception:
        pass


def center_on(window, parent, width, height):
    """Ставит диалог по центру родительского окна (и не за край экрана)."""
    parent.update_idletasks()
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    width, height = min(width, sw - 40), min(height, sh - 80)
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    x = max(0, min(x, sw - width))
    y = max(0, min(y, sh - height - 40))
    window.geometry(f"{width}x{height}+{x}+{y}")


# ========== ИКОНКИ ==========
# Рисуются кодом через PIL (в 4× разрешении и затем уменьшаются) —
# так они чёткие, одного стиля и не зависят от шрифтов с эмодзи.
_icon_cache = {}


def _draw_icon(name, px, color):
    from PIL import Image, ImageDraw
    s = px * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(4, s // 12)

    if name == "barcode":
        x = s * 0.12
        for w in (1, 2, 1, 3, 1, 1, 2, 1, 2):
            bw = w * s * 0.03
            d.rectangle([x, s * 0.18, x + bw, s * 0.82], fill=color)
            x += bw + s * 0.045
    elif name == "qr":
        for cx, cy in ((0.12, 0.12), (0.58, 0.12), (0.12, 0.58)):
            d.rounded_rectangle([s * cx, s * cy, s * (cx + 0.30), s * (cy + 0.30)],
                                radius=s * 0.05, outline=color, width=lw)
            d.rectangle([s * (cx + 0.10), s * (cy + 0.10), s * (cx + 0.20), s * (cy + 0.20)],
                        fill=color)
        for cx, cy in ((0.60, 0.60), (0.60, 0.76), (0.76, 0.76)):
            d.rectangle([s * cx, s * cy, s * (cx + 0.12), s * (cy + 0.12)], fill=color)
    elif name == "template":
        d.rounded_rectangle([s * 0.12, s * 0.18, s * 0.88, s * 0.82],
                            radius=s * 0.08, outline=color, width=lw)
        d.rectangle([s * 0.25, s * 0.32, s * 0.45, s * 0.52], fill=color)
        d.line([s * 0.55, s * 0.36, s * 0.75, s * 0.36], fill=color, width=lw)
        d.line([s * 0.55, s * 0.50, s * 0.70, s * 0.50], fill=color, width=lw)
        d.line([s * 0.25, s * 0.66, s * 0.75, s * 0.66], fill=color, width=lw)
    elif name == "history":
        d.ellipse([s * 0.14, s * 0.14, s * 0.86, s * 0.86], outline=color, width=lw)
        d.line([s * 0.5, s * 0.30, s * 0.5, s * 0.52, s * 0.66, s * 0.62],
               fill=color, width=lw, joint="curve")
    elif name == "play":
        d.polygon([(s * 0.28, s * 0.18), (s * 0.28, s * 0.82), (s * 0.84, s * 0.5)], fill=color)
    elif name == "settings":
        c, r_out, r_in = s / 2, s * 0.40, s * 0.30
        pts = []
        for i in range(48):
            a = i / 48 * 2 * math.pi
            r = r_out if (i // 3) % 2 == 0 else r_in
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        d.polygon(pts, fill=color)
        d.ellipse([c - s * 0.13, c - s * 0.13, c + s * 0.13, c + s * 0.13], fill=(0, 0, 0, 0))
    elif name == "eye":
        d.ellipse([s * 0.08, s * 0.26, s * 0.92, s * 0.74], outline=color, width=lw)
        d.ellipse([s * 0.38, s * 0.38, s * 0.62, s * 0.62], fill=color)
    elif name == "plus":
        d.line([s * 0.5, s * 0.18, s * 0.5, s * 0.82], fill=color, width=lw + 2)
        d.line([s * 0.18, s * 0.5, s * 0.82, s * 0.5], fill=color, width=lw + 2)
    return img.resize((px, px), Image.LANCZOS)


def icon(name, size=20, color=TEXT):
    """CTkImage с иконкой нужного цвета (кэшируется)."""
    key = (name, size, color)
    if key not in _icon_cache:
        img = _draw_icon(name, size, color)
        _icon_cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    return _icon_cache[key]


# ========== ЛОГОТИП-МОЗАИКА ==========
# Фигура, собранная из разноцветных бутылок и пакетов (как пингвин
# на эко-плакатах), и зелёный знак переработки над ней.

def _item_sprite(w, color, kind):
    """Плоский силуэт одного предмета мусора шириной w px: без бликов
    и этикеток, только форма, у бутылок и стаканов — крышка темнее."""
    from PIL import Image, ImageDraw
    ratio = {"bottle": 2.6, "flask": 1.9, "jug": 1.25, "bag": 1.25,
             "cup": 1.35, "can": 1.7}[kind]
    h = max(4, int(w * ratio))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cap = _shade(color, 0.7)
    clear = (0, 0, 0, 0)

    if kind == "bottle":                       # бутылка с горлышком
        n = w * 0.34
        d.rectangle([w / 2 - n / 2, 0, w / 2 + n / 2, h * 0.08], fill=cap)
        d.rectangle([w / 2 - n / 2, h * 0.08, w / 2 + n / 2, h * 0.2], fill=color)
        d.polygon([(w / 2 - n / 2, h * 0.19), (w / 2 + n / 2, h * 0.19),
                   (w - 1, h * 0.36), (0, h * 0.36)], fill=color)
        d.rounded_rectangle([0, h * 0.34, w - 1, h - 1], radius=w * 0.22, fill=color)
    elif kind == "flask":                      # флакон моющего средства
        d.rectangle([w * 0.2, 0, w * 0.48, h * 0.12], fill=cap)
        d.rounded_rectangle([0, h * 0.1, w - 1, h - 1], radius=w * 0.3, fill=color)
    elif kind == "jug":                        # канистра с ручкой-прорезью
        d.rectangle([w * 0.62, 0, w * 0.86, h * 0.16], fill=cap)
        d.rounded_rectangle([0, h * 0.12, w - 1, h - 1], radius=w * 0.14, fill=color)
        d.rounded_rectangle([w * 0.12, h * 0.24, w * 0.46, h * 0.44], radius=w * 0.06, fill=clear)
    elif kind == "bag":                        # пакет-майка
        d.polygon([(0, h * 0.3), (w * 0.22, 0), (w * 0.36, 0), (w * 0.36, h * 0.24),
                   (w * 0.64, h * 0.24), (w * 0.64, 0), (w * 0.78, 0),
                   (w - 1, h * 0.3), (w * 0.94, h - 1), (w * 0.06, h - 1)], fill=color)
    elif kind == "cup":                        # стакан с крышкой
        d.rectangle([0, 0, w - 1, h * 0.12], fill=cap)
        d.polygon([(w * 0.04, h * 0.12), (w * 0.96, h * 0.12),
                   (w * 0.8, h - 1), (w * 0.2, h - 1)], fill=color)
    else:                                      # банка
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=w * 0.18, fill=color)
        d.rectangle([w * 0.1, h * 0.06, w * 0.9, h * 0.1], fill=cap)
    return img


def _shade(hex_color, k):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * k))) for c in (r, g, b))


def _drop_mask(s):
    """Сглаженная маска капли."""
    from PIL import Image, ImageDraw
    k = 2
    m = Image.new("L", (s * k, s * k), 0)
    d = ImageDraw.Draw(m)
    S = s * k
    cx, cy, r = S * 0.5, S * 0.64, S * 0.33
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    # Касательные из вершины к окружности — острый «носик» капли
    top = S * 0.04
    dist = cy - top
    ang = math.asin(r / dist)
    tx = r * math.cos(ang)
    ty = cy - r * math.sin(ang)
    d.polygon([(cx, top), (cx - tx, ty), (cx + tx, ty)], fill=255)
    return m.resize((s, s), Image.LANCZOS)


def _mosaic(s, seed=7, density=13, attempts=14000):
    """Капля, выложенная силуэтами мусора с зазорами между ними (как
    пингвин на эко-плакате). Предметы раскладываются от крупных к мелким
    и не касаются друг друга; край капли образуют сами предметы.
    density — сколько крупных предметов помещается по ширине."""
    from PIL import Image, ImageChops, ImageFilter, ImageStat
    rng = random.Random(seed)
    mask = _drop_mask(s)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    occupied = Image.new("L", (s, s), 0)       # занятое место вместе с зазором
    gap = max(1, round(s * 0.008))
    grow = ImageFilter.MaxFilter(2 * gap + 1)

    inside = [(x, y) for y in range(0, s, 2) for x in range(0, s, 2) if mask.getpixel((x, y)) > 200]
    kinds = ["bottle", "bottle", "bottle", "flask", "jug", "bag", "bag", "cup", "can"]
    w_max, w_min = s / density, s / (density * 4)

    for i in range(attempts):
        cx, cy = rng.choice(inside)
        if occupied.getpixel((cx, cy)):        # быстрый отказ: точка уже занята
            continue
        t = i / attempts
        w = int((w_max + (w_min - w_max) * t ** 0.5) * rng.uniform(0.85, 1.15))
        if w < 3:
            break
        sprite = _item_sprite(w, rng.choice(MOSAIC_COLORS), rng.choice(kinds))
        sprite = sprite.rotate(rng.uniform(0, 360), expand=True, resample=Image.BICUBIC)
        x0, y0 = int(cx - sprite.width / 2), int(cy - sprite.height / 2)
        if x0 < 0 or y0 < 0 or x0 + sprite.width > s or y0 + sprite.height > s:
            continue
        box = (x0, y0, x0 + sprite.width, y0 + sprite.height)
        alpha = sprite.getchannel("A")

        # Не налезать на соседей
        if ImageChops.multiply(occupied.crop(box), alpha).point(lambda v: 255 if v > 24 else 0).getbbox():
            continue
        # Почти целиком внутри капли (край образуют сами предметы)
        total = ImageStat.Stat(alpha).sum[0]
        within = ImageStat.Stat(ImageChops.multiply(mask.crop(box), alpha)).sum[0]
        if total == 0 or within / total < 0.9:
            continue

        img.alpha_composite(sprite, (x0, y0))
        occupied.paste(ImageChops.lighter(occupied.crop(box), alpha.filter(grow)), box)
    return img


def _recycle(s, color=GREEN):
    """Три стрелки по кругу — знак переработки."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, r, lw = s / 2, s * 0.30, s * 0.12
    shades = [color, _shade(color, 0.8), _shade(color, 1.18)]
    for i in range(3):
        start = i * 120 - 90 + 14
        end = start + 76
        # Дуга-«хвост» стрелки
        d.arc([c - r - lw / 2, c - r - lw / 2, c + r + lw / 2, c + r + lw / 2],
              start, end, fill=shades[i], width=int(lw))
        # Наконечник: основание поперёк дуги, острие — вперёд по касательной
        a = math.radians(end)
        ex, ey = c + r * math.cos(a), c + r * math.sin(a)
        tx, ty = -math.sin(a), math.cos(a)          # касательная (по часовой)
        nx, ny = math.cos(a), math.sin(a)           # нормаль (от центра)
        half = lw * 1.05
        tip = (ex + tx * lw * 1.5, ey + ty * lw * 1.5)
        d.polygon([(ex + nx * half, ey + ny * half), tip, (ex - nx * half, ey - ny * half)],
                  fill=shades[i])
    return img


_art_cache = {}
ART_VERSION = 2  # увеличить при изменении рисования мозаики — старый кэш не подхватится


def _cached_art(name, render):
    """Мозаика раскладывается ~1–2 с, поэтому готовая картинка один раз
    сохраняется в папку данных приложения и дальше берётся оттуда."""
    from PIL import Image
    try:
        from settings import APP_DATA_PATH
        path = os.path.join(APP_DATA_PATH, "cache", f"{name}_v{ART_VERSION}.png")
    except Exception:
        path = None
    if path and os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    img = render()
    if path:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            img.save(path)
        except Exception:
            pass
    return img


def logo_image(size=40):
    """Маленький логотип для сайдбара: капля-мозаика."""
    key = ("logo", size)
    if key not in _art_cache:
        from PIL import Image

        def render():
            # В маленьком размере — меньше и крупнее предметы, иначе получится шум
            big = _mosaic(size * 6, seed=3, density=6, attempts=5000)
            return big.resize((size, size), Image.LANCZOS)

        img = _cached_art(f"logo_{size}", render)
        _art_cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    return _art_cache[key]


def drop_logo_pil(size=256):
    """Капля-мозаика картинкой PIL — для центра QR-кода."""
    return _cached_art(f"qrlogo_{size}",
                       lambda: _mosaic(size, seed=3, density=6, attempts=5000))


def eco_illustration(width=150):
    """Знак переработки над каплей из мусора — для пустых состояний."""
    key = ("eco", width)
    if key not in _art_cache:
        from PIL import Image

        def render():
            k = 4
            s = width * k
            recycle_s = int(s * 0.42)
            canvas = Image.new("RGBA", (s, s + recycle_s), (0, 0, 0, 0))
            canvas.alpha_composite(_recycle(recycle_s), ((s - recycle_s) // 2, 0))
            canvas.alpha_composite(_mosaic(s, seed=11), (0, recycle_s))
            return canvas.resize((width, (s + recycle_s) // k), Image.LANCZOS)

        img = _cached_art(f"eco_{width}", render)
        _art_cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
    return _art_cache[key]


# ========== ГОТОВЫЕ ВИДЖЕТЫ ==========
_BUTTON_STYLES = {
    # fg, hover, text
    "primary": (GREEN, GREEN_HOVER, ON_ACCENT),       # «СТАРТ»
    "blue": (BLUE, BLUE_HOVER, ON_ACCENT),            # «ОЗОН»
    "inverse": (NAVY, NAVY_HOVER, ON_ACCENT),
    "secondary": (SURFACE_2, SURFACE_HOVER, TEXT),
    "ghost": ("transparent", SURFACE_2, TEXT_2),
    "danger": (ERROR_BG, ERROR_HOVER, RED),          # «СТОП»
}
_LOUD = ("primary", "blue", "inverse")


def button(parent, text, command=None, variant="secondary", height=40, width=0,
           icon_name=None, **kwargs):
    """Кнопка-«таблетка». variant: primary | blue | inverse | secondary | ghost | danger.
    Яркие кнопки подписаны КАПСОМ, как на панели автомата."""
    fg, hover, tc = _BUTTON_STYLES[variant]
    loud = variant in _LOUD
    weight = "extrabold" if loud else "semibold"
    size = kwargs.pop("font_size", 14 if height >= 44 else 13)
    if loud:
        text = text.upper()
    if icon_name:
        kwargs["image"] = icon(icon_name, 18 if height >= 44 else 16, tc)
        kwargs.setdefault("compound", "left")
        text = f" {text}" if text else ""
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=fg, hover_color=hover, text_color=tc,
        height=height, width=width, corner_radius=height // 2,
        font=font(size, weight), **kwargs,
    )


def icon_button(parent, icon_name, command=None, size=40, variant="secondary", tooltip=None):
    """Круглая кнопка с одной иконкой."""
    fg, hover, tc = _BUTTON_STYLES[variant]
    btn = ctk.CTkButton(
        parent, text="", command=command, image=icon(icon_name, size // 2 - 2, tc),
        fg_color=fg, hover_color=hover, width=size, height=size, corner_radius=size // 2,
    )
    if tooltip:
        Tooltip(btn, tooltip)
    return btn


def card(parent, **kwargs):
    kwargs.setdefault("fg_color", SURFACE)
    kwargs.setdefault("corner_radius", 16)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("border_color", BORDER)
    return ctk.CTkFrame(parent, **kwargs)


def entry(parent, variable=None, placeholder=None, width=140, height=40, **kwargs):
    return ctk.CTkEntry(
        parent, textvariable=variable, placeholder_text=placeholder,
        width=width, height=height, font=font(13), **kwargs,
    )


def option_menu(parent, values, variable=None, command=None, width=160, height=40):
    return ctk.CTkOptionMenu(
        parent, values=values, variable=variable, command=command,
        width=width, height=height, font=font(13, "semibold"), dropdown_font=font(13),
        dynamic_resizing=False,
    )


def segmented(parent, values, variable=None, command=None, height=36):
    """Переключатель-сегменты: выбранный сегмент — синий с белым текстом."""
    seg = None

    def on_change(value):
        _paint_segments(seg)
        if command:
            command(value)

    seg = ctk.CTkSegmentedButton(
        parent, values=values, variable=variable, command=on_change,
        height=height, font=font(13, "bold"), text_color=TEXT,
    )
    if variable is not None:
        variable.trace_add("write", lambda *_: seg.after_idle(lambda: _paint_segments(seg)))
    _paint_segments(seg)
    return seg


def _paint_segments(seg):
    """У CTkSegmentedButton один text_color на все сегменты — красим текст
    выбранного сегмента в белый вручную."""
    try:
        current = str(seg.get())
        for value, btn in seg._buttons_dict.items():
            btn.configure(text_color=ON_ACCENT if str(value) == current else TEXT)
    except Exception:
        pass


def switch(parent, text, variable, command=None):
    return ctk.CTkSwitch(
        parent, text=text, variable=variable, onvalue=True, offvalue=False,
        command=command, font=font(13), switch_width=42, switch_height=22,
    )


def label(parent, text, size=13, weight="normal", color=TEXT, **kwargs):
    return ctk.CTkLabel(parent, text=text, text_color=color,
                        font=font(size, weight), **kwargs)


def overline(parent, text, color=BLUE):
    """Маленькая надпись капсом над заголовком («ШТРИХКОДЫ»)."""
    return label(parent, text.upper(), size=12, weight="extrabold", color=color)


def title(parent, text, size=30):
    """Главный заголовок экрана — КАПСОМ, самым жирным начертанием."""
    return label(parent, text.upper(), size=size, weight="black")


def field_label(parent, text):
    return label(parent, text, size=12, weight="semibold", color=TEXT_2)


def section_title(parent, text):
    return label(parent, text.upper(), size=15, weight="extrabold")


def step_badge(parent, number, size=30, color=ROYAL):
    """Номер шага в синем квадрате — как в «Инструкции» на панели."""
    return ctk.CTkLabel(parent, text=str(number), width=size, height=size,
                        fg_color=color, corner_radius=7, text_color=ON_ACCENT,
                        font=font(int(size * 0.55), "black"))


def step_title(parent, number, text, size=14):
    """Строка «[1] ЗАГОЛОВОК ШАГА»."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    step_badge(row, number, size=int(size * 1.9)).pack(side="left")
    label(row, text.upper(), size=size, weight="extrabold").pack(side="left", padx=(10, 0))
    return row


def chip(parent, text, strong=False):
    """Плашка-«таблетка» для сводки: синяя (strong) или светло-голубая."""
    return ctk.CTkLabel(
        parent, text=text, height=28, corner_radius=14,
        fg_color=BLUE if strong else BLUE_SOFT,
        text_color=ON_ACCENT if strong else ROYAL,
        font=font(12, "extrabold"), padx=12,
    )


def bind_hover(frame, normal, hover):
    """Подсветка строки списка при наведении (учитывает дочерние виджеты)."""
    def on_enter(_e):
        frame.configure(fg_color=hover)

    def on_leave(_e):
        x, y = frame.winfo_pointerxy()
        w = frame.winfo_containing(x, y)
        while w is not None:
            if w == frame:
                return
            w = getattr(w, "master", None)
        frame.configure(fg_color=normal)

    def bind_all(w):
        w.bind("<Enter>", on_enter, add="+")
        w.bind("<Leave>", on_leave, add="+")
        for child in w.winfo_children():
            bind_all(child)

    bind_all(frame)


class Tooltip:
    """Всплывающая подсказка в цветах темы."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, justify="left",
                 bg=NAVY, fg="#FFFFFF", padx=10, pady=6,
                 font=(_WEIGHTS["normal"][0], 10)).pack()

    def hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None
