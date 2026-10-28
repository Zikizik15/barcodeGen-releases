# barcodeGen — Генератор штрихкодов и QR-кодов

Десктопное приложение для генерации штрихкодов, QR-кодов и печатных этикеток в PDF.

## Возможности

- **Штрихкоды**: Code 128, Code 39, EAN-13, EAN-8, UPC-A, ITF, Codabar
- **QR-коды**: с настраиваемым качеством (от 300 до 1500 DPI)
- **QR-паспорта**: генерация QR с ФИО, комплектом и датой выдачи
- **Визуальный редактор шаблонов**: перетаскивание и ресайз элементов
- **Экспорт**: PDF, ZIP-архив, Excel (XLSX), CSV
- **Drag & Drop**: загрузка файлов кодов перетаскиванием
- **Предпросмотр печати**: точный вид этикеток перед печатью
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

### Windows

```bat
build.bat
```

Результат: `dist/main.exe` (Windows) или `dist/main` (Linux)

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
| F5 | Очистить список |

## Структура проекта

```
BarcodeGen/
├── main.py                  # Точка входа
├── pyproject.toml           # Конфигурация сборки
├── requirements.txt         # Зависимости
├── build.sh / build.bat     # Скрипты PyInstaller
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
└── logger.py                # Логирование
```

## Лицензия

MIT
