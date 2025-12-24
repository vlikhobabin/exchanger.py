"""
Сервис для синхронизации и отправки сообщений в RabbitMQ

Модуль содержит класс SyncService для работы с очередями:
отправка успешных сообщений, отправка в очередь ошибок,
синхронизация с Bitrix24.
"""
import json
import time
from typing import Any, Dict

import pika
import requests
from loguru import logger


class SyncService:
    """
    Сервис для синхронизации и отправки сообщений в RabbitMQ

    Предоставляет методы для отправки успешных сообщений,
    отправки в очередь ошибок и синхронизации с Bitrix24.
    """

    def __init__(self, config: Any, stats: Dict[str, int], publisher: Any):
        """
        Инициализация сервиса синхронизации

        Args:
            config: Конфигурация (webhook_url, request_timeout)
            stats: Словарь статистики для обновления счётчиков
            publisher: RabbitMQPublisher для отправки сообщений
        """
        self.config = config
        self.stats = stats
        self.publisher = publisher

    def send_success_message(
        self,
        original_message: Dict[str, Any],
        bitrix_response: Dict[str, Any],
        original_queue: str
    ) -> bool:
        """
        Отправка сообщения об успешной обработке в очередь sent messages

        Args:
            original_message: Исходное сообщение из RabbitMQ
            bitrix_response: Ответ от Bitrix24 API
            original_queue: Имя исходной очереди

        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        try:
            # Подключение к RabbitMQ если нет соединения
            if not self.publisher.is_connected():
                if not self.publisher.connect():
                    logger.error("Не удалось подключиться к RabbitMQ для отправки успешного сообщения")
                    return False

            # Отправка сообщения через publisher
            success = self.publisher.publish_success_message(
                original_queue=original_queue,
                original_message=original_message,
                response_data=bitrix_response
            )

            if success:
                task_id = bitrix_response.get('result', {}).get('task', {}).get('id', 'unknown')
                logger.info(f"Результат создания задачи {task_id} отправлен в очередь успешных сообщений")
            else:
                logger.error("Не удалось отправить результат в очередь успешных сообщений")

            return success

        except Exception as e:
            logger.error(f"Ошибка при отправке успешного сообщения: {e}")
            return False

    def send_to_error_queue(self, message_data: Dict[str, Any], error_message: str) -> bool:
        """
        Отправка сообщения в очередь ошибок для ручного разбора

        Args:
            message_data: Исходное сообщение из RabbitMQ
            error_message: Описание ошибки

        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        try:
            task_id = message_data.get('task_id', 'unknown')
            logger.critical(f"Отправка задачи {task_id} в очередь ошибок: {error_message}")

            # Подготавливаем данные для очереди ошибок
            error_data = {
                "timestamp": int(time.time() * 1000),
                "original_message": message_data,
                "error_type": "ASSIGNEE_ID_ERROR",
                "error_message": error_message,
                "system": "bitrix24",
                "requires_manual_intervention": True,
                "suggested_action": "Проверить соответствие assigneeId в BPMN и пользователей в Bitrix24"
            }

            # Отправляем в очередь ошибок
            error_queue = "errors.camunda_tasks.queue"
            message_json = json.dumps(error_data, ensure_ascii=False)

            # Подключаемся к RabbitMQ если нет соединения
            if not self.publisher.is_connected():
                if not self.publisher.connect():
                    logger.error("Не удалось подключиться к RabbitMQ для отправки в очередь ошибок")
                    return False

            # Создаем очередь ошибок (если не существует)
            self.publisher.channel.queue_declare(queue=error_queue, durable=True)

            # Отправляем сообщение
            self.publisher.channel.basic_publish(
                exchange='',
                routing_key=error_queue,
                body=message_json.encode('utf-8'),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent message
                    content_type='application/json',
                    timestamp=int(time.time())
                )
            )

            logger.critical(f"Задача {task_id} отправлена в очередь ошибок: {error_queue}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки задачи в очередь ошибок: {e}")
            return False

    def send_success_message_with_retry(
        self,
        original_message: Dict[str, Any],
        response_data: Dict[str, Any],
        original_queue: str,
        max_attempts: int = 5
    ) -> bool:
        """
        Отправка сообщения об успешной обработке в очередь sent messages с retry

        Args:
            original_message: Исходное сообщение из RabbitMQ
            response_data: Данные ответа от системы
            original_queue: Имя исходной очереди
            max_attempts: Максимальное количество попыток

        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        task_id = original_message.get('task_id', 'unknown')

        for attempt in range(max_attempts):
            try:
                logger.debug(f"Bitrix24 Handler: Попытка {attempt + 1}/{max_attempts} отправки результата задачи {task_id}")

                if self.send_success_message(original_message, response_data, original_queue):
                    logger.info(f"Bitrix24 Handler: Результат задачи {task_id} успешно отправлен в очередь успешных сообщений (попытка {attempt + 1})")
                    return True

                # Если не последняя попытка - ждем перед повтором
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt  # 1, 2, 4, 8, 16 секунд
                    logger.warning(f"Bitrix24 Handler: Попытка {attempt + 1} не удалась, повтор через {wait_time}s")
                    time.sleep(wait_time)

            except Exception as e:
                logger.error(f"Bitrix24 Handler: Ошибка попытки {attempt + 1} отправки результата задачи {task_id}: {e}")

                # Если не последняя попытка - ждем перед повтором
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Bitrix24 Handler: Ошибка попытки {attempt + 1}, повтор через {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Bitrix24 Handler: Все {max_attempts} попыток отправки результата задачи {task_id} провалились")

        return False

    def send_sync_request(self, message_data: Dict[str, Any]) -> bool:
        """
        Отправка запроса синхронизации в Bitrix24 после успешного создания задачи

        Args:
            message_data: Данные сообщения с processInstanceId и processDefinitionKey

        Returns:
            True если синхронизация успешна, False иначе
        """
        try:
            logger.debug(f"Начало синхронизации, данные сообщения: {message_data}")
            # Извлекаем данные процесса
            process_instance_id = message_data.get('processInstanceId') or message_data.get('process_instance_id')
            process_definition_key = message_data.get('processDefinitionKey') or message_data.get('process_definition_key')

            logger.debug(f"Извлеченные данные: processInstanceId={process_instance_id}, processDefinitionKey={process_definition_key}")

            if not process_instance_id:
                logger.warning("processInstanceId/process_instance_id не найден в сообщении, пропускаем синхронизацию")
                logger.debug(f"Доступные поля в сообщении: {list(message_data.keys())}")
                return False

            if not process_definition_key:
                logger.error("processDefinitionKey/process_definition_key не найден в сообщении - КРИТИЧЕСКАЯ ОШИБКА!")
                logger.error(f"Доступные поля в сообщении: {list(message_data.keys())}")
                logger.error(f"Полное содержимое сообщения: {json.dumps(message_data, ensure_ascii=False, indent=2)}")

                # Попытка извлечь ключ из processDefinitionId
                process_definition_id = message_data.get('processDefinitionId') or message_data.get('process_definition_id')
                if process_definition_id:
                    try:
                        # processDefinitionId обычно имеет формат "key:version:id"
                        process_definition_key = process_definition_id.split(':')[0]
                        logger.debug(f"Извлечен processDefinitionKey из processDefinitionId: {process_definition_key}")
                    except Exception as e:
                        logger.error(f"Ошибка извлечения ключа из processDefinitionId {process_definition_id}: {e}")
                        # НЕ возвращаем False - продолжаем попытку синхронизации с fallback
                        logger.error("Продолжаем синхронизацию без processDefinitionKey (может привести к ошибкам)")
                else:
                    logger.error("processDefinitionId также не найден - синхронизация невозможна")
                    return False

            # URL для синхронизации
            sync_url = f"{self.config.webhook_url.rstrip('/')}/imena.camunda.sync"

            # Данные для отправки
            sync_data = {
                "processDefinitionKey": process_definition_key,
                "processInstanceId": process_instance_id
            }

            logger.debug(f"Отправка запроса синхронизации в Bitrix24: {sync_data}")

            # Отправка POST запроса
            response = requests.post(
                sync_url,
                json=sync_data,
                timeout=self.config.request_timeout,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                result = response.json()
                if result.get('result', {}).get('success'):
                    logger.info(f"Синхронизация успешна: processInstanceId={process_instance_id}, processDefinitionKey={process_definition_key}")
                    self.stats["sync_requests_sent"] += 1
                    return True
                else:
                    error_msg = result.get('result', {}).get('error', 'Unknown error')
                    logger.error(f"Ошибка синхронизации: {error_msg}")
                    self.stats["sync_requests_failed"] += 1
                    return False
            else:
                logger.error(f"HTTP ошибка синхронизации: {response.status_code} - {response.text}")
                self.stats["sync_requests_failed"] += 1
                return False

        except Exception as e:
            logger.error(f"Ошибка отправки запроса синхронизации: {e}")
            self.stats["sync_requests_failed"] += 1
            return False
