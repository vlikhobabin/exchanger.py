#!/bin/bash
# Скрипт сборки folder-helper.exe

echo ">>> Сборка folder-helper..."

# Проверка наличия pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "Ошибка: pyinstaller не установлен. Установите: pip install pyinstaller"
    exit 1
fi

# Переход в директорию скрипта
cd "$(dirname "$0")"

# Сборка с использованием spec файла (рекомендуется)
echo ">>> Используется spec файл для точной настройки..."
pyinstaller folder-helper.spec --clean

# Альтернатива: прямая сборка (раскомментируйте, если spec не нужен)
# pyinstaller --noconsole --onefile --name folder-helper \
#   --hidden-import flask --hidden-import tkinter --hidden-import tkinter.filedialog \
#   folder-helper.py

echo ""
echo ">>> Сборка завершена!"
echo ">>> Исполняемый файл: dist/folder-helper (или dist/folder-helper.exe на Windows)"
echo ""
echo ">>> Для тестирования запустите:"
echo "    ./dist/folder-helper"
echo ""
echo ">>> Затем в браузере откройте:"
echo "    http://localhost:5678/select-folder"

