<?php
/**
 * JavaScript connector for task modifier in Bitrix24 template
 *
 * This file safely connects to header.php template
 * and loads JavaScript task modifier
 *
 * VERSION: 1.3 (fixed encoding and logic)
 * DATE: 2025-01-15
 * AUTHOR: Task automation system
 */

// Check if we are in Bitrix24 context
if (!defined('B_PROLOG_INCLUDED') || B_PROLOG_INCLUDED !== true) {
    // If no Bitrix24 context, check for $APPLICATION
    if (!isset($APPLICATION) || !is_object($APPLICATION)) {
        return;
    }
}

// Simple and safe path definition
$templateFolder = '/local/templates/bitrix24/';

// Add JavaScript file for task modifier
if (isset($APPLICATION) && is_object($APPLICATION) && method_exists($APPLICATION, 'AddHeadScript')) {
    $APPLICATION->AddHeadScript($templateFolder . 'assets/js/enhanced_task_modifier.js');
    
    // Log connection if available
    if (function_exists('AddMessage2Log')) {
        AddMessage2Log(
            "Task modifier JavaScript connector loaded successfully. Template: " . $templateFolder,
            "task_modifier_connector"
        );
    }
}
?> 