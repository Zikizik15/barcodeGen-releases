# tests/test_updater.py — проверка и загрузка обновлений (на локальных файлах)

import hashlib
import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import updater
from updater import UpdateError


def _write_release(tmp_path, version="9.9.9", payload=b"installer bytes" * 1000, sha=None):
    """Имитация релиза: установщик и latest.json в папке (как сетевая папка)."""
    setup = tmp_path / f"barcodeGen-{version}-setup.exe"
    setup.write_bytes(payload)
    manifest = {"version": version, "url": str(setup),
                "sha256": sha or hashlib.sha256(payload).hexdigest(), "notes": "Новое"}
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return str(path), setup


class TestVersions:
    def test_numeric_compare(self):
        assert updater.is_newer("6.10.0", "6.9.9")      # строками было бы наоборот
        assert not updater.is_newer("6.4.0", "6.4.0")
        assert not updater.is_newer("6.3.9", "6.4.0")
        assert updater.is_newer("v7.0.0", "6.99.99")

    def test_bad_version(self):
        with pytest.raises(UpdateError):
            updater.parse_version("шесть")


class TestManifest:
    def test_newer_found(self, tmp_path):
        source, _ = _write_release(tmp_path, "9.9.9")
        assert updater.check_for_update("6.4.0", source)["version"] == "9.9.9"

    def test_same_version_no_update(self, tmp_path):
        source, _ = _write_release(tmp_path, "6.4.0")
        assert updater.check_for_update("6.4.0", source) is None

    def test_missing_field(self, tmp_path):
        p = tmp_path / "latest.json"
        p.write_text(json.dumps({"version": "9.0.0", "url": "x"}), encoding="utf-8")
        with pytest.raises(UpdateError, match="sha256"):
            updater.fetch_manifest(str(p))

    def test_unreachable_source(self, tmp_path):
        with pytest.raises(UpdateError):
            updater.fetch_manifest(str(tmp_path / "нет-такого.json"))

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("BARCODEGEN_UPDATE_URL", r"\\server\share\latest.json")
        assert updater.manifest_url() == r"\\server\share\latest.json"


class TestDownload:
    def test_download_and_verify(self, tmp_path):
        source, setup = _write_release(tmp_path)
        seen = []
        path = updater.download(updater.fetch_manifest(source), progress=lambda d, t: seen.append((d, t)),
                                dest_dir=str(tmp_path / "dl"))
        assert open(path, "rb").read() == setup.read_bytes()
        assert seen[-1][0] == seen[-1][1] == setup.stat().st_size

    def test_wrong_checksum_rejected(self, tmp_path):
        source, _ = _write_release(tmp_path, sha="0" * 64)
        dest = tmp_path / "dl"
        dest.mkdir()
        with pytest.raises(UpdateError, match="повреждён"):
            updater.download(updater.fetch_manifest(source), dest_dir=str(dest))
        assert not list(dest.iterdir())        # битый файл удалён

    def test_cancel(self, tmp_path):
        source, _ = _write_release(tmp_path)
        cancel = threading.Event()
        cancel.set()
        with pytest.raises(UpdateError, match="отменена"):
            updater.download(updater.fetch_manifest(source), cancel=cancel, dest_dir=str(tmp_path))


def test_install_command_relaunches():
    cmd = updater.install_command(r"C:\tmp\setup.exe")
    assert cmd[0] == r"C:\tmp\setup.exe" and "/SILENT" in cmd and "/UPDATE=1" in cmd


def test_source_run_cannot_self_update():
    assert updater.can_self_update() is False   # запуск из исходников — не установленная программа
