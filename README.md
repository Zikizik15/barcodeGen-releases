# barcodeGen — Генератор штрихкодов и QR-кодов

Десктопное приложение для генерации штрихкодов, QR-кодов и печатных этикеток в PDF.

## Возможности

- **Штрихкоды**: Code 128, Code 39, EAN-13, EAN-8, UPC-A, ITF, Codabar
  (для EAN/UPC проверяется контрольная цифра)
- **QR-коды**: с настраиваемым качеством (от 300 до 1500 DPI)
- **QR-паспорта**: генерация QR с ФИО, комплектом и датой выдачи,
  по желанию — с логотипом в центре (капля или свой файл)
- **Серия номеров**: SN-0001…SN-0500 с префиксом, шагом и числом цифр;
  для EAN/UPC контрольная цифра дописывается автоматически
- **Визуальный редактор шаблонов**: перетаскивание и ресайз элементов,
  подстановки `{code}`, `{name}`, `{price}` и любые колонки из CSV/Excel
- **Импорт**: TXT, CSV, Excel (XLSX) — кнопкой или перетаскиванием
- **Экспорт**: PDF, ZIP-архив, Excel (XLSX), CSV
- **Раскладка**: несколько этикеток на странице PDF, в том числе по шаблону
- **Предпросмотр печати**: показывает ровно то, что попадёт в PDF
- **Фоновая генерация**: окно не зависает, генерацию можно отменить
- **Автосохранение**: каждые 30 секунд
- **Горячие клавиши**: Ctrl+O/S/G/R/F/H/P, F5, Ctrl+T

## Установка

```bash
pip install -r requirements.txt
```

Или через `pyproject.toml`:

```bash
pip install .
```

## Запуск

```bash
python3 main.py
```

## Сборка в standalone-исполняемый файл

### Linux

```bash
./build.sh
```

### Windows: установщик (рекомендуется)

```bat
build_installer.bat
```

Результат: `dist\installerarcodeGen-<версия>-setup.exe` — обычный установщик
с ярлыками в «Пуске» и на рабочем столе и удалением через «Приложения».
Ставится без прав администратора. Программа в этом варианте запускается
быстрее, чем одиночный exe. Нужен [Inno Setup 6](https://jrsoftware.org/isinfo.php):
`winget install --id JRSoftware.InnoSetup -e`.

### Windows: один exe-файл

```bat
build.bat
```

Результат: `dist/barcodeGen.exe` (Windows) или `dist/barcodeGen` (Linux).
Шрифт Montserrat из папки `fonts/` встраивается в exe автоматически.

## Обновления у пользователей

Установленная программа при запуске проверяет, нет ли новой версии, и показывает
в сайдбаре плашку «Доступна версия …». По кнопке «Обновить» установщик
скачивается, проверяется по SHA-256 и ставится тихо поверх; программа
перезапускается сама, настройки и список кодов сохраняются. Проверить вручную —
«О программе» → «Проверить обновления».

Обновления берутся из публичного репозитория
[`Zikizik15/barcodeGen-releases`](https://github.com/Zikizik15/barcodeGen-releases)
(только установщики; исходный код остаётся приватным) — см. `RELEASES_REPO`
в `updater.py`.

Как выпустить обновление:

1. Поменять версию в `version.py` и `pyproject.toml`.
2. `build_installer.bat`
3. `python publish_update.py --notes "Что нового"` — создаст `dist\installer\latest.json`.
4. В репозитории `barcodeGen-releases` → Releases → **Draft a new release**:
   тег `v<версия>`, приложить установщик и `latest.json`, **Publish release**.

Для офиса без интернета источник можно переопределить переменной окружения
`BARCODEGEN_UPDATE_URL` — путём к `latest.json` в сетевой папке.

## Тесты

```bash
pip install pytest
python -m pytest
```

## Зависимости

| Пакет | Назначение |
|---|---|
| customtkinter | GUI-фреймворк |
| python-barcode | Генерация штрихкодов |
| Pillow | Обработка изображений |
| reportlab | Генерация PDF |
| qrcode | Генерация QR-кодов |
| openpyxl | Экспорт в Excel |
| tkinterdnd2 | Drag & Drop |
| pyzbar | QA-проверка штрихкодов |

## Хранилище данных

Настройки, история и автосохранение хранятся в:

- **Linux**: `~/.config/barcodeGen/`
- **Windows**: `%APPDATA%\barcodeGen\`
- **macOS**: `~/Library/Application Support/barcodeGen/`

## Горячие клавиши

| Клавиша | Действие |
|---|---|
| Ctrl+O | Открыть файл |
| Ctrl+S | Сохранить файл |
| Ctrl+G | Создать PDF |
| Ctrl+R | Случайный код |
| Ctrl+F | Поиск |
| Ctrl+H | История |
| Ctrl+P | Предпросмотр |
| Ctrl+T | Редактор шаблона |
| F1 | О программе |
| F5 | Очистить список |

## Структура проекта

```
BarcodeGen/
├── main.py                  # Точка входа
├── version.py               # Номер версии (единственное место)
├── pyproject.toml           # Конфигурация сборки
├── requirements.txt         # Зависимости
├── build.sh / build.bat     # Скрипты PyInstaller (один exe)
├── build_installer.bat      # Сборка установщика
├── installer.iss            # Скрипт установщика Inno Setup
├── updater.py               # Проверка и установка обновлений
├── publish_update.py        # Подготовка latest.json для выпуска обновления
├── fonts/                   # Шрифт Montserrat (лицензия OFL)
├── gui/
│   ├── theme.py             # Дизайн-система: палитра, шрифты, иконки, готовые виджеты
│   ├── gui.py               # Главное окно
│   ├── gui_qr_tab.py        # Вкладка QR-паспортов
│   ├── gui_barcode_settings.py # Настройки штрихкодов
│   ├── gui_qr_settings.py   # Настройки QR-паспортов
│   ├── gui_template_editor.py # Редактор шаблонов
│   ├── gui_preview.py       # Предпросмотр печати
│   └── gui_widgets.py       # Переиспользуемые виджеты и каркас окна настроек
├── barcode_generator.py     # Генерация штрихкодов/PDF
├── utils.py                 # Утилиты и пресеты
├── settings.py              # Менеджер настроек
├── logger.py                # Логирование
└── tests/                   # Тесты (pytest)
```

## Лицензия

MIT
