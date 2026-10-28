@echo off
chcp 65001 >nul
rem build_installer.bat - Сборка установщика barcodeGen
rem
rem 1) PyInstaller собирает программу в папку dist\barcodeGen\ (а не в один exe:
rem    так она быстрее запускается и реже смущает антивирусы)
rem 2) Inno Setup упаковывает папку в dist\installer\barcodeGen-<версия>-setup.exe
rem
rem Нужно: Python с зависимостями (requirements.txt) и Inno Setup 6
rem (winget install --id JRSoftware.InnoSetup -e)

setlocal
cd /d "%~dp0"

for /f %%v in ('python -c "from version import __version__; print(__version__)"') do set APP_VERSION=%%v
if "%APP_VERSION%"=="" ( echo Не удалось прочитать версию из version.py & exit /b 1 )
echo Версия: %APP_VERSION%

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" ( echo Inno Setup 6 не найден. Установите: winget install --id JRSoftware.InnoSetup -e & exit /b 1 )

echo.
echo === 1/2 Сборка программы (PyInstaller) ===
python -m PyInstaller --noconfirm --onedir --windowed ^
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
if errorlevel 1 ( echo Ошибка сборки PyInstaller & exit /b 1 )

echo.
echo === 2/2 Сборка установщика (Inno Setup) ===
"%ISCC%" /Qp /DMyAppVersion=%APP_VERSION% installer.iss
if errorlevel 1 ( echo Ошибка сборки установщика & exit /b 1 )

echo.
echo ГОТОВО: dist\installer\barcodeGen-%APP_VERSION%-setup.exe
endlocal
