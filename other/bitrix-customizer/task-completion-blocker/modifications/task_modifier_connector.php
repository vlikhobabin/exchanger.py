<?php
/**
 * Коннектор для подключения модификатора задач к шаблону Bitrix24
 *
 * Этот файл безопасно подключается к header.php шаблона
 * и обеспечивает загрузку JavaScript модификатора задач
 *
 * ВЕРСИЯ: 1.2 (исправлена проблема с $this)
 * ДАТА: 2025-01-15
 * АВТОР: Система автоматизации задач
 */

// Проверяем, что мы находимся в контексте Bitrix24
if (!defined('B_PROLOG_INCLUDED') || B_PROLOG_INCLUDED !== true) {
    // Если нет контекста Bitrix24, проверяем наличие $APPLICATION
    if (!isset($APPLICATION) || !is_object($APPLICATION)) {
        return;
    }
}

// Безопасное определение пути к шаблону
$templateFolder = '/local/templates/bitrix24/';
if (defined('SITE_TEMPLATE_PATH')) {
    $templateFolder = SITE_TEMPLATE_PATH . '/';
} elseif (isset($this) && is_object($this) && method_exists($this, 'GetFolder')) {
    $templateFolder = $this->GetFolder();
}

// Проверяем, что мы находимся в правильном шаблоне
if (strpos($templateFolder, 'bitrix24') === false) {
    return; // Не наш шаблон
}

// Подключаем JavaScript файл модификатора задач
$APPLICATION->AddHeadScript($templateFolder . 'assets/js/enhanced_task_modifier.js');

// Логируем подключение (если доступно)
if (function_exists('AddMessage2Log')) {
    AddMessage2Log(
        "Task modifier JavaScript connector loaded successfully. Template: " . $templateFolder,
        "task_modifier_connector"
    );
}
?> 