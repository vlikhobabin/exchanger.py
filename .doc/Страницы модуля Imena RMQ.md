# IMENA RabbitMQ - Документация страниц модуля

**Версия:** 1.0+  
**Статус:** ✅ Активно используется  
**Автор:** #vlikhobabin@gmail.com  
**Дата последнего обновления:** 25.01.2025

---

## 📋 Содержание

1. [Обзор](#обзор)
2. [Структура каталога](#структура-каталога)
3. [Страницы модуля](#страницы-модуля)
   - [queues/index.php - Список очередей](#queuesindexphp---список-очередей)
   - [settings/index.php - Настройки подключения](#settingsindexphp---настройки-подключения)
4. [Меню навигации](#меню-навигации)
5. [Архитектура страниц](#архитектура-страниц)
6. [Интеграция с компонентами](#интеграция-с-компонентами)
7. [JavaScript функциональность](#javascript-функциональность)
8. [Стили и оформление](#стили-и-оформление)
9. [Безопасность](#безопасность)
10. [Разработка и расширение](#разработка-и-расширение)

---

## Обзор

Каталог `/local/pages/imena/rmq/` содержит страницы пользовательского интерфейса для модуля управления RabbitMQ. Страницы предоставляют веб-интерфейс для работы с RabbitMQ Management API через Bitrix24.

### Основные возможности

- ✅ **Список очередей** - отображение всех очередей RabbitMQ в Grid системе
- ✅ **Настройки подключения** - конфигурация API credentials и проверка соединения
- ✅ **Навигационное меню** - левое меню для перехода между разделами
- ✅ **AJAX обновления** - динамическое обновление данных без перезагрузки страницы
- ✅ **Обработка ошибок** - пользовательские сообщения об ошибках подключения

---

## Структура каталога

```
local/pages/imena/rmq/
├── .left.menu.php          # Конфигурация левого меню навигации
├── queues/
│   └── index.php           # Страница списка очередей RabbitMQ
├── settings/
│   └── index.php           # Страница настроек подключения к RabbitMQ
└── README.md               # Этот файл
```

---

## Страницы модуля

### queues/index.php - Список очередей

**Путь:** `/local/pages/imena/rmq/queues/`  
**Назначение:** Главная страница модуля для отображения списка очередей RabbitMQ

#### Описание

Страница отображает список всех очередей из указанного виртуального хоста (vhost) в виде таблицы с использованием Bitrix Grid системы. Страница интегрирована с компонентом `imena.rmq:queue.list` и предоставляет современный интерфейс для управления очередями.

#### Основные функции

1. **Отображение списка очередей**
   - Табличное представление с Grid системой Bitrix24
   - Информация о количестве сообщений, потребителях, состоянии
   - Отображение особенностей очередей (durable, auto-delete, exclusive)
   - Информация о потреблении памяти и узлах кластера

2. **Проверка настроек подключения**
   - Автоматическая проверка наличия credentials
   - Предупреждение при отсутствии настроек
   - Ссылка на страницу настроек

3. **Кнопка обновления данных**
   - Динамическая кнопка обновления в toolbar
   - AJAX обновление Grid без перезагрузки страницы
   - Визуальная индикация процесса обновления

#### Архитектура

```php
queues/index.php
    │
    ├─> Проверка модуля imena.rmq
    ├─> Проверка настроек подключения
    ├─> Отображение предупреждения (если нет credentials)
    │
    └─> bitrix:ui.sidepanel.wrapper
            │
            └─> imena.rmq:queue.list (компонент)
                    │
                    ├─> RmqQueueGrid (Grid система)
                    ├─> RmqApiClient (API запросы)
                    └─> QueueEntity (Value Objects)
```

#### Параметры компонента

```php
$APPLICATION->IncludeComponent(
    'bitrix:ui.sidepanel.wrapper',
    '',
    [
        'POPUP_COMPONENT_NAME' => 'imena.rmq:queue.list',
        'POPUP_COMPONENT_TEMPLATE_NAME' => '',
        'POPUP_COMPONENT_PARAMS' => [
            'VHOST' => '/',                    // Virtual host
            'SHOW_EMPTY_QUEUES' => 'Y',        // Показывать пустые очереди
            'CACHE_TIME' => 0,                 // Без кеширования
            'CACHE_TYPE' => 'N',
        ],
        'USE_UI_TOOLBAR' => 'Y',
        'POPUP_COMPONENT_USE_BITRIX24_THEME' => 'Y',
    ]
);
```

#### JavaScript функциональность

**1. Кнопка обновления данных:**
```javascript
BX.ready(function() {
    // Создание кнопки обновления в toolbar
    var refreshButton = BX.create('button', {
        props: { className: 'ui-btn ui-btn-success ...' },
        events: {
            click: function(e) {
                // Блокировка кнопки
                // Показ уведомления
                // Обновление Grid через BX.Imena.RmqGrid.refreshGrid()
            }
        }
    });
});
```

**2. Обработчики событий:**
```javascript
// Событие выбора очереди
BX.addCustomEvent('onRabbitMQQueueSelected', function(queueName, queueData) {
    // Обработка выбора очереди
});

// Событие обновления данных
BX.addCustomEvent('onRabbitMQDataUpdated', function() {
    // Обработка обновления данных
});
```

**3. Проверка статуса подключения:**
```javascript
<?php if (!$hasCredentials): ?>
    BX.UI.Notification.Center.notify({
        content: 'Настройте подключение к RabbitMQ API для работы с очередями',
        position: 'top-right',
        type: 'warning'
    });
<?php endif; ?>
```

#### Стили

Страница включает кастомные стили для:
- Предупреждений о настройках (`.ui-alert-warning`)
- Кнопки обновления (`.ui-btn-icon-refresh`)
- Анимации вращения иконки при загрузке
- Адаптивности для мобильных устройств

#### Обработка ошибок

```php
// Проверка наличия credentials
$apiUrl = \Bitrix\Main\Config\Option::get('imena.rmq', 'api_url', '');
$hasCredentials = !empty($apiUrl) && !empty(\Bitrix\Main\Config\Option::get('imena.rmq', 'api_password'));

// Отображение предупреждения
<?php if (!$hasCredentials): ?>
    <div class="ui-alert ui-alert-warning">
        <span class="ui-alert-message">
            <strong>Внимание:</strong> Не настроено подключение к RabbitMQ API. 
            <a href="/local/pages/imena/rmq/settings/" class="ui-link">Перейти к настройкам</a>
        </span>
    </div>
<?php endif; ?>
```

---

### settings/index.php - Настройки подключения

**Путь:** `/local/pages/imena/rmq/settings/`  
**Назначение:** Страница настройки подключения к RabbitMQ Management API

#### Описание

Страница предоставляет форму для ввода учетных данных RabbitMQ Management API (URL, username, password) с возможностью проверки подключения и сохранения настроек. Настройки сохраняются в модульных опциях Bitrix24.

#### Основные функции

1. **Форма ввода учетных данных**
   - Поле URL сервера RabbitMQ (должно заканчиваться на `/api/`)
   - Поле имени пользователя
   - Поле пароля (с маскированием)
   - Валидация обязательных полей

2. **Проверка подключения**
   - Кнопка "Тестировать подключение"
   - Вызов `RmqApiClient::testConnection()`
   - Отображение результата (успех/ошибка)
   - Показ версии RabbitMQ и узла при успехе

3. **Сохранение настроек**
   - Сохранение в модульные опции Bitrix24
   - Автоматическая проверка подключения после сохранения
   - Отображение сообщения об успехе/ошибке

4. **Удаление учетных данных**
   - Кнопка "Удалить учетные данные"
   - Подтверждение действия
   - Очистка всех настроек подключения

5. **Информационная панель**
   - Описание RabbitMQ Management API
   - Требования к настройке
   - Инструкции по получению учетных данных

#### Архитектура

```php
settings/index.php
    │
    ├─> Обработка POST запросов
    │   ├─> save_credentials (сохранение)
    │   ├─> test_connection (проверка)
    │   └─> clear_credentials (удаление)
    │
    ├─> Получение текущих настроек из Option
    │
    └─> Отображение формы и статуса
```

#### Обработка действий

**1. Сохранение учетных данных:**
```php
if ($_SERVER['REQUEST_METHOD'] === 'POST' && check_bitrix_sessid()) {
    $action = $_POST['action'] ?? '';
    
    if ($action === 'save_credentials') {
        $serverUrl = trim($_POST['rmq_server_url'] ?? '');
        $username = trim($_POST['rmq_username'] ?? '');
        $password = trim($_POST['rmq_password'] ?? '');
        
        if (empty($serverUrl) || empty($username) || empty($password)) {
            $error = 'Все поля обязательны для заполнения';
        } else {
            // Сохранение настроек
            Option::set('imena.rmq', 'api_url', $serverUrl);
            Option::set('imena.rmq', 'api_username', $username);
            Option::set('imena.rmq', 'api_password', $password);
            
            // Тестирование подключения
            $apiClient = new RmqApiClient();
            $testResult = $apiClient->testConnection();
            
            if ($testResult->isSuccess()) {
                $saved = true;
            } else {
                $error = $testResult->getErrors()[0]->getMessage();
            }
        }
    }
}
```

**2. Тестирование подключения:**
```php
elseif ($action === 'test_connection') {
    try {
        $apiClient = new RmqApiClient();
        $testResult = $apiClient->testConnection();
    } catch (\Exception $e) {
        $error = 'Ошибка тестирования подключения: ' . $e->getMessage();
    }
}
```

**3. Удаление учетных данных:**
```php
elseif ($action === 'clear_credentials') {
    Option::delete('imena.rmq', ['api_url', 'api_username', 'api_password']);
    LocalRedirect($APPLICATION->GetCurPage());
}
```

#### Форма настроек

**Структура формы:**
```html
<form method="post" action="<?= $APPLICATION->GetCurPage() ?>" class="rmq-credentials-form">
    <?= bitrix_sessid_post() ?>
    <input type="hidden" name="action" value="save_credentials">
    
    <!-- URL сервера -->
    <div class="ui-form-row">
        <div class="ui-form-label">
            <div class="ui-ctl-label-text">URL сервера RabbitMQ <span class="required">*</span></div>
        </div>
        <div class="ui-form-content">
            <input type="url" name="rmq_server_url" class="ui-ctl-element" 
                   value="<?= htmlspecialcharsbx($apiUrl) ?>" 
                   placeholder="http://rmq.eg-holding.ru:15672/api/" required>
        </div>
    </div>
    
    <!-- Имя пользователя -->
    <div class="ui-form-row">
        <!-- ... -->
    </div>
    
    <!-- Пароль -->
    <div class="ui-form-row">
        <!-- ... -->
    </div>
    
    <!-- Кнопки действий -->
    <div class="ui-form-row">
        <button type="submit" class="ui-btn ui-btn-success">Сохранить</button>
        <button type="button" onclick="testConnection()">Тестировать подключение</button>
        <button type="button" onclick="clearCredentials()">Удалить учетные данные</button>
    </div>
</form>
```

#### Статус подключения

**Панель статуса:**
```php
<div class="rmq-status-panel">
    <div class="rmq-status-item">
        <span class="rmq-status-label">Статус:</span>
        <span class="rmq-status-value <?= $hasPassword ? 'status-ok' : 'status-error' ?>">
            <?= $hasPassword ? '✓ Настроено' : '✗ Не настроено' ?>
        </span>
    </div>
    
    <?php if ($apiUrl): ?>
        <div class="rmq-status-item">
            <span class="rmq-status-label">API URL:</span>
            <span class="rmq-status-value"><?= htmlspecialcharsbx($apiUrl) ?></span>
        </div>
    <?php endif; ?>
    
    <?php if ($username): ?>
        <div class="rmq-status-item">
            <span class="rmq-status-label">Пользователь:</span>
            <span class="rmq-status-value"><?= htmlspecialcharsbx($username) ?></span>
        </div>
    <?php endif; ?>
</div>
```

#### JavaScript функциональность

**1. Тестирование подключения:**
```javascript
function testConnection() {
    if (confirm('Протестировать подключение к RabbitMQ?')) {
        document.getElementById('test-connection-form').submit();
    }
}
```

**2. Удаление учетных данных:**
```javascript
function clearCredentials() {
    if (confirm('Вы уверены, что хотите удалить учетные данные?')) {
        document.getElementById('clear-credentials-form').submit();
    }
}
```

**3. Предотвращение клика на активной кнопке меню:**
```javascript
BX.ready(function() {
    const menuButtons = document.querySelectorAll('.main-buttons-item');
    
    menuButtons.forEach(function(button) {
        if (button.classList.contains('main-buttons-item-active')) {
            const link = button.querySelector('a.main-buttons-item-link, span.main-buttons-item-link');
            
            if (link) {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }, true);
                
                link.style.cursor = 'default';
            }
        }
    });
});
```

#### Стили

Страница включает кастомные стили для:
- Контейнера настроек (`.rmq-settings-container`)
- Панели статуса (`.rmq-status-panel`)
- Формы учетных данных (`.rmq-credentials-form`)
- Информационной панели (`.rmq-info-panel`)
- Адаптивности для мобильных устройств

#### Хранение настроек

**Модульные опции Bitrix24:**
- `imena.rmq` / `api_url` - URL сервера RabbitMQ API
- `imena.rmq` / `api_username` - Имя пользователя
- `imena.rmq` / `api_password` - Пароль (зашифрован)

**Чтение настроек:**
```php
$apiUrl = Option::get('imena.rmq', 'api_url', 'http://rmq.eg-holding.ru:15672/api/');
$username = Option::get('imena.rmq', 'api_username', 'admin');
$hasPassword = !empty(Option::get('imena.rmq', 'api_password'));
```

**Сохранение настроек:**
```php
Option::set('imena.rmq', 'api_url', $serverUrl);
Option::set('imena.rmq', 'api_username', $username);
Option::set('imena.rmq', 'api_password', $password);
```

---

## Меню навигации

### .left.menu.php

**Назначение:** Конфигурация левого меню навигации для модуля RabbitMQ

#### Описание

Файл определяет структуру меню, которое автоматически подхватывается компонентом `bitrix:menu` с шаблоном `top_horizontal` и отображается через `bitrix:main.interface.buttons` в шапке страницы.

#### Структура меню

```php
$aMenuLinks = [
    [
        'Очереди RabbitMQ',                    // Название пункта меню
        '/local/pages/imena/rmq/queues/',      // URL страницы
        [],                                     // Дополнительные параметры
        [
            'menu_item_id' => 'rmq_queues',    // ID пункта меню
            'class' => '',                      // CSS класс
        ],
        '',                                     // Дополнительные условия
    ],
    [
        'Настройки',
        '/local/pages/imena/rmq/settings/',
        [],
        [
            'menu_item_id' => 'rmq_settings',
            'class' => '',
        ],
        '',
    ],
];
```

#### Интеграция с Bitrix24

Меню автоматически отображается в шапке страницы через стандартный механизм Bitrix24:
- Компонент `bitrix:menu` с шаблоном `top_horizontal`
- Компонент `bitrix:main.interface.buttons`
- Автоматическое выделение активного пункта меню

---

## Архитектура страниц

### Общая структура

```
Страница (index.php)
    │
    ├─> Подключение bitrix/header.php
    ├─> Проверка модуля imena.rmq
    ├─> Загрузка локализации
    ├─> Установка заголовка страницы
    │
    ├─> Проверка настроек (для queues/)
    ├─> Отображение предупреждений (если нужно)
    │
    ├─> Подключение компонентов
    │   ├─> bitrix:ui.sidepanel.wrapper (для queues/)
    │   └─> imena.rmq:queue.list (для queues/)
    │
    ├─> JavaScript код
    │   ├─> Обработчики событий
    │   ├─> Кастомные функции
    │   └─> Интеграция с Grid
    │
    ├─> CSS стили
    │   ├─> Кастомные стили страницы
    │   └─> Адаптивность
    │
    └─> Подключение bitrix/footer.php
```

### Обработка ошибок

**Уровень 1: Проверка модуля**
```php
if (!Loader::includeModule('imena.rmq')) {
    ShowError('Модуль imena.rmq не установлен');
    require($_SERVER['DOCUMENT_ROOT'].'/bitrix/footer.php');
    die();
}
```

**Уровень 2: Проверка настроек**
```php
$apiUrl = \Bitrix\Main\Config\Option::get('imena.rmq', 'api_url', '');
$hasCredentials = !empty($apiUrl) && !empty(\Bitrix\Main\Config\Option::get('imena.rmq', 'api_password'));

if (!$hasCredentials) {
    // Отображение предупреждения
}
```

**Уровень 3: Обработка в компоненте**
```php
// В компоненте imena.rmq:queue.list
try {
    $apiClient = new RmqApiClient();
    $queuesData = $apiClient->getQueues($vhost);
} catch (RmqApiException $e) {
    $result['ERROR'] = $e->getMessage();
}
```

---

## Интеграция с компонентами

### Компонент imena.rmq:queue.list

**Использование на странице queues/index.php:**
```php
$APPLICATION->IncludeComponent(
    'bitrix:ui.sidepanel.wrapper',
    '',
    [
        'POPUP_COMPONENT_NAME' => 'imena.rmq:queue.list',
        'POPUP_COMPONENT_PARAMS' => [
            'VHOST' => '/',
            'SHOW_EMPTY_QUEUES' => 'Y',
            'CACHE_TIME' => 0,
            'CACHE_TYPE' => 'N',
        ],
    ]
);
```

**Параметры компонента:**
- `VHOST` - виртуальный хост RabbitMQ
- `SHOW_EMPTY_QUEUES` - показывать ли пустые очереди
- `GRID_ID` - идентификатор Grid (по умолчанию: `IMENA_RMQ_QUEUE_LIST`)
- `CACHE_TIME` - время кеширования
- `CACHE_TYPE` - тип кеширования

**AJAX действия компонента:**
- `purgeQueue` - очистка очереди от всех сообщений

---

## JavaScript функциональность

### Общие функции

**1. Обновление Grid:**
```javascript
if (BX.Imena && BX.Imena.RmqGrid && BX.Imena.RmqGrid.refreshGrid) {
    BX.Imena.RmqGrid.refreshGrid();
}
```

**2. Уведомления:**
```javascript
BX.UI.Notification.Center.notify({
    content: 'Сообщение',
    position: 'top-right',
    autoHideDelay: 3000,
    type: 'success' // или 'error', 'warning'
});
```

**3. Кастомные события:**
```javascript
// Подписка на событие
BX.addCustomEvent('onRabbitMQQueueSelected', function(queueName, queueData) {
    // Обработка события
});

// Генерация события
BX.onCustomEvent('onRabbitMQDataUpdated', []);
```

### Специфичные функции

**Для страницы queues/index.php:**
- Создание кнопки обновления в toolbar
- Обработка кликов на кнопку обновления
- Интеграция с Grid системой

**Для страницы settings/index.php:**
- Тестирование подключения
- Удаление учетных данных
- Предотвращение клика на активной кнопке меню

---

## Стили и оформление

### Общие стили

**Цветовая схема:**
- Успех: `#3bc8f5` (голубой)
- Ошибка: `#ff5752` (красный)
- Предупреждение: `#fff3cd` (желтый фон), `#856404` (текст)
- Информация: `#2fc6f6` (светло-голубой)

**Компоненты UI:**
- Использование стандартных классов Bitrix24 UI
- `.ui-btn`, `.ui-alert`, `.ui-form-row`, `.ui-ctl-element`
- Адаптивность через медиа-запросы

### Специфичные стили

**Для queues/index.php:**
- `.rmq-queue-list-wrapper` - обертка списка очередей
- `.rmq-type-*` - стили для типов очередей (classic, quorum, stream)
- `.rmq-state-*` - стили для статусов (success, warning, danger)
- `.rmq-messages-*` - стили для количества сообщений
- Анимация вращения иконки при загрузке

**Для settings/index.php:**
- `.rmq-settings-container` - контейнер настроек
- `.rmq-status-panel` - панель статуса подключения
- `.rmq-credentials-form` - форма учетных данных
- `.rmq-info-panel` - информационная панель

---

## Безопасность

### Защита от CSRF

**Использование bitrix_sessid:**
```php
// В формах
<?= bitrix_sessid_post() ?>

// Проверка в обработчиках
if ($_SERVER['REQUEST_METHOD'] === 'POST' && check_bitrix_sessid()) {
    // Обработка запроса
}
```

### Валидация входных данных

**Санитизация:**
```php
$serverUrl = trim($_POST['rmq_server_url'] ?? '');
$username = trim($_POST['rmq_username'] ?? '');
$password = trim($_POST['rmq_password'] ?? '');
```

**Экранирование вывода:**
```php
<?= htmlspecialcharsbx($apiUrl) ?>
<?= htmlspecialcharsbx($error) ?>
```

### Защита паролей

**Хранение:**
- Пароли сохраняются в модульных опциях Bitrix24
- Bitrix24 автоматически шифрует чувствительные данные
- Пароль не отображается в форме (только поле ввода)

**Проверка:**
```php
$hasPassword = !empty(Option::get('imena.rmq', 'api_password'));
// Проверка наличия без получения значения
```

### AJAX безопасность

**В компоненте:**
```php
public function configureActions()
{
    return [
        'purgeQueue' => [
            'prefilters' => [
                new ActionFilter\Authentication(),  // Требуется авторизация
                new ActionFilter\HttpMethod([ActionFilter\HttpMethod::METHOD_POST]),
                new ActionFilter\Csrf(),            // CSRF защита
            ]
        ],
    ];
}
```

---

## Разработка и расширение

### Добавление новой страницы

**1. Создать директорию:**
```bash
mkdir -p /local/pages/imena/rmq/new-page/
```

**2. Создать index.php:**
```php
<?php
require($_SERVER['DOCUMENT_ROOT'].'/bitrix/header.php');

use Bitrix\Main\Loader;
use Bitrix\Main\Localization\Loc;

Loader::includeModule('imena.rmq');
Loc::loadMessages(__FILE__);

$APPLICATION->SetTitle('Новая страница');

// Ваш код здесь

require($_SERVER['DOCUMENT_ROOT'].'/bitrix/footer.php');
```

**3. Добавить в меню (.left.menu.php):**
```php
$aMenuLinks[] = [
    'Новая страница',
    '/local/pages/imena/rmq/new-page/',
    [],
    [
        'menu_item_id' => 'rmq_new_page',
        'class' => '',
    ],
    '',
];
```

### Добавление нового JavaScript функционала

**1. Создать файл:**
```bash
/local/modules/imena.rmq/install/js/rmq/pages/custom.js
```

**2. Подключить на странице:**
```php
$this->addExternalJS('/local/modules/imena.rmq/install/js/rmq/pages/custom.js');
```

**3. Использовать:**
```javascript
BX.ready(function() {
    // Ваш код
});
```

### Добавление новых стилей

**1. Встроенные стили (в index.php):**
```php
<style>
.custom-style {
    /* Ваши стили */
}
</style>
```

**2. Внешний файл:**
```php
$this->addExternalCss('/local/modules/imena.rmq/install/css/rmq/pages/custom.css');
```

### Интеграция с другими модулями

**Использование API других модулей:**
```php
use Imena\Storm\Diagram\Diagram;
use Imena\Camunda\Process\ProcessInstance;

// Использование классов других модулей
```

**Передача данных между страницами:**
```php
// Через GET параметры
$queueName = $_GET['QUEUE'] ?? '';

// Через сессию
$_SESSION['RMQ_QUEUE_NAME'] = $queueName;

// Через модульные опции (для глобальных настроек)
Option::set('imena.rmq', 'last_selected_queue', $queueName);
```

---

## Примеры использования

### Пример 1: Базовая страница

```php
<?php
require($_SERVER['DOCUMENT_ROOT'].'/bitrix/header.php');

use Bitrix\Main\Loader;
use Bitrix\Main\Localization\Loc;

Loader::includeModule('imena.rmq');
Loc::loadMessages(__FILE__);

$APPLICATION->SetTitle('Моя страница');
?>

<div class="my-page">
    <h1>Заголовок страницы</h1>
    <!-- Контент -->
</div>

<?php require($_SERVER['DOCUMENT_ROOT'].'/bitrix/footer.php'); ?>
```

### Пример 2: Страница с AJAX действиями

```php
<?php
// В index.php
?>

<script>
BX.ready(function() {
    BX.ajax.runComponentAction('imena.rmq:queue.list', 'purgeQueue', {
        data: {
            queueName: 'my_queue',
            vhost: '/'
        }
    }).then(function(response) {
        if (response.data.success) {
            BX.UI.Notification.Center.notify({
                content: response.data.message,
                autoHideDelay: 3000
            });
        }
    });
});
</script>
```

### Пример 3: Страница с формой

```php
<?php
// Обработка POST
if ($_SERVER['REQUEST_METHOD'] === 'POST' && check_bitrix_sessid()) {
    $action = $_POST['action'] ?? '';
    
    if ($action === 'save') {
        // Сохранение данных
        Option::set('imena.rmq', 'my_setting', $_POST['value']);
        LocalRedirect($APPLICATION->GetCurPage());
    }
}

// Получение текущего значения
$value = Option::get('imena.rmq', 'my_setting', '');
?>

<form method="post">
    <?= bitrix_sessid_post() ?>
    <input type="hidden" name="action" value="save">
    <input type="text" name="value" value="<?= htmlspecialcharsbx($value) ?>">
    <button type="submit">Сохранить</button>
</form>
```

---

## Требования

- **Bitrix24:** 20.0.0+
- **PHP:** 8.0+
- **Модуль:** `imena.rmq` должен быть установлен
- **RabbitMQ:** Management API должен быть доступен

---

## Отладка

### Логирование

**В PHP:**
```php
error_log('[RMQ Page] Debug: ' . print_r($data, true));
```

**В JavaScript:**
```javascript
console.log('[RMQ Page] Debug:', data);
```

### Проверка AJAX запросов

**В консоли браузера:**
```javascript
// Перехват AJAX запросов
BX.ajax.runComponentAction = (function(original) {
    return function(component, action, params) {
        console.log('AJAX Request:', component, action, params);
        return original.apply(this, arguments);
    };
})(BX.ajax.runComponentAction);
```

### Проверка настроек

**В PHP:**
```php
$apiUrl = Option::get('imena.rmq', 'api_url', '');
$username = Option::get('imena.rmq', 'api_username', '');
$hasPassword = !empty(Option::get('imena.rmq', 'api_password'));

var_dump([
    'api_url' => $apiUrl,
    'username' => $username,
    'has_password' => $hasPassword
]);
```

---

## Известные ограничения

1. **Производительность:**
   - При большом количестве очередей (>1000) может быть медленная загрузка
   - Рекомендуется использовать фильтрацию по vhost

2. **Кеширование:**
   - Страница queues/ не использует кеширование для real-time данных
   - Для production рекомендуется добавить кеширование с TTL 30 секунд

3. **Безопасность:**
   - Пароли хранятся в модульных опциях (шифруются Bitrix24)
   - Рекомендуется использовать HTTPS для RabbitMQ API

---

## История версий

### Версия 1.0+ (25.01.2025)

**Основные возможности:**
- ✅ Страница списка очередей (queues/index.php)
- ✅ Страница настроек подключения (settings/index.php)
- ✅ Навигационное меню (.left.menu.php)
- ✅ Интеграция с компонентом imena.rmq:queue.list
- ✅ JavaScript функциональность для обновления данных
- ✅ Обработка ошибок и предупреждений

---

## Поддержка

**Автор:** #vlikhobabin@gmail.com

**Документация:**
- Модуль: `/local/modules/imena.rmq/README.md`
- Компоненты: `/local/components/imena.rmq/README.md`
- Grid система: `/local/modules/imena.rmq/lib/Queue/Grid/README.md`

**Логи:**
- Страницы: `error_log('[RMQ Page] ...')`
- Компоненты: `error_log('[RMQ Component] ...')`
- API: через `RmqApiClient`

---

*Последнее обновление: 25.01.2025*

