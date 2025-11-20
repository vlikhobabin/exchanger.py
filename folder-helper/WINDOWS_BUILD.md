# Инструкция по сборке для Windows 11

## Быстрый старт

### Шаг 1: Подготовка файлов

Скопируйте на Windows-машину следующие файлы:
- `folder-helper.py` - основной файл приложения
- `build-windows.bat` - скрипт автоматической сборки
- `folder-helper-windows.spec` - конфигурация PyInstaller (опционально)

### Шаг 2: Установка Python

1. Скачайте Python 3.8+ с [python.org](https://www.python.org/downloads/)
2. При установке **обязательно** отметьте "Add Python to PATH"
3. Проверьте установку:
   ```cmd
   python --version
   ```

### Шаг 3: Сборка

#### Автоматическая сборка (рекомендуется)

Просто запустите:
```cmd
build-windows.bat
```

Скрипт автоматически:
- Проверит наличие Python
- Установит Flask и PyInstaller (если нужно)
- Выполнит сборку
- Создаст `dist\folder-helper.exe`

#### Ручная сборка

1. Откройте командную строку (cmd) или PowerShell
2. Перейдите в папку с файлами:
   ```cmd
   cd путь\к\папке\folder-helper
   ```
3. Установите зависимости:
   ```cmd
   pip install flask pyinstaller
   ```
4. Выполните сборку:
   ```cmd
   pyinstaller --noconsole --onefile --name folder-helper --hidden-import flask --hidden-import tkinter --hidden-import tkinter.filedialog folder-helper.py
   ```

### Шаг 4: Результат

После успешной сборки файл будет находиться в:
```
dist\folder-helper.exe
```

## Использование

1. Запустите `folder-helper.exe`
2. Приложение запустит локальный сервер на `http://localhost:5678`
3. В браузере откройте: `http://localhost:5678/select-folder`
4. Откроется диалог выбора папки
5. После выбора папки вы получите JSON с полным путем

## Интеграция с Bitrix24

В JavaScript коде Bitrix24:

```javascript
fetch('http://localhost:5678/select-folder')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('Выбранная папка:', data.path);
      // Используйте data.path
      BX('input-field-id').value = data.path;
    } else {
      alert('Папка не выбрана');
    }
  })
  .catch(error => {
    alert('Ошибка подключения. Убедитесь, что folder-helper.exe запущен.');
  });
```

## Устранение неполадок

### Ошибка: "Python не найден"
- Убедитесь, что Python установлен и добавлен в PATH
- Перезапустите командную строку после установки Python

### Ошибка: "pip не найден"
- Установите Python с официального сайта (не из Microsoft Store)
- При установке отметьте "Add Python to PATH"

### Ошибка при сборке: "tkinter not found"
- Установите Python с официального сайта (tkinter входит в стандартную поставку)
- Не используйте Microsoft Store версию Python

### Антивирус блокирует exe
- Добавьте папку `dist` в исключения антивируса
- Это нормально - PyInstaller создает упакованные exe, которые могут вызывать подозрения

### Приложение не запускается
- Убедитесь, что порт 5678 свободен
- Проверьте, нет ли другого экземпляра приложения
- Попробуйте запустить из командной строки для просмотра ошибок

## Технические детали

- **Размер exe**: ~15-20 MB (включает Python runtime и все зависимости)
- **Порт**: 5678 (можно изменить в `folder-helper.py`)
- **Зависимости**: Flask, tkinter (встроен в Python)
- **Совместимость**: Windows 10, Windows 11

## Альтернатива: Готовая сборка

Если у вас нет возможности собрать самостоятельно, можно:
1. Попросить коллегу с Windows собрать для вас
2. Использовать виртуальную машину Windows
3. Использовать облачный сервис с Windows (Azure, AWS)

