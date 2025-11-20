# Folder Helper - Desktop приложение для выбора папки

Мини-приложение для получения абсолютного пути к локальной папке через браузер.

## Описание

Это решение обходит ограничения безопасности браузера, которые не позволяют JavaScript получить полный путь к локальной папке. Приложение работает как локальный REST-сервер, который показывает системный диалог выбора папки и возвращает абсолютный путь.

## Установка зависимостей

```bash
pip install flask pyinstaller
```

## Сборка исполняемого файла

### Для Linux

#### Вариант 1: Использование spec файла (рекомендуется)

```bash
cd bpmn/folder-helper
pyinstaller folder-helper.spec --clean
```

#### Вариант 2: Использование скрипта сборки

```bash
cd bpmn/folder-helper
./build.sh
```

#### Вариант 3: Прямая команда PyInstaller

```bash
cd bpmn/folder-helper
pyinstaller --noconsole --onefile --name folder-helper \
  --hidden-import flask --hidden-import tkinter --hidden-import tkinter.filedialog \
  folder-helper.py
```

### Для Windows 11

⚠️ **Важно**: Сборка для Windows должна выполняться на Windows-машине (PyInstaller не поддерживает кросс-компиляцию).

#### Вариант 1: Использование bat-скрипта (рекомендуется)

1. Скопируйте файлы на Windows-машину:
   - `folder-helper.py`
   - `build-windows.bat`
   - `folder-helper-windows.spec` (опционально)

2. Запустите сборку:
   ```cmd
   build-windows.bat
   ```

#### Вариант 2: Ручная сборка

1. Установите Python 3.8+ с официального сайта python.org
2. Установите зависимости:
   ```cmd
   pip install flask pyinstaller
   ```
3. Выполните сборку:
   ```cmd
   pyinstaller --noconsole --onefile --name folder-helper ^
     --hidden-import flask --hidden-import tkinter --hidden-import tkinter.filedialog ^
     folder-helper.py
   ```

#### Вариант 3: Использование spec файла

```cmd
pyinstaller folder-helper-windows.spec --clean
```

## Результат сборки

После сборки исполняемый файл будет находиться в:
- **Linux**: `dist/folder-helper`
- **Windows**: `dist/folder-helper.exe`

## Использование

### 1. Запуск приложения

```bash
# Linux
./dist/folder-helper

# Windows
dist\folder-helper.exe
```

### 2. Использование из браузера (JavaScript)

```javascript
// Выбор папки
fetch('http://localhost:5678/select-folder')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('Выбранная папка:', data.path);
      // Используйте data.path для дальнейшей обработки
    } else {
      console.error('Ошибка:', data.error);
    }
  })
  .catch(error => {
    console.error('Ошибка подключения:', error);
  });

// Проверка доступности сервера
fetch('http://localhost:5678/health')
  .then(response => response.json())
  .then(data => console.log('Статус:', data.status));
```

### 3. Интеграция с Bitrix24

В пользовательском поле или компоненте Bitrix24:

```javascript
BX.ajax({
    url: 'http://localhost:5678/select-folder',
    method: 'GET',
    dataType: 'json',
    onsuccess: function(data) {
        if (data.success) {
            // Заполнить поле значением data.path
            BX('input-field-id').value = data.path;
        } else {
            alert('Папка не выбрана');
        }
    },
    onfailure: function() {
        alert('Ошибка подключения к folder-helper. Убедитесь, что приложение запущено.');
    }
});
```

## API Endpoints

- `GET /select-folder` - Открывает диалог выбора папки и возвращает путь
  - Успех: `{"path": "/full/path/to/folder", "success": true}`
  - Отмена: `{"path": "", "success": false, "error": "Папка не выбрана"}`
  - Ошибка: `{"path": "", "success": false, "error": "описание ошибки"}`

- `GET /health` - Проверка доступности сервера
  - Ответ: `{"status": "ok"}`

## Безопасность

⚠️ **Важно**: Приложение слушает только на `127.0.0.1:5678`, что означает доступ только с локального компьютера. Это безопасно для использования.

## Устранение неполадок

### Приложение не запускается
- Убедитесь, что порт 5678 свободен
- Проверьте, что все зависимости установлены

### Браузер не может подключиться
- Убедитесь, что приложение запущено
- Проверьте, что нет блокировки файрволом
- Попробуйте открыть `http://localhost:5678/health` в браузере

### Диалог не появляется
- На Linux может потребоваться установка GUI библиотек
- Убедитесь, что вы запускаете приложение в графической среде

## Технические детали

- **Flask**: Веб-сервер для REST API
- **tkinter**: Системный диалог выбора папки
- **PyInstaller**: Упаковка в исполняемый файл
- **Порт**: 5678 (можно изменить в коде)

