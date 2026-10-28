# updater.py - Проверка и установка обновлений
#
# Как это устроено:
#   1. В публичном репозитории RELEASES_REPO на GitHub в каждом релизе лежат
#      установщик и latest.json (его готовит publish_update.py):
#        {"version": "6.5.0",
#         "url": "https://github.com/.../barcodeGen-6.5.0-setup.exe",
#         "sha256": "…", "notes": "Что нового…"}
#   2. Программа скачивает latest.json по ссылке «последний релиз», сравнивает
#      версию со своей и предлагает обновиться.
#   3. Установщик скачивается во временную папку, проверяется по SHA-256
#      и запускается тихо с ключом /UPDATE=1 — после установки он сам
#      запускает программу снова (см. installer.iss).
#
# Источник можно переопределить переменной окружения BARCODEGEN_UPDATE_URL
# (ссылка или путь к latest.json, в том числе в сетевой папке) — удобно для
# проверки обновлений и для офисов без интернета.

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

# Публичный репозиторий только с установщиками (исходный код — в приватном)
RELEASES_REPO = "Zikizik15/barcodeGen-releases"
MANIFEST_URL = f"https://github.com/{RELEASES_REPO}/releases/latest/download/latest.json"

TIMEOUT = 15            # секунд на соединение
CHUNK = 64 * 1024


class UpdateError(Exception):
    """Понятная пользователю ошибка обновления."""


class NoReleases(UpdateError):
    """Ни одного обновления ещё не опубликовано — это не ошибка."""


def _human_error(e):
    """Сетевые ошибки — понятным языком."""
    if isinstance(e, urllib.error.HTTPError):
        return f"сервер ответил ошибкой {e.code}"
    if isinstance(e, (urllib.error.URLError, TimeoutError, ConnectionError)):
        return "нет связи с сервером обновлений — проверьте интернет"
    if isinstance(e, FileNotFoundError):
        return "файл не найден"
    return str(e)


def manifest_url():
    return os.environ.get("BARCODEGEN_UPDATE_URL") or MANIFEST_URL


def parse_version(text):
    """«6.10.2» → (6, 10, 2). Сравнение по числам, а не по строкам."""
    try:
        return tuple(int(part) for part in str(text).strip().lstrip("vV").split("."))
    except ValueError:
        raise UpdateError(f"Непонятный номер версии: {text!r}")


def is_newer(remote, local):
    return parse_version(remote) > parse_version(local)


def _open(source):
    """Поток для чтения по ссылке http(s) или из файла (в т.ч. сетевой папки)."""
    if source.lower().startswith(("http://", "https://")):
        request = urllib.request.Request(source, headers={"User-Agent": "barcodeGen-updater"})
        return urllib.request.urlopen(request, timeout=TIMEOUT)
    return open(source, "rb")


def fetch_manifest(source=None):
    """Скачивает и проверяет latest.json."""
    source = source or manifest_url()
    try:
        with _open(source) as f:
            data = json.loads(f.read().decode("utf-8-sig"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # В репозитории ещё нет ни одного релиза с latest.json
            raise NoReleases("Обновлений пока не публиковали")
        raise UpdateError(f"Не удалось проверить обновления: {_human_error(e)}")
    except ValueError:
        raise UpdateError("Описание обновления повреждено (latest.json)")
    except Exception as e:
        raise UpdateError(f"Не удалось проверить обновления: {_human_error(e)}")
    for key in ("version", "url", "sha256"):
        if not data.get(key):
            raise UpdateError(f"В описании обновления нет поля «{key}»")
    parse_version(data["version"])
    data.setdefault("notes", "")
    return data


def check_for_update(current_version, source=None):
    """Манифест, если есть версия новее текущей, иначе None."""
    try:
        manifest = fetch_manifest(source)
    except NoReleases:
        return None
    return manifest if is_newer(manifest["version"], current_version) else None


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def download(manifest, progress=None, cancel=None, dest_dir=None):
    """Скачивает установщик и проверяет SHA-256. progress(получено, всего).
    Возвращает путь к файлу; при отмене или ошибке — UpdateError."""
    url = manifest["url"]
    dest_dir = dest_dir or tempfile.mkdtemp(prefix="barcodegen_update_")
    os.makedirs(dest_dir, exist_ok=True)
    name =os.path.basename(url.split("?")[0]) or "barcodeGen-setup.exe"
    path = os.path.join(dest_dir, name)
    try:
        with _open(url) as src, open(path, "wb") as out:
            if hasattr(src, "headers"):          # ответ сервера
                total = int(src.headers.get("Content-Length") or 0)
            else:                                # локальный или сетевой файл
                total = os.fstat(src.fileno()).st_size
            done = 0
            while True:
                if cancel is not None and cancel.is_set():
                    raise UpdateError("Загрузка отменена")
                block = src.read(CHUNK)
                if not block:
                    break
                out.write(block)
                done += len(block)
                if progress:
                    progress(done, total)
    except UpdateError:
        _remove(path)
        raise
    except Exception as e:
        _remove(path)
        raise UpdateError(f"Не удалось скачать обновление: {_human_error(e)}")

    if sha256_file(path).lower() != manifest["sha256"].strip().lower():
        _remove(path)
        raise UpdateError("Файл обновления повреждён (контрольная сумма не совпала). "
                          "Попробуйте ещё раз позже.")
    return path


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def install_command(installer_path):
    """Тихая установка поверх текущей версии; /UPDATE=1 — перезапуск после неё."""
    return [installer_path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
            "/CLOSEAPPLICATIONS", "/UPDATE=1"]


def can_self_update():
    """Обновляться умеет только версия, поставленная установщиком
    (рядом с exe лежит его деинсталлятор)."""
    if not getattr(sys, "frozen", False):
        return False
    folder = os.path.dirname(sys.executable)
    return any(name.lower().startswith("unins") and name.lower().endswith(".exe")
               for name in os.listdir(folder))


def launch_installer(installer_path):
    """Запускает установщик отдельным процессом; программа после этого
    должна сразу закрыться, чтобы установщик мог заменить её файлы."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(install_command(installer_path), close_fds=True, creationflags=flags)
