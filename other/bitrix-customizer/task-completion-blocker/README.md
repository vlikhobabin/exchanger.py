# Блокировщик завершения задач с требованием результата

## Описание

Система кастомизации модуля задач Bitrix24, которая блокирует завершение задач с флагом "требуется результат" до тех пор, пока пользователь не выберет результат (Да/Нет). Включает JavaScript модификатор интерфейса и PHP обработчик событий.

## Возможности

- ✅ **Автоматическое обнаружение** задач с требуемым результатом
- ✅ **Кастомная кнопка** "Завершить с результатом"
- ✅ **Модальное окно** с выбором результата
- ✅ **Блокировка завершения** без результата
- ✅ **Автоматическое сохранение** ответа в UF поле
- ✅ **Автозакрытие слайдера** после завершения
- ✅ **Безопасное развертывание** с резервным копированием

## Структура компонентов

```
task-completion-blocker/
├── 🎯 Модификации
│   ├── enhanced_task_modifier.js     # JavaScript модификатор интерфейса
│   ├── task_completion_blocker.php   # PHP обработчик событий
│   └── init.php                      # Файл инициализации
├── 🚀 Развертывание
│   ├── deploy_task_blocker.py        # Система развертывания
│   └── deploy_and_test.py            # Мастер-скрипт развертывания
├── ⚙️ Конфигурация
│   └── config/
│       └── task_blocker_config.json  # Конфигурация блокировщика
├── 📦 Развертывание
│   └── deployment/
└── 📄 README.md                      # Документация
```

## Принцип работы

### 1. Обнаружение задач с требуемым результатом

JavaScript сканирует задачи на наличие поля `UF_RESULT_EXPECTED=true`:

```javascript
// Автоматическое обнаружение задач
if (taskData.UF_RESULT_EXPECTED === true) {
    // Задача требует результат
    modifyTaskInterface(completeButton, taskId, taskData, targetWindow);
}
```

### 2. Модификация интерфейса

Заменяет стандартную кнопку "Завершить" на "Завершить с результатом":

```javascript
// Создание кастомной кнопки
const customButton = document.createElement('button');
customButton.textContent = 'Завершить с результатом';
customButton.onclick = () => showResultModal(taskId, questionText, targetWindow);
```

### 3. Модальное окно выбора

Показывает диалог с вопросом и кнопками "Да/Нет/Отмена":

```javascript
// Обработка выбора результата
function handleAnswer(taskId, answer, messageBox, targetWindow) {
    // Сохранение ответа в UF_RESULT_ANSWER
    // Завершение задачи
    // Автозакрытие слайдера
}
```

### 4. PHP обработчик событий

Блокирует завершение задач без результата:

```php
// Обработчик OnBeforeTaskUpdate
function blockTaskCompletionWithoutAnswer($taskId, &$arFields, &$arTaskCopy) {
    if ($arFields['STATUS'] == CTasks::STATE_COMPLETED) {
        if ($arTaskCopy['UF_RESULT_EXPECTED'] && empty($arTaskCopy['UF_RESULT_ANSWER'])) {
            // Блокируем завершение без результата
            return false;
        }
    }
    return true;
}
```

## Использование

### Быстрое развертывание

```bash
# Автоматическое развертывание всех компонентов
python deploy_and_test.py

# Выполняет:
# 1. Создание резервной копии
# 2. Развертывание файлов
# 3. Настройку шаблонов
# 4. Тестирование
```

### Пошаговое развертывание

```bash
# 1. Развертывание блокировщика
python deployment/deploy_task_blocker.py

# 2. Тестирование функциональности
python deployment/deploy_task_blocker.py --test
```

## Конфигурация

### Настройка полей Bitrix24

В файле `config.json` настройте ID полей:

```json
{
  "bitrix_field_config": {
    "UF_RESULT_ANSWER": {
      "type": "list",
      "values": {
        "yes": 26,
        "no": 27
      }
    }
  }
}
```

### Конфигурация поля UF_RESULT_ANSWER

Поле должно быть типа "Список" со значениями:

| ID | XML_ID | Значение |
|----|--------|----------|
| 26 | да | ДА |
| 27 | нет | НЕТ |

