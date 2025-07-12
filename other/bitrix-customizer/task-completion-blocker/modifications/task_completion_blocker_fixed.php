<?php
/**
 * Event handler for blocking task completion without required answer
 * 
 * VERSION: 1.1
 * DATE: 2025-01-12
 * AUTHOR: Task automation system
 * 
 * This file should be included in /local/php_interface/init.php
 */

// Register event handler only if Bitrix24 system is initialized
if (function_exists('AddEventHandler') && function_exists('AddMessage2Log')) {
    AddEventHandler("tasks", "OnBeforeTaskUpdate", "blockTaskCompletionWithoutAnswer");
    
    // Log successful registration
    safeLog(
        "Task completion blocker event handler registered successfully. Version: 1.1"
    );
} else {
    // If system is not initialized, register handler through deferred call
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
 * Safe logging with function availability check
 * 
 * @param string $message Message to log
 * @param string $category Log category
 */
function safeLog($message, $category = 'tasks_completion_blocker')
{
    if (function_exists('AddMessage2Log')) {
        AddMessage2Log($message, $category);
    }
}

/**
 * Blocks task completion without required answer
 * 
 * @param int $taskId Task ID
 * @param array &$arFields Fields for update
 * @param array &$arTaskCopy Copy of task data
 * @return void
 * @throws \Bitrix\Tasks\ActionFailedException
 */
function blockTaskCompletionWithoutAnswer($taskId, &$arFields, &$arTaskCopy)
{
    // Log call for debugging
    safeLog(
        "blockTaskCompletionWithoutAnswer called for task #{$taskId}. Fields: " . print_r($arFields, true)
    );
    
    // Check if task status is changing to "Completed"
    if (!isset($arFields['STATUS']) || $arFields['STATUS'] != CTasks::STATE_COMPLETED) {
        safeLog(
            "Task #{$taskId}: Status not changing to completed. Current status: " . ($arFields['STATUS'] ?? 'not set')
        );
        return; // Not completion - skip
    }
    
    // Include tasks module
    if (!CModule::IncludeModule('tasks')) {
        safeLog(
            "Task #{$taskId}: Cannot include tasks module"
        );
        return;
    }
    
    try {
        // Get current task data
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
        
        // Check if "Result expected" flag is set
        if (empty($arTask['UF_RESULT_EXPECTED']) || $arTask['UF_RESULT_EXPECTED'] != 1) {
            safeLog(
                "Task #{$taskId}: Result not expected (UF_RESULT_EXPECTED = " . ($arTask['UF_RESULT_EXPECTED'] ?? 'null') . ")"
            );
            return; // Answer not required
        }
        
        // Check if answer is provided
        $resultAnswer = $arTask['UF_RESULT_ANSWER'] ?? null;
        
        // Consider empty values: null, '', '0', 0, false
        if (empty($resultAnswer) || $resultAnswer === '0' || $resultAnswer === 0) {
            
            // Get user info for logs
            $currentUserId = isset($GLOBALS['USER']) ? $GLOBALS['USER']->GetID() : 'unknown';
            
            // Log attempt
            safeLog(
                "BLOCKING task #{$taskId} completion without answer. " .
                "User: {$currentUserId}, " .
                "UF_RESULT_EXPECTED: " . ($arTask['UF_RESULT_EXPECTED'] ?? 'null') . ", " .
                "UF_RESULT_ANSWER: " . ($resultAnswer ?? 'null')
            );
            
            // Get question text for more informative message
            $questionText = $arTask['UF_RESULT_QUESTION'] ?? 'Answer to question required';
            
            // Block completion with detailed message
            $errorMessage = "Task cannot be completed without answer to required question!\n\n" .
                           "Question: {$questionText}\n\n" .
                           "To complete the task:\n" .
                           "1. Open task edit form\n" .
                           "2. Fill 'Result answer' field (select 'Yes' or 'No')\n" .
                           "3. Save changes\n" .
                           "4. Then complete the task";
            
            // Use exception to block completion
            if (class_exists('\Bitrix\Tasks\ActionFailedException')) {
                throw new \Bitrix\Tasks\ActionFailedException($errorMessage);
            } else {
                // Fallback for older versions
                throw new Exception($errorMessage);
            }
        }
        
        // If we got here - everything is fine, allow completion
        safeLog(
            "Task #{$taskId}: Completion allowed. Answer provided: " . $resultAnswer
        );
        
    } catch (\Bitrix\Tasks\ActionFailedException $e) {
        // Re-throw blocking exception
        throw $e;
    } catch (Exception $e) {
        // Log unexpected errors
        safeLog(
            "Task #{$taskId}: Unexpected error in blockTaskCompletionWithoutAnswer: " . $e->getMessage()
        );
        
        // Block completion as precaution on error
        $errorMessage = "Error while checking task. Completion blocked as precaution. " .
                       "Contact system administrator.";
        
        if (class_exists('\Bitrix\Tasks\ActionFailedException')) {
            throw new \Bitrix\Tasks\ActionFailedException($errorMessage);
        } else {
            throw new Exception($errorMessage);
        }
    }
}

/**
 * Additional function for testing blocker
 * Can be called from console or admin panel for testing
 */
function testTaskCompletionBlocker()
{
    if (!CModule::IncludeModule('tasks')) {
        return "ERROR: Cannot include tasks module";
    }
    
    $results = [];
    
    // Create test task with required question
    $testTaskData = [
        'TITLE' => 'TEST: Task with required question',
        'DESCRIPTION' => 'Test task for completion blocking check',
        'RESPONSIBLE_ID' => 1,
        'UF_RESULT_EXPECTED' => 1,
        'UF_RESULT_QUESTION' => 'Test question: Is task completed correctly?',
        'UF_RESULT_ANSWER' => '' // Empty answer
    ];
    
    try {
        $taskId = CTasks::Add($testTaskData, 1);
        
        if ($taskId) {
            $results[] = "Test task created: #{$taskId}";
            
            try {
                // Try to complete without answer
                CTasks::Update($taskId, ['STATUS' => CTasks::STATE_COMPLETED], 1);
                $results[] = "ERROR: Task completed without answer! Blocking not working.";
            } catch (\Bitrix\Tasks\ActionFailedException $e) {
                $results[] = "SUCCESS: Completion blocked correctly";
                $results[] = "   Message: " . $e->getMessage();
            } catch (Exception $e) {
                $results[] = "SUCCESS: Completion blocked (fallback exception)";
                $results[] = "   Message: " . $e->getMessage();
            }
            
            // Now test with filled answer
            try {
                CTasks::Update($taskId, ['UF_RESULT_ANSWER' => 26], 1); // 26 = "YES"
                CTasks::Update($taskId, ['STATUS' => CTasks::STATE_COMPLETED], 1);
                $results[] = "SUCCESS: Task completed after filling answer";
            } catch (Exception $e) {
                $results[] = "ERROR: Could not complete task even with answer: " . $e->getMessage();
            }
            
            // Delete test task
            CTasks::Delete($taskId);
            $results[] = "Test task deleted";
            
        } else {
            $results[] = "ERROR: Could not create test task";
        }
        
    } catch (Exception $e) {
        $results[] = "ERROR while creating test task: " . $e->getMessage();
    }
    
    return implode("\n", $results);
}

// Log fact of file inclusion
safeLog(
    "Task completion blocker loaded successfully. Version: 1.1"
);

?> 