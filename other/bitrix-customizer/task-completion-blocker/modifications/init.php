<?php
/**
 * Файл инициализации локальных модификаций Bitrix24
 * 
 * Этот файл должен быть размещен в /local/php_interface/init.php
 * 
 * ВЕРСИЯ: 1.2 (БЕЗОПАСНАЯ ВЕРСИЯ)
 * ДАТА: 2025-01-15
 */

// Подключаем обработчик блокировки завершения задач
// ИСПРАВЛЕНО: Теперь безопасно включен с улучшенной системой резервного копирования
require_once(__DIR__ . '/task_completion_blocker.php');

// Логируем факт подключения только если функция доступна
if (function_exists('AddMessage2Log')) {
    AddMessage2Log(
        "Local init.php loaded successfully. Task completion blocker ENABLED. Version: 1.2",
        "local_init"
    );
}

?> 