#!/bin/bash
# build.sh - Скрипт сборки для Linux

set -e

echo "========================================"
echo " barcodeGen - Сборка (Linux)"
echo "========================================"
echo

echo "📦 Установка зависимостей..."
pip3 install -r requirements.txt
echo

echo "🚀 Сборка..."
# --collect-all нужен для customtkinter (JSON-файлы тем подгружаются по
# пути к пакету в рантайме) и для python-barcode (классы штрихкодов
# code128/code39/... подгружаются динамически по строке).
pyinstaller --noconfirm --onefile --windowed \
    --name "barcodeGen" \
    --icon "logo.ico" \
    --add-data "logo.ico:." \
    --add-data "logo.png:." \
    --collect-all customtkinter \
    --collect-all barcode \
    --collect-all tkinterdnd2 \
    --hidden-import "PIL._imaging" \
    main.py

echo
echo "✅ Готово! Файл: dist/barcodeGen"
