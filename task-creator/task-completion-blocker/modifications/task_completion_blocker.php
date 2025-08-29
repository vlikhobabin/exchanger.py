<?php
/**
 * Обработчик событий для блокировки завершения задач без ответа на обязательный вопрос
 * 
 * ВЕРСИЯ: 1.1
 * ДАТА: 2025-01-12
 * АВТОР: Система автоматизации задач
 * 
 * Этот файл должен быть подключен в /local/php_interface/init.php
 */

// Регистрируем обработчик события только если система Bitrix24 инициализирована
if (function_exists('AddEventHandler') && function_exists('AddMessage2Log')) {
    AddEventHandler("tasks", "OnBeforeTaskUpdate", "blockTaskCompletionWithoutAnswer");
    
    // Логируем успешную регистрацию
    safeLog(
        "Task completion blocker event handler registered successfully. Version: 1.1"
    );
} else {
    // Если система не инициализирована, регистрируем обработчик через отложенный вызов
    if (function_exists('AddEventHandler')) {
        AddEventHandler("main", "OnEpilog", function() {
            static $registered = false;
            if (!$registered && function_exists('AddEventHandler')) {
                AddEventHandler("tasks", "OnBeforeTaskUpdate", "blockTaskCompletionWithoutAnswer");
                $registered = true;
                safeLog(
                    "Task completion blocker event handler registered via OnEpilog. Version: 1.1"
                );
            }
        });
    }
}

/**
 * Безопасное логирование с проверкой доступности функции
 * 
 * @param string $message Сообщение для логирования
 * @param string $category Категория лога
 */
function safeLog($message, $category = 'tasks_completion_blocker')
{
    if (function_exists('AddMessage2Log')) {
        AddMessage2Log($message, $category);
    }
}

/**
 * Блокирует завершение задачи без ответа на обязательный вопрос
 * 
 * @param int $taskId ID задачи
 * @param array &$arFields Поля для обновления
 * @param array &$arTaskCopy Копия данных задачи
 * @return void
 * @throws \Bitrix\Tasks\ActionFailedException
 */
function blockTaskCompletionWithoutAnswer($taskId, &$arFields, &$arTaskCopy)
{
    // Логируем вызов для отладки
    safeLog(
        "blockTaskCompletionWithoutAnswer called for task #{$taskId}. Fields: " . print_r($arFields, true)
    );
    
    // Проверяем, меняется ли статус задачи на "Завершена"
    if (!isset($arFields['STATUS']) || $arFields['STATUS'] != CTasks::STATE_COMPLETED) {
        safeLog(
            "Task #{$taskId}: Status not changing to completed. Current status: " . ($arFields['STATUS'] ?? 'not set')
        );
        return; // Не завершение - пропускаем
    }
    
    // Подключаем модуль задач
    if (!CModule::IncludeModule('tasks')) {
        safeLog(
            "Task #{$taskId}: Cannot include tasks module"
        );
        return;
    }
    
    try {
        // Получаем текущие данные задачи
        $rsTask = CTasks::GetByID($taskId);
        if (!$arTask = $rsTask->GetNext()) {
            safeLog(
                "Task #{$taskId}: Cannot get task data"
            );
            return;
        }
        
        safeLog(
            "Task #{$taskId}: Retrieved task data. UF_RESULT_EXPECTED: " . ($arTask['UF_RESULT_EXPECTED'] ?? 'not set') . 
            ", UF_RESULT_ANSWER: " . ($arTask['UF_RESULT_ANSWER'] ?? 'not set')
        );
        
        // Проверяем наличие флага "Ожидается результат"
        if (empty($arTask['UF_RESULT_EXPECTED']) || $arTask['UF_RESULT_EXPECTED'] != 1) {
            safeLog(
                "Task #{$taskId}: Result not expected (UF_RESULT_EXPECTED = " . ($arTask['UF_RESULT_EXPECTED'] ?? 'null') . ")"
            );
            return; // Ответ не требуется
        }
        
        // Проверяем наличие ответа
        $resultAnswer = $arTask['UF_RESULT_ANSWER'] ?? null;
        
        // Считаем пустыми значения: null, '', '0', 0, false
        if (empty($resultAnswer) || $resultAnswer === '0' || $resultAnswer === 0) {
            
            // Получаем информацию о пользователе для логов
            $currentUserId = isset($GLOBALS['USER']) ? $GLOBALS['USER']->GetID() : 'unknown';
            
            // Логируем попытку
            safeLog(
                "BLOCKING task #{$taskId} completion without answer. " .
                "User: {$currentUserId}, " .
                "UF_RESULT_EXPECTED: " . ($arTask['UF_RESULT_EXPECTED'] ?? 'null') . ", " .
                "UF_RESULT_ANSWER: " . ($resultAnswer ?? 'null')
            );
            
            // Получаем текст вопроса для более информативного сообщения
            $questionText = $arTask['UF_RESULT_QUESTION'] ?? 'Требуется ответ на вопрос';
            
            // Блокируем завершение с подробным сообщением
            $errorMessage = "⚠️ Задача не может быть завершена без ответа на обязательный вопрос!\n\n" .
                           "Вопрос: {$questionText}\n\n" .
                           "Для завершения задачи необходимо:\n" .
                           "1. Открыть форму редактирования задачи\n" .
                           "2. Заполнить поле 'Результат ответа' (выбрать 'Да' или 'Нет')\n" .
                           "3. Сохранить изменения\n" .
                           "4. Затем завершить задачу";
            
            // Используем исключение для блокировки завершения
            if (class_exists('\Bitrix\Tasks\ActionFailedException')) {
                throw new \Bitrix\Tasks\ActionFailedException($errorMessage);
            } else {
                // Fallback для старых версий
                throw new Exception($errorMessage);
            }
        }
        
        // Если дошли до этого момента - все в порядке, разрешаем завершение
        safeLog(
            "Task #{$taskId}: Completion allowed. Answer provided: " . $resultAnswer
        );
        
    } catch (\Bitrix\Tasks\ActionFailedException $e) {
        // Перебрасываем исключение блокировки
        throw $e;
    } catch (Exception $e) {
        // Логируем неожиданные ошибки
        safeLog(
            "Task #{$taskId}: Unexpected error in blockTaskCompletionWithoutAnswer: " . $e->getMessage()
        );
        
        // В случае ошибки блокируем завершение из предосторожности
        $errorMessage = "⚠️ Ошибка при проверке задачи. Завершение заблокировано из предосторожности. " .
                       "Обратитесь к администратору системы.";
        
        if (class_exists('\Bitrix\Tasks\ActionFailedException')) {
            throw new \Bitrix\Tasks\ActionFailedException($errorMessage);
        } else {
            throw new Exception($errorMessage);
        }
    }
}

