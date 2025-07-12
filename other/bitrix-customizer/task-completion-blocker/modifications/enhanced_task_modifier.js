/**
 * РАСШИРЕННЫЙ МОДИФИКАТОР ЗАДАЧ - ВЕРСИЯ 2.0
 * 
 * Интегрирован с PHP обработчиком событий для блокировки завершения задач
 * без ответа на обязательный вопрос.
 * 
 * Изменения в версии 2.0:
 * - Улучшена интеграция с серверной логикой
 * - Добавлена обработка ошибок от сервера
 * - Улучшен UX при блокировке завершения
 * - Добавлена предварительная проверка полей
 * 
 * ДАТА: 2025-01-12
 */
(function() {
    'use strict';

    const CONFIG = {
        CHECK_INTERVAL: 300,
        EXPECTED_FIELD_VALUES: {
            YES: 26,
            NO: 27
        },
        SELECTORS: {
            IFRAME: 'iframe.side-panel-iframe[src*="/tasks/task/view/"]',
            COMPLETE_BUTTON: 'span[data-action="COMPLETE"]',
            FIELD_ROWS: '.task-detail-property-name'
        }
    };

    let taskCheckInterval = null;
    let lastProcessedTask = null;

    /**
     * Основная функция поиска и модификации задач
     */
    function findAndModifyTask() {
        const iframe = document.querySelector(CONFIG.SELECTORS.IFRAME);
        if (!iframe) return;

        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        if (iframeDoc.readyState !== 'complete') return;

        const completeButton = iframeDoc.querySelector(CONFIG.SELECTORS.COMPLETE_BUTTON);
        if (!completeButton || completeButton.dataset.customized) {
            return;
        }

        const taskId = getTaskIdFromUrl(iframe.src);
        if (!taskId) return;

        // Избегаем повторной обработки той же задачи
        if (lastProcessedTask === taskId) return;
        lastProcessedTask = taskId;

        console.log(`[TaskModifier] Processing task #${taskId}`);

        // Проверяем, требуется ли результат для этой задачи
        const taskData = analyzeTaskFields(iframeDoc);
        
        if (!taskData.resultExpected) {
            console.log(`[TaskModifier] Task #${taskId} - result not expected`);
            return;
        }

        // Модифицируем интерфейс
        modifyTaskInterface(completeButton, taskId, taskData, iframe.contentWindow);
    }

    /**
     * Анализирует поля задачи для определения необходимости ответа
     */
    function analyzeTaskFields(iframeDoc) {
        const taskData = {
            resultExpected: false,
            resultAnswer: null,
            questionText: 'Вы уверены в результате?'
        };

        // Проверяем поле "Ожидается результат"
        const expectedFieldRow = findFieldRowByLabel(iframeDoc, 'Ожидается результат');
        if (expectedFieldRow) {
            const expectedValueNode = expectedFieldRow.querySelector('.fields.boolean.field-item');
            if (expectedValueNode && expectedValueNode.textContent.trim().toLowerCase() === 'да') {
                taskData.resultExpected = true;
            }
        }

        // Получаем текст вопроса
        const questionRow = findFieldRowByLabel(iframeDoc, 'Вопрос на результат');
        if (questionRow) {
            const questionNode = questionRow.querySelector('.fields.string.field-item');
            if (questionNode && questionNode.textContent.trim()) {
                taskData.questionText = questionNode.textContent.trim();
            }
        }

        // Проверяем текущий ответ
        const answerRow = findFieldRowByLabel(iframeDoc, 'Результат ответа');
        if (answerRow) {
            const answerNode = answerRow.querySelector('.fields.list.field-item');
            if (answerNode && answerNode.textContent.trim()) {
                taskData.resultAnswer = answerNode.textContent.trim();
            }
        }

        return taskData;
    }

    /**
     * Модифицирует интерфейс задачи
     */
    function modifyTaskInterface(completeButton, taskId, taskData, targetWindow) {
        completeButton.dataset.customized = 'true';
        
        // Меняем текст кнопки
        const originalText = completeButton.innerText;
        completeButton.innerText = 'Завершить с результатом';
        
        // Добавляем стили для выделения
        completeButton.style.fontWeight = 'bold';
        completeButton.style.backgroundColor = '#FFA500';
        completeButton.style.color = 'white';

        // Заменяем обработчик клика
        const originalHandler = completeButton.onclick;
        completeButton.onclick = null;

        completeButton.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            
            console.log(`[TaskModifier] Complete button clicked for task #${taskId}`);
            
            // Проверяем, заполнен ли ответ
            if (taskData.resultAnswer && taskData.resultAnswer !== 'Не задано') {
                console.log(`[TaskModifier] Answer already provided: ${taskData.resultAnswer}`);
                // Ответ уже дан, можно завершать обычным способом
                proceedWithNormalCompletion(taskId, targetWindow);
            } else {
                // Показываем диалог для получения ответа
                showResultModal(taskId, taskData.questionText, targetWindow);
            }
        });

        console.log(`[TaskModifier] Task #${taskId} interface modified successfully`);
    }

    /**
     * Продолжает обычное завершение задачи
     */
    function proceedWithNormalCompletion(taskId, targetWindow) {
        console.log(`[TaskModifier] Proceeding with normal completion for task #${taskId}`);
        
        targetWindow.BX.showWait();
        
        // Завершаем задачу
        targetWindow.BX.ajax.runComponentAction('bitrix:tasks.task', 'complete', {
            mode: 'class',
            data: { taskId: taskId }
        }).then(function() {
            console.log(`[TaskModifier] Task #${taskId} completed successfully`);
            // Закрываем слайдер
            if (top.BX.SidePanel && top.BX.SidePanel.Instance) {
                top.BX.SidePanel.Instance.close();
            }
            targetWindow.BX.closeWait();
        }).catch(function(response) {
            console.error(`[TaskModifier] Error completing task #${taskId}:`, response);
            targetWindow.BX.closeWait();
            
            // Показываем ошибку от сервера
            let errorMessage = 'Произошла ошибка при завершении задачи.';
            if (response.errors && response.errors.length > 0) {
                errorMessage = response.errors[0].message || errorMessage;
            }
            
            showErrorDialog(errorMessage, targetWindow);
        });
    }

    /**
     * Показывает диалог для получения ответа на вопрос
     */
    function showResultModal(taskId, questionText, targetWindow) {
        console.log(`[TaskModifier] Showing result modal for task #${taskId}`);
        
        targetWindow.BX.UI.Dialogs.MessageBox.show({
            title: 'Требуется ответ на вопрос:',
            message: targetWindow.BX.util.htmlspecialchars(questionText),
            modal: true,
            buttons: [
                new targetWindow.BX.UI.Button({
                    text: 'Да',
                    color: targetWindow.BX.UI.Button.Color.SUCCESS,
                    onclick: (button) => handleAnswer(taskId, true, button.getContext(), targetWindow)
                }),
                new targetWindow.BX.UI.Button({
                    text: 'Нет',
                    color: targetWindow.BX.UI.Button.Color.DANGER,
                    onclick: (button) => handleAnswer(taskId, false, button.getContext(), targetWindow)
                }),
                new targetWindow.BX.UI.Button({
                    text: 'Отмена',
                    color: targetWindow.BX.UI.Button.Color.LINK,
                    onclick: (button) => {
                        console.log(`[TaskModifier] User cancelled answer for task #${taskId}`);
                        button.getContext().close();
                    }
                })
            ]
        });
    }

    /**
     * Обрабатывает ответ пользователя
     */
    function handleAnswer(taskId, answer, messageBox, targetWindow) {
        console.log(`[TaskModifier] Processing answer for task #${taskId}: ${answer ? 'YES' : 'NO'}`);
        
        messageBox.close();
        targetWindow.BX.showWait();

        const answerValue = answer ? CONFIG.EXPECTED_FIELD_VALUES.YES : CONFIG.EXPECTED_FIELD_VALUES.NO;

        // Шаг 1: Обновляем пользовательское поле
        targetWindow.BX.ajax.runComponentAction('bitrix:tasks.task', 'legacyUpdate', {
            mode: 'class',
            data: {
                taskId: taskId,
                data: { 'UF_RESULT_ANSWER': answerValue }
            }
        }).then(function() {
            console.log(`[TaskModifier] Answer saved for task #${taskId}`);
            
            // Шаг 2: Завершаем задачу
            return targetWindow.BX.ajax.runComponentAction('bitrix:tasks.task', 'complete', {
                mode: 'class',
                data: { taskId: taskId }
            });
        }).then(function() {
            console.log(`[TaskModifier] Task #${taskId} completed successfully with answer`);
            
            // Шаг 3: Закрываем слайдер
            if (top.BX.SidePanel && top.BX.SidePanel.Instance) {
                top.BX.SidePanel.Instance.close();
            }
            targetWindow.BX.closeWait();
            
            // Показываем успешное сообщение
            if (top.BX.UI.Notification) {
                top.BX.UI.Notification.Center.notify({
                    content: `Задача #${taskId} успешно завершена с ответом: ${answer ? 'Да' : 'Нет'}`,
                    position: 'top-right',
                    autoHideDelay: 3000
                });
            }
            
        }).catch(function(response) {
            console.error(`[TaskModifier] Error saving answer or completing task #${taskId}:`, response);
            targetWindow.BX.closeWait();
            
            // Показываем ошибку от сервера
            let errorMessage = 'Произошла ошибка при сохранении ответа или завершении задачи.';
            if (response.errors && response.errors.length > 0) {
                errorMessage = response.errors[0].message || errorMessage;
            }
            
            showErrorDialog(errorMessage, targetWindow);
        });
    }

    /**
     * Показывает диалог с ошибкой
     */
    function showErrorDialog(message, targetWindow) {
        targetWindow.BX.UI.Dialogs.MessageBox.alert(
            'Ошибка',
            message,
            function() {
                // Можно добавить дополнительные действия при закрытии
            }
        );
    }

    /**
     * Находит строку с полем по метке
     */
    function findFieldRowByLabel(doc, labelText) {
        const cells = doc.querySelectorAll(CONFIG.SELECTORS.FIELD_ROWS);
        for (let i = 0; i < cells.length; i++) {
            if (cells[i].textContent.trim() === labelText) {
                return cells[i].parentNode;
            }
        }
        return null;
    }

    /**
     * Извлекает ID задачи из URL
     */
    function getTaskIdFromUrl(url) {
        const match = url.match(/\/tasks\/task\/view\/(\d+)\//);
        return match ? parseInt(match[1], 10) : null;
    }

    /**
     * Инициализация модификатора
     */
    function init() {
        console.log('[TaskModifier] Enhanced Task Modifier v2.0 initialized');
        
        // Запускаем проверку задач
        taskCheckInterval = setInterval(findAndModifyTask, CONFIG.CHECK_INTERVAL);
        
        // Сбрасываем состояние при изменении URL
        let currentUrl = window.location.href;
        setInterval(function() {
            if (window.location.href !== currentUrl) {
                currentUrl = window.location.href;
                lastProcessedTask = null;
                console.log('[TaskModifier] URL changed, resetting state');
            }
        }, 1000);
    }

    /**
     * Очистка при выгрузке
     */
    function cleanup() {
        if (taskCheckInterval) {
            clearInterval(taskCheckInterval);
            taskCheckInterval = null;
        }
        console.log('[TaskModifier] Cleanup completed');
    }

    // Инициализация
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Очистка при выгрузке страницы
    window.addEventListener('beforeunload', cleanup);

})(); 