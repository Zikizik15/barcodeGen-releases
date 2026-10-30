# tests/test_settings.py — Unit-тесты для settings.py (на временных файлах)

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import settings
from settings import SettingsManager


@pytest.fixture
def files(tmp_path, monkeypatch):
    """Перенаправляет все файлы настроек во временную папку."""
    paths = {
        "SETTINGS_FILE": tmp_path / "barcode_settings.json",
        "HISTORY_FILE": tmp_path / "barcode_history.json",
        "RECENT_FILES_FILE": tmp_path / "recent_files.json",
        "TEMP_CODES_FILE": tmp_path / "temp_codes_backup.txt",
    }
    for name, path in paths.items():
        monkeypatch.setattr(settings, name, str(path))
    return paths


class TestLoad:
    def test_corrupted_file_falls_back_to_defaults(self, files):
        files["SETTINGS_FILE"].write_text("{ это не json", encoding="utf-8")
        sm = SettingsManager()
        assert sm.get("barcode_type") == "code128"
        assert sm.get("barcode_label_width") == "58"
        # Повреждённый файл сохранён для разбора
        assert files["SETTINGS_FILE"].with_name("barcode_settings.json.broken").exists()

    def test_not_an_object_falls_back_to_defaults(self, files):
        files["SETTINGS_FILE"].write_text("[1, 2, 3]", encoding="utf-8")
        assert SettingsManager().get("barcode_dpi") == "600"

    def test_missing_keys_filled_with_defaults(self, files):
        files["SETTINGS_FILE"].write_text(json.dumps({"barcode_type": "ean13"}), encoding="utf-8")
        sm = SettingsManager()
        assert sm.get("barcode_type") == "ean13"          # своё значение сохранено
        assert sm.get("barcode_show_text") is True         # новый ключ — по умолчанию

    def test_font_family_default(self, files):
        """У нового ключа barcode_font_family есть значение по умолчанию."""
        files["SETTINGS_FILE"].write_text("{}", encoding="utf-8")
        sm = SettingsManager()
        from utils import BARCODE_FONT_DEFAULT
        assert sm.get("barcode_font_family") == BARCODE_FONT_DEFAULT


class TestSave:
    def test_update_writes_once(self, files, monkeypatch):
        sm = SettingsManager()
        writes = []
        real = settings._write_json
        monkeypatch.setattr(settings, "_write_json", lambda p, d: (writes.append(p), real(p, d)))
        sm.update({"barcode_type": "code39", "barcode_dpi": "1200", "qr_format": "json"})
        assert len(writes) == 1
        saved = json.loads(files["SETTINGS_FILE"].read_text(encoding="utf-8"))
        assert (saved["barcode_type"], saved["barcode_dpi"], saved["qr_format"]) == ("code39", "1200", "json")

    def test_no_tmp_file_left(self, files):
        SettingsManager().set("barcode_type", "itf")
        assert not files["SETTINGS_FILE"].with_name("barcode_settings.json.tmp").exists()

    def test_failed_write_keeps_old_file(self, files, monkeypatch):
        sm = SettingsManager()
        sm.set("barcode_type", "code39")

        def broken_replace(src, dst):
            raise OSError("диск отвалился")
        monkeypatch.setattr(settings.os, "replace", broken_replace)
        sm.set("barcode_type", "ean8")   # ошибка логируется, исключение не летит
        saved = json.loads(files["SETTINGS_FILE"].read_text(encoding="utf-8"))
        assert saved["barcode_type"] == "code39"

    def test_history_and_temp_codes(self, files):
        sm = SettingsManager()
        sm.add_history("a.pdf", 3, "code128", "58×40")
        assert json.loads(files["HISTORY_FILE"].read_text(encoding="utf-8"))[0]["codes_count"] == 3
        assert sm.save_temp_codes("ABC\nDEF")
        assert sm.load_temp_codes() == "ABC\nDEF"
