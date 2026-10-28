@echo off
chcp 65001 >nul
echo ========================================
echo  barcodeGen - Сборка EXE
echo ========================================
echo.

echo 📦 Установка зависимостей...
python -m pip install -r requirements.txt
if errorlevel 1 ( echo Ошибка установки! & pause & exit /b 1 )

echo.
echo 🚀 Сборка EXE...
python -m PyInstaller --noconfirm --onefile --windowed ^
    --name "barcodeGen" ^
    --icon "logo.ico" ^
    --add-data "logo.ico;." ^
    --add-data "logo.png;." ^
    --add-data "fonts;fonts" ^
    --collect-all customtkinter ^
    --collect-all barcode ^
    --collect-all tkinterdnd2 ^
    --hidden-import "PIL._imaging" ^
    main.py

if errorlevel 1 ( echo Ошибка сборки! & pause & exit /b 1 )

echo.
echo ========================================
echo  ГОТОВО! EXE в папке dist
echo ========================================
pause