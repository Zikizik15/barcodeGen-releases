# publish_update.py - Подготовка обновления к публикации
#
# Порядок выпуска новой версии:
#   1. Поменять версию в version.py и pyproject.toml
#   2. build_installer.bat               → dist\installer\barcodeGen-<версия>-setup.exe
#   3. python publish_update.py --notes "Что нового"   (или --notes-file файл.txt)
#                                         → dist\installer\latest.json
#   4. В публичном репозитории с релизами создать релиз с тегом v<версия>
#      и приложить к нему ОБА файла: установщик и latest.json.
#
# Программы у пользователей смотрят latest.json последнего релиза и
# предлагают обновиться, если версия в нём новее.

import argparse
import json
import os
import sys

from version import __version__, APP_NAME
from updater import RELEASES_REPO, sha256_file, parse_version

INSTALLER_DIR = os.path.join("dist", "installer")


def main():
    parser = argparse.ArgumentParser(description="Готовит latest.json для обновления программы")
    notes = parser.add_mutually_exclusive_group()
    notes.add_argument("--notes", default="", help="Что нового (текст для пользователей)")
    notes.add_argument("--notes-file", help="Файл с описанием изменений (UTF-8)")
    args = parser.parse_args()

    parse_version(__version__)
    name = f"{APP_NAME}-{__version__}-setup.exe"
    installer = os.path.join(INSTALLER_DIR, name)
    if not os.path.exists(installer):
        sys.exit(f"Нет установщика {installer}. Сначала запустите build_installer.bat")

    text = args.notes
    if args.notes_file:
        with open(args.notes_file, encoding="utf-8-sig") as f:
            text = f.read().strip()

    manifest = {
        "version": __version__,
        "url": f"https://github.com/{RELEASES_REPO}/releases/download/v{__version__}/{name}",
        "sha256": sha256_file(installer),
        "notes": text,
    }
    out = os.path.join(INSTALLER_DIR, "latest.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Готово: {out}\n")
    print(f"Теперь на https://github.com/{RELEASES_REPO}/releases/new :")
    print(f"  • тег:   v{__version__}")
    print(f"  • файлы: {installer}")
    print(f"           {out}")
    print("  • нажмите «Publish release».")
    print("\nПрограммы пользователей увидят обновление при следующем запуске.")


if __name__ == "__main__":
    main()
