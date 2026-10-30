# settings.py - Управление настройками и историей

import os
import sys
import json
from datetime import datetime

# ========== ПУТЬ К ДАННЫМ ==========
def get_app_data_path():
    """Получение пути для хранения данных приложения"""
    if os.name == 'nt':  # Windows
        app_data = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'barcodeGen')
    elif sys.platform == 'darwin':  # macOS
        app_data = os.path.join(os.path.expanduser('~/Library/Application Support'), 'barcodeGen')
    else:  # Linux и прочие
        app_data = os.path.join(os.path.expanduser('~/.config'), 'barcodeGen')

    os.makedirs(app_data, exist_ok=True)
    return app_data


APP_DATA_PATH = get_app_data_path()

SETTINGS_FILE = os.path.join(APP_DATA_PATH, "barcode_settings.json")
HISTORY_FILE = os.path.join(APP_DATA_PATH, "barcode_history.json")
RECENT_FILES_FILE = os.path.join(APP_DATA_PATH, "recent_files.json")
TEMP_CODES_FILE = os.path.join(APP_DATA_PATH, "temp_codes_backup.txt")


# ========== ЛОГГЕР (безопасный импорт) ==========
# logger.py лениво импортирует settings внутри своей функции _get_log_dir(),
# поэтому здесь циклического импорта не будет. Если по какой-то причине
# logger недоступен - работаем без логирования, но не падаем.
try:
    from logger import logger
except Exception:
    class _DummyLogger:
        def info(self, *a, **k): pass
        def error(self, *a, **k): pass
        def warning(self, *a, **k): pass
        def debug(self, *a, **k): pass
    logger = _DummyLogger()


def _write_atomic(path, text):
    """Запись через временный файл и os.replace: если программа упадёт
    посреди записи, старый файл останется целым."""
    tmp = f"{path}.tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _write_json(path, data):
    _write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2))