/**
 * Дополнительная функция для тестирования блокировки
 * Можно вызывать из консоли или админки для проверки
 */
function testTaskCompletionBlocker()
{
    if (!CModule::IncludeModule('tasks')) {
        return "ERROR: Cannot include tasks module";
    }
    
    $results = [];
    
    // Создаем тестовую задачу с обязательным вопросом
    $testTaskData = [
        'TITLE' => 'ТЕСТ: Задача с обязательным вопросом',
        'DESCRIPTION' => 'Тестовая задача для проверки блокировки завершения',
        'RESPONSIBLE_ID' => 1,
        'UF_RESULT_EXPECTED' => 1,
        'UF_RESULT_QUESTION' => 'Тестовый вопрос: Выполнена ли задача правильно?',
        'UF_RESULT_ANSWER' => '' // Пустой ответ
    ];
    
    try {
        $taskId = CTasks::Add($testTaskData, 1);
        
        if ($taskId) {
            $results[] = "✅ Тестовая задача создана: #{$taskId}";
            
            try {
                // Пытаемся завершить без ответа
                CTasks::Update($taskId, ['STATUS' => CTasks::STATE_COMPLETED], 1);
                $results[] = "❌ ОШИБКА: Задача завершена без ответа! Блокировка не работает.";
            } catch (\Bitrix\Tasks\ActionFailedException $e) {
                $results[] = "✅ УСПЕХ: Завершение заблокировано корректно";
                $results[] = "   Сообщение: " . $e->getMessage();
            } catch (Exception $e) {
                $results[] = "✅ УСПЕХ: Завершение заблокировано (fallback exception)";
                $results[] = "   Сообщение: " . $e->getMessage();
            }
            
            // Теперь тестируем с заполненным ответом
            try {
                CTasks::Update($taskId, ['UF_RESULT_ANSWER' => 26], 1); // 26 = "ДА"
                CTasks::Update($taskId, ['STATUS' => CTasks::STATE_COMPLETED], 1);
                $results[] = "✅ УСПЕХ: Задача завершена после заполнения ответа";
            } catch (Exception $e) {
                $results[] = "❌ ОШИБКА: Не удалось завершить задачу даже с ответом: " . $e->getMessage();
            }
            
            // Удаляем тестовую задачу
            CTasks::Delete($taskId);
            $results[] = "🗑️ Тестовая задача удалена";
            
        } else {
            $results[] = "❌ ОШИБКА: Не удалось создать тестовую задачу";
        }
        
    } catch (Exception $e) {
        $results[] = "❌ ОШИБКА при создании тестовой задачи: " . $e->getMessage();
    }
    
    return implode("\n", $results);
}

// Логируем факт подключения файла
safeLog(
    "Task completion blocker loaded successfully. Version: 1.1"
);

?> 