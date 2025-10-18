#!/usr/bin/env python3
"""
BitrixTaskTracker - Модуль для отслеживания задач в Bitrix24.

Основная функциональность:
- Мониторит очередь bitrix24.sent.queue на предмет новых задач
- Проверяет статус задач в Bitrix24 через REST API
- Перемещает завершенные задачи в очередь camunda.responses.queue
- Ведет детальную статистику обработки задач

Архитектура:
- Использует RabbitMQ для получения и отправки сообщений
- Интегрируется с Bitrix24 через REST API
- Поддерживает резолвинг пользовательских полей задач
- Оптимизированное логирование с heartbeat механизмом

Автор: Vyacheslav Likhobabin
Версия: 2.0
"""
import json
import requests
import time
from typing import Dict, Any, Optional, List
from loguru import logger
from .config import bitrix_config
from rabbitmq_consumer import RabbitMQConsumer
from rabbitmq_publisher import RabbitMQPublisher


class BitrixTaskTracker:
    """
    Tracker для отслеживания статуса задач в Bitrix24.
    
    Основная функциональность:
    - Мониторит очередь bitrix24.sent.queue на предмет новых задач
    - Проверяет статус задач в Bitrix24 через API
    - Перемещает завершенные задачи в очередь camunda.responses.queue
    - Ведет статистику обработки задач
    
    Attributes:
        config: Конфигурация Bitrix24
        consumer: RabbitMQ потребитель для чтения сообщений
        publisher: RabbitMQ издатель для отправки сообщений
        source_queue: Исходная очередь для мониторинга
        target_queue: Целевая очередь для завершенных задач
        completed_statuses: Список статусов завершенных задач
        stats: Словарь со статистикой работы
    """
    
    def __init__(self):
        """
        Инициализация BitrixTaskTracker.
        
        Настраивает подключения к RabbitMQ, API Bitrix24 и инициализирует
        статистику для мониторинга работы трекера.
        """
        self.config = bitrix_config
        self.task_get_url = f"{self.config.webhook_url}/tasks.task.get.json"
        
        # Инициализация RabbitMQ компонентов
        self.consumer = RabbitMQConsumer()
        self.publisher = RabbitMQPublisher()
        
        # Настройка очередей
        self.source_queue = "bitrix24.sent.queue"  # Очередь для мониторинга
        self.target_queue = "camunda.responses.queue"  # Очередь для завершенных задач
        
        # Статусы завершенных задач в Bitrix24
        # 4 - Выполнена, 5 - Отклонена
        self.completed_statuses = ["4", "5"]

        # Инициализация статистики
        self.stats = {
            "start_time": time.time(),  # Время запуска трекера
            "total_checked": 0,  # Общее количество проверенных задач
            "completed_tasks": 0,  # Количество завершенных задач
            "moved_to_responses": 0,  # Количество успешно перемещенных задач
            "failed_moves": 0,  # Количество неудачных перемещений
            "failed_checks": 0,  # Количество неудачных проверок
            "last_check_time": None,  # Время последней проверки
            "errors": []  # Список ошибок
        }
        
        # Синхронизация пользовательских полей при инициализации
        self._sync_user_fields()
        
        logger.info("BitrixTaskTracker инициализирован с упрощенной логикой резолвинга полей.")
    
    def _sync_user_fields(self):
        """
        Синхронизация пользовательских полей при инициализации трекера.
        
        Получает актуальные значения поля UF_RESULT_ANSWER из Bitrix24 API
        или загружает из кеш-файла при недоступности API.
        """
        try:
            from .userfield_sync import BitrixUserFieldSync
            
            # Создаем экземпляр синхронизатора
            uf_sync = BitrixUserFieldSync(self.config)
            
            # Выполняем синхронизацию
            updated_mapping = uf_sync.sync_mapping()
            
            if updated_mapping:
                # Обновляем маппинг в конфигурации
                self.config.uf_result_answer_mapping = updated_mapping
                logger.info(f"✅ UF_RESULT_ANSWER маппинг обновлен: {updated_mapping}")
            else:
                logger.warning("⚠️ Не удалось обновить маппинг UF_RESULT_ANSWER, используются значения по умолчанию")
                if not self.config.uf_result_answer_mapping:
                    # Устанавливаем fallback значения если маппинг пустой
                    self.config.uf_result_answer_mapping = {
                        "26": "ДА",
                        "27": "НЕТ"
                    }
                    logger.info(f"Установлены fallback значения: {self.config.uf_result_answer_mapping}")
                    
        except ImportError as e:
            logger.error(f"Ошибка импорта модуля синхронизации пользовательских полей: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при синхронизации пользовательских полей: {e}")
    
    def _check_tasks_in_queue(self):
        """
        Основной метод проверки задач в очереди.
        
        Выполняет следующие действия:
        1. Подключается к RabbitMQ если необходимо
        2. Получает сообщения из исходной очереди
        3. Обрабатывает каждое сообщение (проверяет статус задачи в Bitrix24)
        4. Перемещает завершенные задачи в целевую очередь
        5. Обновляет статистику и логирует результаты
        
        Логирование оптимизировано:
        - Heartbeat каждые 5 минут для мониторинга активности
        - Детальное логирование только при изменении количества сообщений
        - Ошибки логируются всегда для отладки
        """
        try:
            # Обновляем время последней проверки
            self.stats["last_check_time"] = time.time()
            
            # Подключаемся к RabbitMQ если не подключены
            if not self.consumer.is_connected() and not self.consumer.connect():
                return
            
            # Получаем сообщения из исходной очереди
            messages = self._get_messages_from_queue(self.source_queue)
            
            # Определяем необходимость логирования heartbeat (каждые 5 минут)
            current_time = time.time()
            should_log_heartbeat = (
                not hasattr(self, '_last_heartbeat_log') or 
                (current_time - self._last_heartbeat_log) >= 300
            )
            
            # Проверяем изменение количества сообщений для оптимизации логирования
            current_message_count = len(messages) if messages else 0
            last_message_count = getattr(self, '_last_message_count', 0)
            message_count_changed = current_message_count != last_message_count
            self._last_message_count = current_message_count
            
            if messages:
                # Логируем только при изменении количества сообщений или для heartbeat
                if message_count_changed or should_log_heartbeat:
                    logger.info(f"Проверка {len(messages)} сообщений в очереди {self.source_queue}")
                    if should_log_heartbeat:
                        self._last_heartbeat_log = current_time
                
                # Обрабатываем каждое сообщение
                for message_info in messages:
                    try:
                        self._process_message(message_info)
                    except Exception as e:
                        logger.error(f"Критическая ошибка обработки сообщения {message_info.get('delivery_tag', 'unknown')}: {e}")
                        self.stats["failed_checks"] += 1
            elif should_log_heartbeat:
                # Логируем heartbeat когда очередь пуста
                logger.debug(f"Tracker heartbeat: очередь {self.source_queue} пуста")
                self._last_heartbeat_log = current_time
                
        except Exception as e:
            logger.error(f"Ошибка при проверке задач в очереди: {e}")
            self.stats["errors"].append(str(e))
    
    def _get_messages_from_queue(self, queue_name: str) -> List[Dict[str, Any]]:
        """
        Получает сообщения из указанной очереди RabbitMQ.
        
        Args:
            queue_name: Имя очереди для получения сообщений
            
        Returns:
            List[Dict[str, Any]]: Список сообщений, каждое содержит:
                - delivery_tag: Тег доставки для подтверждения/отклонения
                - message_data: Данные сообщения в формате JSON
                
        Особенности:
            - Проверяет подключение к RabbitMQ перед получением
            - Ограничивает количество сообщений до 50 за один раз
            - Не подтверждает сообщения автоматически (auto_ack=False)
            - Возвращает пустой список при ошибках или отсутствии сообщений
        """
        messages = []
        try:
            # Проверяем подключение к RabbitMQ
            if not self.consumer.is_connected() and not self.consumer.connect():
                return messages
            
            # Получаем информацию об очереди (количество сообщений)
            method = self.consumer.channel.queue_declare(queue=queue_name, passive=True)
            if method.method.message_count == 0: 
                return messages
            
            # Получаем сообщения (максимум 50 за раз для производительности)
            for _ in range(min(method.method.message_count, 50)):
                method_frame, _, body = self.consumer.channel.basic_get(queue=queue_name, auto_ack=False)
                if method_frame is None: 
                    break
                # Парсим JSON и сохраняем с delivery_tag для последующего подтверждения
                messages.append({
                    "delivery_tag": method_frame.delivery_tag, 
                    "message_data": json.loads(body)
                })
            return messages
        except Exception as e:
            logger.error(f"Ошибка получения сообщений из очереди {queue_name}: {e}")
            return []
    
    def _process_message(self, message_info: Dict[str, Any]):
        """
        Обрабатывает одно сообщение из очереди.
        
        Алгоритм обработки:
        1. Извлекает ID задачи из сообщения
        2. Получает актуальную информацию о задаче из Bitrix24
        3. Проверяет статус задачи
        4. Если задача завершена - перемещает в целевую очередь
        5. Подтверждает или отклоняет сообщение в RabbitMQ
        
        Args:
            message_info: Словарь с информацией о сообщении:
                - delivery_tag: Тег для подтверждения/отклонения
                - message_data: Данные сообщения
                
        Логика подтверждения сообщений:
        - ACK: Сообщение успешно обработано и перемещено
        - NACK + requeue: Сообщение не обработано, возвращается в очередь
        """
        delivery_tag = message_info["delivery_tag"]
        try:
            # Извлекаем ID задачи из сообщения
            task_id = self._extract_task_id(message_info["message_data"])
            if not task_id:
                # Если не удалось извлечь ID - отклоняем сообщение
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return

            # Получаем актуальную информацию о задаче из Bitrix24
            task_info = self._get_task_info_from_bitrix(task_id)
            if not task_info:
                # Если не удалось получить информацию - отклоняем сообщение
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return
            
            # Проверяем статус задачи
            if str(task_info.get('status')) in self.completed_statuses:
                logger.info(f"Задача {task_id} завершена (статус: {task_info['status']}), перемещаем.")
                
                # Обновляем данные сообщения с актуальной информацией о задаче
                updated_message = self._update_response_data(message_info["message_data"], task_info)
                
                # Перемещаем в целевую очередь
                if self._move_to_responses_queue(updated_message):
                    # Успешно перемещено - подтверждаем сообщение
                    self.consumer.channel.basic_ack(delivery_tag=delivery_tag)
                    self.stats["completed_tasks"] += 1
                    self.stats["moved_to_responses"] += 1
                else:
                    # Ошибка перемещения - отклоняем сообщение
                    self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
            else:
                # Задача не завершена - возвращаем в очередь для повторной проверки
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения {delivery_tag}: {e}")
            # При критической ошибке - отклоняем сообщение
            if self.consumer.is_connected():
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)

    def _extract_task_id(self, message_data: Dict[str, Any]) -> Optional[str]:
        """
        Извлекает ID задачи из данных сообщения.
        
        Args:
            message_data: Данные сообщения в формате JSON
            
        Returns:
            Optional[str]: ID задачи в виде строки или None если не найден
            
        Структура ожидаемых данных:
            message_data['response_data']['result']['task']['id']
            
        Обработка ошибок:
            - Логирует предупреждение при отсутствии ID
            - Возвращает None для некорректных данных
        """
        try:
            return str(message_data['response_data']['result']['task']['id'])
        except KeyError:
            logger.warning("ID задачи не найден в response_data")
            return None
    
    def _get_task_info_from_bitrix(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о задаче из Bitrix24 через REST API.
        
        Args:
            task_id: ID задачи в Bitrix24
            
        Returns:
            Optional[Dict[str, Any]]: Информация о задаче или None при ошибке
            
        Запрашиваемые поля:
            - *: Все стандартные поля задачи
            - UF_RESULT_EXPECTED: Пользовательское поле "Ожидаемый результат"
            - UF_RESULT_QUESTION: Пользовательское поле "Вопрос"
            - UF_RESULT_ANSWER: Пользовательское поле "Ответ"
            
        Обработка ошибок:
            - Логирует ошибки сетевых запросов
            - Возвращает None при отсутствии данных или ошибках
            - Использует таймаут из конфигурации
        """
        try:
            # Настраиваем поля для запроса (включая пользовательские поля)
            select_fields = ['*', 'UF_RESULT_EXPECTED', 'UF_RESULT_QUESTION', 'UF_RESULT_ANSWER']
            params = {'taskId': task_id, 'select[]': select_fields}
            
            # Выполняем запрос к Bitrix24 API
            response = requests.get(self.task_get_url, params=params, timeout=self.config.request_timeout)
            response.raise_for_status()
            
            # Извлекаем данные задачи из ответа
            task_info = response.json().get('result', {}).get('task', {})
            return task_info if task_info.get('id') else None
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к Bitrix24 для задачи {task_id}: {e}")
            return None

    def _update_response_data(self, message_data: Dict[str, Any], task_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обновляет данные сообщения с актуальной информацией о задаче.
        
        Args:
            message_data: Исходные данные сообщения
            task_info: Актуальная информация о задаче из Bitrix24
            
        Returns:
            Dict[str, Any]: Обновленные данные сообщения
            
        Выполняемые операции:
            1. Резолвинг пользовательского поля UF_RESULT_ANSWER
            2. Обновление response_data с актуальными данными задачи
            3. Добавление метаданных обработки (время, статус)
            
        Логика резолвинга:
            - Извлекает ID ответа из поля ufResultAnswer
            - Использует маппинг из конфигурации для преобразования ID в текст
            - Если маппинг не найден - использует исходный ID
        """
        # Упрощенная логика резолвинга пользовательского поля
        answer_id = task_info.get('ufResultAnswer')
        if answer_id:
            # Проверяем наличие маппинга
            if not self.config.uf_result_answer_mapping:
                logger.warning("Маппинг UF_RESULT_ANSWER пуст, используется исходный ID")
            
            # Используем маппинг из конфига. .get() вернет ID, если соответствие не найдено.
            mapped_value = self.config.uf_result_answer_mapping.get(str(answer_id), str(answer_id))
            task_info['ufResultAnswer_text'] = mapped_value
            
            # Логируем резолвинг для отладки
            if mapped_value != str(answer_id):
                logger.debug(f"Резолвинг UF_RESULT_ANSWER: {answer_id} -> {mapped_value}")
            else:
                logger.debug(f"UF_RESULT_ANSWER не найден в маппинге, используется ID: {answer_id}")

        # Обновляем данные сообщения с актуальной информацией о задаче
        message_data['response_data'] = {'result': {'task': task_info}}
        message_data['processed_at'] = time.time()
        message_data['processing_status'] = 'completed_by_tracker'
        return message_data

    def _move_to_responses_queue(self, message_data: Dict[str, Any]) -> bool:
        """
        Перемещает сообщение в целевую очередь для завершенных задач.
        
        Args:
            message_data: Данные сообщения для отправки
            
        Returns:
            bool: True если сообщение успешно отправлено, False при ошибке
            
        Особенности:
            - Проверяет подключение к RabbitMQ перед отправкой
            - Использует persistent=True для сохранения сообщения на диск
            - Логирует ошибки отправки для отладки
        """
        try:
            # Проверяем подключение к RabbitMQ
            if not self.publisher.is_connected() and not self.publisher.connect():
                return False
            
            # Отправляем сообщение в целевую очередь с персистентностью
            return self.publisher.publish_message(self.target_queue, message_data, persistent=True)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в {self.target_queue}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику работы трекера.
        
        Returns:
            Dict[str, Any]: Словарь со статистикой:
                - uptime_seconds: Время работы в секундах
                - total_checked: Общее количество проверенных задач
                - completed_tasks: Количество завершенных задач
                - moved_to_responses: Количество успешно перемещенных задач
                - failed_moves: Количество неудачных перемещений
                - failed_checks: Количество неудачных проверок
                - completion_rate: Процент завершенных задач от проверенных
                - success_move_rate: Процент успешных перемещений от завершенных
                - last_check_time: Время последней проверки
                - errors_count: Количество ошибок
                - recent_errors: Последние 5 ошибок
        """
        uptime = time.time() - self.stats["start_time"]
        return {
            "uptime_seconds": uptime, 
            "total_checked": self.stats["total_checked"], 
            "completed_tasks": self.stats["completed_tasks"], 
            "moved_to_responses": self.stats["moved_to_responses"],
            "failed_moves": self.stats["failed_moves"], 
            "failed_checks": self.stats["failed_checks"],
            "completion_rate": (self.stats["completed_tasks"] / self.stats["total_checked"] * 100 if self.stats["total_checked"] > 0 else 0),
            "success_move_rate": (self.stats["moved_to_responses"] / self.stats["completed_tasks"] * 100 if self.stats["completed_tasks"] > 0 else 0),
            "last_check_time": self.stats["last_check_time"], 
            "errors_count": len(self.stats["errors"]),
            "recent_errors": self.stats["errors"][-5:]
        }
    
    def cleanup(self):
        """
        Очищает ресурсы трекера.
        
        Выполняет следующие действия:
        1. Отключает RabbitMQ consumer если подключен
        2. Отключает RabbitMQ publisher если подключен
        3. Логирует завершение очистки
        
        Рекомендуется вызывать при завершении работы трекера
        для корректного закрытия соединений с RabbitMQ.
        """
        # Отключаем consumer если подключен
        if hasattr(self, 'consumer') and self.consumer.is_connected(): 
            self.consumer.disconnect()
        
        # Отключаем publisher если подключен
        if hasattr(self, 'publisher') and self.publisher.is_connected(): 
            self.publisher.disconnect()
        
        logger.info("Ресурсы BitrixTaskTracker очищены")