### Конфигурация поля UF_RESULT_EXPECTED

Поле должно быть типа "Да/Нет" для флага необходимости результата.

## Архитектура решения

### Frontend (JavaScript)

- **Сканирование задач** на наличие флага результата
- **Модификация интерфейса** замена кнопки завершения
- **Модальные окна** для выбора результата
- **AJAX запросы** для сохранения данных
- **Автозакрытие слайдера** после завершения

### Backend (PHP)

- **Обработчики событий** для блокировки завершения
- **Валидация данных** проверка наличия результата
- **Логирование** для отслеживания операций
- **Безопасная обработка** ошибок и исключений

## Безопасность

### Проверки на стороне сервера

```php
// Проверка наличия результата
if ($arTaskCopy['UF_RESULT_EXPECTED']) {
    if (empty($arTaskCopy['UF_RESULT_ANSWER'])) {
        safeLog("Попытка завершить задачу без результата: " . $taskId);
        return false;
    }
}
```

### Валидация на стороне клиента

```javascript
// Проверка перед отправкой
if (!answer || (answer !== 'yes' && answer !== 'no')) {
    showErrorDialog('Необходимо выбрать результат', targetWindow);
    return;
}
```

## Интеграция с шаблонами

### Подключение JavaScript

В файле `/local/templates/bitrix24/footer.php`:

```php
<script src="<?=SITE_TEMPLATE_PATH?>/assets/js/enhanced_task_modifier.js?v=<?=time()?>"></script>
```

### Подключение PHP обработчиков

В файле `/local/php_interface/init.php`:

```php
<?php
require_once(__DIR__ . '/task_completion_blocker.php');
```

## Развертывание

### Автоматическое развертывание

```bash
# Полное развертывание с проверками
python deploy_and_test.py

# Этапы:
# 1. Проверка конфигурации
# 2. Создание резервной копии
# 3. Копирование файлов
# 4. Настройка шаблонов
# 5. Установка прав доступа
# 6. Тестирование функциональности
```

### Ручное развертывание

```bash
# 1. Копирование PHP файлов
python deployment/deploy_task_blocker.py --php-only

# 2. Копирование JavaScript файлов
python deployment/deploy_task_blocker.py --js-only

# 3. Настройка шаблонов
python deployment/deploy_task_blocker.py --templates-only
```

## Тестирование

### Функциональное тестирование

```bash
# Тестирование развертывания
python deployment/deploy_task_blocker.py --test

# Проверяет:
# - Наличие файлов на сервере
# - Подключение к шаблонам
# - Права доступа
# - Синтаксис PHP и JavaScript
```

### Мануальное тестирование

1. Создайте задачу с флагом `UF_RESULT_EXPECTED = true`
2. Откройте задачу в интерфейсе
3. Проверьте наличие кнопки "Завершить с результатом"
4. Попробуйте завершить задачу без выбора результата
5. Выберите результат и завершите задачу

## Устранение проблем

### Типичные ошибки

**Ошибка:** Кнопка не изменяется
**Решение:** Проверьте подключение JavaScript в шаблоне

**Ошибка:** Задача завершается без результата
**Решение:** Проверьте подключение PHP обработчика

**Ошибка:** Модальное окно не появляется
**Решение:** Проверьте настройку полей UF_RESULT_EXPECTED

### Диагностика

```bash
# Проверка файлов на сервере
python deployment/deploy_task_blocker.py --check

# Проверка логов
tail -f /var/log/bitrix/php_error.log
```

## Откат изменений

### Восстановление из резервной копии

```bash
# Полное восстановление системы
python ../backup-restore-system/restore_manager.py full

# Удаляет все файлы блокировщика и восстанавливает оригинальные
```

### Ручное удаление

```bash
# Удаление файлов блокировщика
rm /home/bitrix/www/local/php_interface/task_completion_blocker.php
rm /home/bitrix/www/local/templates/bitrix24/assets/js/enhanced_task_modifier.js

# Удаление подключений из шаблонов
# Отредактируйте footer.php и init.php
```

---

**Версия:** 2.0  
**Совместимость:** Bitrix24 коробочная версия, JavaScript ES6+  
**Зависимости:** PHP 7.4+, MySQL, SSH доступ 