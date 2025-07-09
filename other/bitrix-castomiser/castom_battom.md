**Задача:** Заменить стандартную кнопку "Завершить" в задаче на кастомную "Завершить с результатом" с диалогом подтверждения, если приоритет задачи высокий (равен 2).

**Метод:** Создание глобального JavaScript-модификатора, который отслеживает появление слайдера с задачей и вносит в него изменения "на лету". Этот способ не затрагивает системные файлы и устойчив к обновлениям.

---

#### Шаг 1: Создайте файл для скрипта

В консоли сервера выполните последовательно две команды, чтобы создать нужную структуру папок и сам файл:

```bash
# 1. Создаем директории
mkdir -p /home/bitrix/www/local/templates/bitrix24/assets/js/

# 2. Создаем пустой файл
touch /home/bitrix/www/local/templates/bitrix24/assets/js/global_task_modifier.js
```

#### Шаг 2: Добавьте код в созданный файл

Откройте файл `/home/bitrix/www/local/templates/bitrix24/assets/js/global_task_modifier.js` и поместите в него следующий код:

```javascript
/**
 * Глобальный наблюдатель, который ищет слайдер задачи
 * и модифицирует его содержимое, если задача имеет высокий приоритет.
 */
(function() {
    let taskCheckInterval = null;

    function findAndModifyTask() {
        // Ищем iframe, в URL которого есть путь к задаче
        const iframe = document.querySelector('iframe.side-panel-iframe[src*="/tasks/task/view/"]');
        if (!iframe) return;

        // Получаем доступ к документу внутри iframe
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        if (iframeDoc.readyState !== 'complete') return;

        // Ищем кнопку "Завершить" и проверяем, не обработали ли мы ее ранее
        const completeButton = iframeDoc.querySelector('span[data-action="COMPLETE"]');
        if (!completeButton || completeButton.dataset.customized === 'true') return;

        // Проверяем приоритет задачи
        const highPriorityMarker = iframeDoc.querySelector('[data-priority="2"]');
        if (!highPriorityMarker) {
            completeButton.dataset.customized = 'true'; // Помечаем, чтобы не проверять снова
            return;
        }

        // --- Основная логика ---
        completeButton.innerText = 'Завершить с результатом';
        completeButton.dataset.customized = 'true'; // Ставим метку

        completeButton.addEventListener('click', (event) => {
            if (!confirm('Вы уверены, что задачу нужно завершить?')) {
                event.preventDefault();
                event.stopPropagation();
            }
        }, true);
        
        // Работа сделана, останавливаем наблюдатель
        clearInterval(taskCheckInterval);
    }

    // Запускаем проверку каждые 300 миллисекунд
    taskCheckInterval = setInterval(findAndModifyTask, 300);

})();
```

#### Шаг 3: Подключите скрипт к сайту

1.  Откройте файл `footer.php` вашего шаблона сайта. Он находится по пути:
    `/home/bitrix/www/local/templates/bitrix24/footer.php`

2.  Пролистайте в самый конец файла и прямо **перед** закрывающим тегом `</body>` добавьте следующую строку:

    ```php
    <script src="<?=SITE_TEMPLATE_PATH?>/assets/js/global_task_modifier.js?v=<?=time()?>"></script>
    ```
    *Параметр `?v=<?=time()?>` нужен, чтобы при любых изменениях скрипта браузер не использовал старую версию из кеша.*

3.  Сохраните файл.

#### Шаг 4: Очистите кеш

В административной панели Битрикс перейдите в `Настройки` -> `Настройки продукта` -> `Автокеширование` и очистите кеш для всех сайтов.

На этом все. Кастомизация будет работать.