class SettingsManager:
    """Класс для управления настройками приложения"""

    def __init__(self):
        self.settings = {}
        self.history = []
        self.recent_files = []
        self.load_all()

    def load_all(self):
        """Загрузка всех данных"""
        self.load_settings()
        self.load_history()
        self.load_recent_files()

    # ===== Настройки =====
    def load_settings(self):
        """Загрузка настроек из файла"""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                if not isinstance(self.settings, dict):
                    raise ValueError("ожидался JSON-объект")

                # Миграция старых ключей в новые
                self._migrate_old_settings()

                # Ключи, появившиеся в новых версиях, — со значениями по умолчанию
                for key, value in self.get_default_settings().items():
                    self.settings.setdefault(key, value)

                logger.info(f"✅ Настройки загружены из {SETTINGS_FILE}")
            except Exception as e:
                logger.error(f"Ошибка загрузки настроек: {e}")
                # Повреждённый файл сохраняем для разбора и стартуем с умолчаний
                try:
                    os.replace(SETTINGS_FILE, f"{SETTINGS_FILE}.broken")
                    logger.warning(f"Повреждённые настройки сохранены в {SETTINGS_FILE}.broken")
                except OSError:
                    pass
                self.settings = self.get_default_settings()
        else:
            self.settings = self.get_default_settings()
            logger.info("Настройки по умолчанию (файла ещё нет)")

    def _migrate_old_settings(self):
        """Мигрирует плоские ключи в новые раздельные ключи barcode_* / qr_*."""
        legacy_keys = {
            "label_width": ("barcode_label_width", "qr_label_width"),
            "label_height": ("barcode_label_height", "qr_label_height"),
            "margin_top": ("barcode_margin_top", "qr_margin_top"),
            "margin_bottom": ("barcode_margin_bottom", "qr_margin_bottom"),
            "margin_left": ("barcode_margin_left", "qr_margin_left"),
            "margin_right": ("barcode_margin_right", "qr_margin_right"),
            "show_border": ("barcode_show_border", "qr_show_border"),
        }
        changed = False
        for old_key, new_keys in legacy_keys.items():
            if old_key in self.settings:
                val = self.settings[old_key]
                for nk in new_keys:
                    if nk not in self.settings:
                        self.settings[nk] = val
                        changed = True
                del self.settings[old_key]

        # Дополнительно
        if "labels_per_page" in self.settings and "barcode_labels_per_page" not in self.settings:
            self.settings["barcode_labels_per_page"] = self.settings["labels_per_page"]
            del self.settings["labels_per_page"]
            changed = True
        if "selected_only" in self.settings and "barcode_selected_only" not in self.settings:
            self.settings["barcode_selected_only"] = self.settings["selected_only"]
            del self.settings["selected_only"]
            changed = True
        if "batch_mode" in self.settings and "barcode_batch_mode" not in self.settings:
            self.settings["barcode_batch_mode"] = self.settings["batch_mode"]
            del self.settings["batch_mode"]
            changed = True
        if "use_template" in self.settings and "barcode_use_template" not in self.settings:
            self.settings["barcode_use_template"] = self.settings["use_template"]
            del self.settings["use_template"]
            changed = True

        if changed:
            self.save_settings(self.settings)
            logger.info("✅ Миграция настроек выполнена")

    def save_settings(self, settings_dict):
        """Сохранение настроек"""
        try:
            _write_json(SETTINGS_FILE, settings_dict)
            self.settings = settings_dict
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}")

    def get_default_settings(self):
        """Настройки по умолчанию, разделённые на два модуля."""
        return {
            # ===== Общие =====
            "selected_preset": "58×40 мм (стандарт для чеков)",
            "codes_metadata": {},
            "label_templates": {},
            "current_template": "",

            # ===== Модуль «Штрихкоды» =====
            "barcode_type": "code128",
            "barcode_dpi": "600",
            "barcode_label_width": "58",
            "barcode_label_height": "40",
            "barcode_margin_top": "5",
            "barcode_margin_bottom": "5",
            "barcode_margin_left": "5",
            "barcode_margin_right": "5",
            "barcode_labels_per_page": 1,
            "barcode_show_border": False,
            "barcode_selected_only": False,
            "barcode_batch_mode": False,
            "barcode_use_template": True,
            "barcode_show_text": True,
            "barcode_font_family": "Montserrat",

            # ===== Модуль «QR-паспорта» =====
            "qr_label_width": "58",
            "qr_label_height": "40",
            "qr_margin_top": "5",
            "qr_margin_bottom": "5",
            "qr_margin_left": "5",
            "qr_margin_right": "5",
            "qr_show_border": False,
            "qr_box_size": "8",
            "qr_format": "text",
            "qr_logo": "none",          # none | drop | путь к своей картинке
            "qr_records": [],

            # ===== Совместимость (устаревшие ключи) =====
            "use_qr": False,
        }

    def get(self, key, default=None):
        """Получение значения настройки"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Установка значения настройки"""
        self.settings[key] = value
        self.save_settings(self.settings)

    def update(self, values):
        """Установка нескольких значений с одной записью на диск."""
        self.settings.update(values)
        self.save_settings(self.settings)

    # ===== История =====
    def load_history(self):
        """Загрузка истории"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки истории: {e}")
                self.history = []

    def add_history(self, filename, codes_count, barcode_type, label_size):
        """Добавление записи в историю"""
        self.history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "codes_count": codes_count,
            "file": os.path.basename(filename),
            "barcode_type": barcode_type,
            "label_size": label_size
        })
        self.history = self.history[-50:]

        try:
            _write_json(HISTORY_FILE, self.history)
            logger.info(f"📝 История: добавлена запись {os.path.basename(filename)} ({codes_count} кодов)")
        except Exception as e:
            logger.error(f"Ошибка сохранения истории: {e}")

    def get_history(self):
        """Получение истории"""
        return self.history

    # ===== Недавние файлы =====
    def load_recent_files(self):
        """Загрузка списка недавних файлов"""
        if os.path.exists(RECENT_FILES_FILE):
            try:
                with open(RECENT_FILES_FILE, 'r', encoding='utf-8') as f:
                    self.recent_files = json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки недавних файлов: {e}")
                self.recent_files = []

    def add_recent_file(self, filename):
        """Добавление файла в список недавних"""
        if filename in self.recent_files:
            self.recent_files.remove(filename)
        self.recent_files.insert(0, filename)
        self.recent_files = self.recent_files[:10]

        try:
            _write_json(RECENT_FILES_FILE, self.recent_files)
        except Exception as e:
            logger.error(f"Ошибка сохранения недавних файлов: {e}")

    def get_recent_files(self):
        """Получение списка недавних файлов"""
        return self.recent_files

    # ===== Автосохранение =====
    def save_temp_codes(self, text):
        """Сохранение временных кодов"""
        try:
            _write_atomic(TEMP_CODES_FILE, text)
            return True
        except Exception as e:
            logger.error(f"Ошибка автосохранения кодов: {e}")
            return False

    def load_temp_codes(self):
        """Загрузка временных кодов"""
        if os.path.exists(TEMP_CODES_FILE):
            try:
                with open(TEMP_CODES_FILE, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Ошибка загрузки автосохранения: {e}")
                return None
        return None

    def clear_temp_codes(self):
        """Очистка временных кодов"""
        try:
            if os.path.exists(TEMP_CODES_FILE):
                os.remove(TEMP_CODES_FILE)
            return True
        except Exception as e:
            logger.error(f"Ошибка очистки автосохранения: {e}")
            return False