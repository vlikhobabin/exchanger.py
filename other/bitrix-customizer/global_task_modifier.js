/**
 * ВЕРСИЯ 12: Исправлена работа с полем UF_RESULT_ANSWER типа "Список".
 * Теперь используются ID из списка: 26 = "ДА", 27 = "НЕТ".
 */
(function() {
    'use strict';

    let taskCheckInterval = null;

    function findAndModifyTask() {
        const iframe = document.querySelector('iframe.side-panel-iframe[src*="/tasks/task/view/"]');
        if (!iframe) return;

        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        if (iframeDoc.readyState !== 'complete') return;

        const completeButton = iframeDoc.querySelector('span[data-action="COMPLETE"]');
        if (!completeButton || completeButton.dataset.customized) {
            return;
        }

        completeButton.dataset.customized = 'true';

        const expectedFieldRow = findFieldRowByLabel(iframeDoc, 'Ожидается результат');
        if (!expectedFieldRow) return;

        const expectedValueNode = expectedFieldRow.querySelector('.fields.boolean.field-item');
        if (!expectedValueNode || expectedValueNode.textContent.trim().toLowerCase() !== 'да') {
            return;
        }

        const questionRow = findFieldRowByLabel(iframeDoc, 'Вопрос на результат');
        const questionText = questionRow ? questionRow.querySelector('.fields.string.field-item').textContent.trim() : 'Вы уверены?';
        
        const taskId = getTaskIdFromUrl(iframe.src);
        if (!taskId) return;

        completeButton.innerText = 'Завершить с результатом';

        completeButton.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            showResultModal(taskId, questionText, iframe.contentWindow);
        });
    }

    function showResultModal(taskId, questionText, targetWindow) {
        targetWindow.BX.UI.Dialogs.MessageBox.show({
            title: 'Требуется результат',
            message: targetWindow.BX.util.htmlspecialchars(questionText),
            modal: true,
            buttons: [
                new targetWindow.BX.UI.Button({
                    text: 'Да',
                    color: targetWindow.BX.UI.Button.Color.SUCCESS,
                    onclick: (button) => handleAnswer(taskId, true, button.getContext())
                }),
                new targetWindow.BX.UI.Button({
                    text: 'Нет',
                    color: targetWindow.BX.UI.Button.Color.DANGER,
                    onclick: (button) => handleAnswer(taskId, false, button.getContext())
                }),
                new targetWindow.BX.UI.Button({
                    text: 'Отмена',
                    color: targetWindow.BX.UI.Button.Color.LINK,
                    onclick: (button) => button.getContext().close()
                })
            ]
        });
    }

    function handleAnswer(taskId, answer, messageBox) {
        messageBox.close();
        BX.showWait();

        // Шаг 1: Обновляем пользовательское поле
        // UF_RESULT_ANSWER - поле типа "Список": ID 26 = "ДА", ID 27 = "НЕТ"
        BX.ajax.runComponentAction('bitrix:tasks.task', 'legacyUpdate', {
            mode: 'class',
            data: {
                taskId: taskId,
                data: { 'UF_RESULT_ANSWER': answer ? 26 : 27 }
            }
        }).then(function() {
            // Шаг 2: Завершаем задачу
            return BX.ajax.runComponentAction('bitrix:tasks.task', 'complete', {
                mode: 'class',
                data: { taskId: taskId }
            });
        }).then(function(){
            // Шаг 3 (НОВЫЙ): Закрываем текущий слайдер
            console.log('Задача успешно завершена. Закрываю слайдер...');
            if (top.BX.SidePanel && top.BX.SidePanel.Instance) {
                top.BX.SidePanel.Instance.close();
            }
            BX.closeWait();
        }).catch(function(response) {
            console.error('Ошибка:', response.errors);
            BX.closeWait();
            alert('Произошла ошибка при сохранении результата.');
        });
    }

    function findFieldRowByLabel(doc, labelText) {
        const cells = doc.querySelectorAll('td.task-detail-property-name');
        for (let i = 0; i < cells.length; i++) {
            if (cells[i].textContent.trim() === labelText) {
                return cells[i].parentNode;
            }
        }
        return null;
    }

    function getTaskIdFromUrl(url) {
        const match = url.match(/\/tasks\/task\/view\/(\d+)\//);
        return match ? parseInt(match[1], 10) : null;
    }

    taskCheckInterval = setInterval(findAndModifyTask, 300);

})();