# main.py - Точка входа в приложение

import tkinter as tk
from tkinter import messagebox
import sys
import os
import traceback

# Определяем платформу
IS_WINDOWS = sys.platform == 'win32'
IS_MAC = sys.platform == 'darwin'
IS_LINUX = sys.platform.startswith('linux')


# ========== ФИКС ПУТЕЙ ДО ВСЕХ ИМПОРТОВ ==========
# 1) Папка, где лежит сам main.py (абсолютный путь)
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# 2) Папка проекта — первой; системные site-packages — только в конец списка,
#    как запасной вариант. Если поставить их первыми, они перекроют пакеты
#    из venv, и подхватится не та версия Pillow/reportlab.
sys.path.insert(0, application_path)

try:
    import site
    extra_paths = []

    user_site = site.getusersitepackages()
    if user_site:
        extra_paths.append(user_site)

    try:
        extra_paths.extend(site.getsitepackages())
    except Exception:
        pass

    # Типовые пути Debian/Ubuntu/Mint
    extra_paths.extend([
        "/usr/lib/python3/dist-packages",
        "/usr/local/lib/python3/dist-packages",
    ])

    for p in extra_paths:
        if p and os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)
except Exception:
    pass

# 3) ВАЖНО: не делаем os.chdir(APP_DATA_PATH).
#    Все пути в settings.py уже абсолютные, chdir не нужен,
#    а он ломал импорты при запуске относительным путём.

# ========== ИМПОРТ ЛОГГЕРА ==========
from logger import logger

from version import __version__, APP_NAME

# ========== ПУТЬ К ДАННЫМ (для логов и сообщений об ошибках) ==========
from settings import APP_DATA_PATH

# ========== ИМПОРТ ПРИЛОЖЕНИЯ ==========
try:
    from gui import BarcodeApp
except ImportError:
    sys.path.insert(0, os.path.dirname(application_path))
    from gui import BarcodeApp


# ========== ГЛОБАЛЬНАЯ ОБРАБОТКА ОШИБОК ==========
def exception_handler(exc_type, exc_value, exc_traceback):
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.error(f"НЕОБРАБОТАННАЯ ОШИБКА:\n{error_msg}")

    try:
        root = tk._default_root
        if root and root.winfo_exists():
            messagebox.showerror(
                "Критическая ошибка",
                f"Произошла критическая ошибка:\n\n{exc_type.__name__}: {exc_value}\n\n"
                f"Ошибка записана в лог: {os.path.join(APP_DATA_PATH, 'barcode_app.log')}"
            )
    except Exception:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {exc_type.__name__}: {exc_value}")
        print(error_msg)


sys.excepthook = exception_handler


# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    logger.info("=" * 60)
    logger.info(f"🚀 ЗАПУСК ПРИЛОЖЕНИЯ {APP_NAME} {__version__}")
    logger.info(f"Платформа: {sys.platform}")
    logger.info(f"Путь: {application_path}")
    logger.info(f"Данные: {APP_DATA_PATH}")
    logger.info("=" * 60)

    try:
        # Drag & Drop (опционально)
        try:
            from tkinterdnd2 import TkinterDnD
            root = TkinterDnD.Tk()
            logger.info("✅ Drag & Drop поддержка включена")
        except ImportError:
            root = tk.Tk()
            logger.warning("⚠️ Drag & Drop не поддерживается")
            if not IS_WINDOWS:
                print("Для поддержки Drag & Drop установите: pip install tkinterdnd2")

        # ========== Иконка окна ==========
        try:
            from PIL import Image, ImageTk

            # Для frozen exe ресурсы в sys._MEIPASS, для исходников — рядом с main.py
            if getattr(sys, 'frozen', False):
                resource_path = getattr(sys, '_MEIPASS', application_path)
            else:
                resource_path = application_path

            ico_path = os.path.join(resource_path, "logo.ico")
            png_path = os.path.join(resource_path, "logo.png")

            if IS_WINDOWS and os.path.exists(ico_path):
                root.iconbitmap(ico_path)
                logger.info(f"✅ Иконка окна установлена (.ico): {ico_path}")
            elif os.path.exists(png_path):
                icon_img = Image.open(png_path).convert("RGBA")
                icon_photo = ImageTk.PhotoImage(icon_img)
                root.iconphoto(True, icon_photo)
                root._icon_photo = icon_photo
                logger.info(f"✅ Иконка окна установлена (.png): {png_path}")
            else:
                logger.warning(f"⚠️ logo.ico / logo.png не найдены в {resource_path}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось установить иконку окна: {e}")

        # ========== Запуск GUI ==========
        app = BarcodeApp(root)  # noqa: F841 — держим ссылку на главное окно
        logger.info("✅ Приложение успешно создано")

        root.mainloop()

        logger.info("🛑 ПРИЛОЖЕНИЕ ЗАВЕРШЕНО")
        logger.info("=" * 60)

    except Exception as e:
        error_msg = traceback.format_exc()
        logger.error(f"ОШИБКА В MAIN:\n{error_msg}")
        try:
            messagebox.showerror(
                "Ошибка запуска",
                f"Не удалось запустить приложение:\n\n{str(e)}\n\n"
                f"Ошибка записана в лог: {os.path.join(APP_DATA_PATH, 'barcode_app.log')}"
            )
        except Exception:
            print(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
