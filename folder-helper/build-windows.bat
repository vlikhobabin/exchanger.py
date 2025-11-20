@echo off
REM Скрипт сборки folder-helper.exe для Windows
REM Использование: build-windows.bat

echo ========================================
echo Сборка folder-helper.exe для Windows
echo ========================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден! Установите Python 3.8+
    pause
    exit /b 1
)

echo [1/4] Проверка зависимостей...
python -m pip show flask >nul 2>&1
if errorlevel 1 (
    echo [УСТАНОВКА] Устанавливаю Flask...
    python -m pip install flask
)

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [УСТАНОВКА] Устанавливаю PyInstaller...
    python -m pip install pyinstaller
)

echo [2/4] Очистка предыдущих сборок...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] Сборка исполняемого файла...
python -m PyInstaller --noconsole --onefile --name folder-helper ^
    --hidden-import flask ^
    --hidden-import tkinter ^
    --hidden-import tkinter.filedialog ^
    folder-helper.py

if errorlevel 1 (
    echo [ОШИБКА] Сборка не удалась!
    pause
    exit /b 1
)

echo.
echo [4/4] Сборка завершена успешно!
echo.
echo ========================================
echo Исполняемый файл: dist\folder-helper.exe
echo ========================================
echo.
echo Для запуска выполните:
echo   dist\folder-helper.exe
echo.
pause

