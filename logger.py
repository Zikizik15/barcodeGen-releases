# logger.py - Единый модуль логирования для всего приложения
#
# Использование:
#   from logger import logger
#   logger.info("сообщение")
#   logger.error("ошибка")

import os
import sys
import logging
from datetime import datetime


def _get_log_dir():
    """Возвращает папку для лога - ту же, где приложение хранит настройки.

    Специально импортируется лениво (внутри функции), чтобы не создать
    циклический импорт: logger импортируется и из main.py, и из gui,
    и из settings.py."""
    try:
        from settings import APP_DATA_PATH
        return APP_DATA_PATH
    except Exception:
        # Fallback, если settings ещё не загрузился или недоступен
        if sys.platform == "win32":
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
        elif sys.platform == "darwin":
            base = os.path.expanduser('~/Library/Application Support')
        else:
            base = os.path.expanduser('~/.config')
        path = os.path.join(base, 'barcodeGen')
        os.makedirs(path, exist_ok=True)
        return path


class Logger:
    """Синглтон-логгер: один файл, один обработчик на всё приложение."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.log_dir = _get_log_dir()
        self.log_file = os.path.join(self.log_dir, "barcode_app.log")
        self.max_size = 1024 * 1024  # 1 MB

        # Ротация: если файл больше лимита - переименовываем в .old
        if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > self.max_size:
            backup = f"{self.log_file}.old"
            try:
                if os.path.exists(backup):
                    os.remove(backup)
                os.rename(self.log_file, backup)
            except OSError:
                pass

        # Настраиваем logging
        self.logger = logging.getLogger('BarcodeGen')
        self.logger.setLevel(logging.DEBUG)

        # Чистим старые обработчики (на случай повторной инициализации)
        if self.logger.handlers:
            for h in list(self.logger.handlers):
                self.logger.removeHandler(h)

        formatter = logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )

        # Файл
        try:
            fh = logging.FileHandler(self.log_file, encoding='utf-8')
            fh.setFormatter(formatter)
            fh.setLevel(logging.DEBUG)
            self.logger.addHandler(fh)
        except OSError:
            pass

        # Консоль (может не работать в --windowed exe, это нормально)
        try:
            sh = logging.StreamHandler()
            sh.setFormatter(formatter)
            sh.setLevel(logging.INFO)
            self.logger.addHandler(sh)
        except Exception:
            pass

        # Не засоряем лог шумом сторонних библиотек
        logging.getLogger('PIL').setLevel(logging.WARNING)
        logging.getLogger('barcode').setLevel(logging.WARNING)
        logging.getLogger('matplotlib').setLevel(logging.WARNING)

    # ---- короткие обёртки ----
    def info(self, msg):
        self.logger.info(msg)

    def error(self, msg):
        self.logger.error(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def debug(self, msg):
        self.logger.debug(msg)


# Единый экземпляр на всё приложение
logger = Logger()