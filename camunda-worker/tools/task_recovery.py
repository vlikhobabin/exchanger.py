#!/usr/bin/env python3
"""
Утилита для восстановления зависших External Tasks
"""
import requests
import time
import sys
import os
import json
import pika
from requests.auth import HTTPBasicAuth

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config, rabbitmq_config
from loguru import logger


class TaskRecovery:
    """Класс для восстановления зависших задач"""
    
    def __init__(self):
        self.base_url = camunda_config.base_url.rstrip('/')
        if not self.base_url.endswith('/engine-rest'):
            self.base_url = f"{self.base_url}/engine-rest"
        
        self.auth = None
        if camunda_config.auth_enabled:
            self.auth = HTTPBasicAuth(camunda_config.auth_username, camunda_config.auth_password)
        
        # RabbitMQ соединение
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
    
    def connect_rabbitmq(self) -> bool:
        """Подключение к RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(
                username=rabbitmq_config.username,
                password=rabbitmq_config.password
            )
            
            parameters = pika.ConnectionParameters(
                host=rabbitmq_config.host,
                port=rabbitmq_config.port,
                virtual_host=rabbitmq_config.virtual_host,
                credentials=credentials,
                heartbeat=rabbitmq_config.heartbeat,
                blocked_connection_timeout=rabbitmq_config.blocked_connection_timeout,
            )
            
            self.rabbitmq_connection = pika.BlockingConnection(parameters)
            self.rabbitmq_channel = self.rabbitmq_connection.channel()
            
            logger.info(f"Подключение к RabbitMQ успешно: {rabbitmq_config.host}:{rabbitmq_config.port}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к RabbitMQ: {e}")
            return False
    
    def disconnect_rabbitmq(self):
        """Отключение от RabbitMQ"""
        try:
            if self.rabbitmq_channel and not self.rabbitmq_channel.is_closed:
                self.rabbitmq_channel.close()
            if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
                self.rabbitmq_connection.close()
            logger.info("Соединение с RabbitMQ закрыто")
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединения RabbitMQ: {e}")
        finally:
            self.rabbitmq_connection = None
            self.rabbitmq_channel = None
    
    def check_message_in_queue(self, queue_name: str, external_task_id: str) -> bool:
        """
        Проверяет наличие сообщения с указанным External Task ID в очереди
        
        Args:
            queue_name: Имя очереди для проверки
            external_task_id: External Task ID для поиска
            
        Returns:
            True если сообщение найдено, False иначе
        """
        try:
            if not self.rabbitmq_channel:
                if not self.connect_rabbitmq():
                    return False
            
            # Получаем информацию об очереди
            try:
                method = self.rabbitmq_channel.queue_declare(queue=queue_name, passive=True)
                message_count = method.method.message_count
            except Exception:
                # Очередь не существует
                logger.debug(f"Очередь {queue_name} не существует")
                return False
            
            if message_count == 0:
                logger.debug(f"Очередь {queue_name} пуста")
                return False
            
            logger.debug(f"Проверяем {message_count} сообщений в очереди {queue_name} на наличие External Task ID {external_task_id}")
            
            # Получаем все сообщения из очереди (без ACK)
            found_messages = []
            for _ in range(message_count):
                method_frame, header_frame, body = self.rabbitmq_channel.basic_get(queue=queue_name, auto_ack=False)
                if method_frame is None:
                    break
                
                try:
                    message_data = json.loads(body.decode('utf-8'))
                    message_task_id = message_data.get('task_id')
                    
                    if message_task_id == external_task_id:
                        logger.debug(f"Найдено сообщение с External Task ID {external_task_id} в очереди {queue_name}")
                        found_messages.append((method_frame.delivery_tag, message_data))
                    else:
                        # Возвращаем сообщение в очередь (NACK с requeue=True)
                        self.rabbitmq_channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
                        
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"Ошибка парсинга сообщения из очереди {queue_name}: {e}")
                    # Возвращаем некорректное сообщение в очередь
                    self.rabbitmq_channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
            
            # Возвращаем найденные сообщения в очередь
            for delivery_tag, message_data in found_messages:
                self.rabbitmq_channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
            
            return len(found_messages) > 0
            
        except Exception as e:
            logger.error(f"Ошибка проверки очереди {queue_name}: {e}")
            return False
    
    def is_task_stuck(self, task_id: str, max_age_minutes: int = 30) -> bool:
        """
        Определяет, является ли задача зависшей
        
        Критерии зависшей задачи:
        1. Задача заблокирована в Camunda
        2. Нет сообщения в bitrix24.queue (не отправлено в обработку)
        3. Нет сообщения в bitrix24.sent.queue (не обработано успешно)
        4. Время блокировки превышает max_age_minutes
        
        Args:
            task_id: External Task ID
            max_age_minutes: Максимальный возраст блокировки в минутах
            
        Returns:
            True если задача зависшая, False если не зависшая, None при ошибке подключения к RabbitMQ
        """
        try:
            # Подключаемся к RabbitMQ если нужно
            if not self.rabbitmq_channel:
                if not self.connect_rabbitmq():
                    logger.error("Не удалось подключиться к RabbitMQ для проверки зависших задач")
                    return None  # Возвращаем None при ошибке подключения
            
            # Проверяем наличие сообщения в bitrix24.queue
            if self.check_message_in_queue("bitrix24.queue", task_id):
                logger.debug(f"Задача {task_id} найдена в bitrix24.queue - не зависшая")
                return False
            
            # Проверяем наличие сообщения в bitrix24.sent.queue
            if self.check_message_in_queue("bitrix24.sent.queue", task_id):
                logger.debug(f"Задача {task_id} найдена в bitrix24.sent.queue - не зависшая")
                return False
            
            # Если сообщений нет в обеих очередях - задача может быть зависшей
            logger.debug(f"Задача {task_id} не найдена в RabbitMQ очередях - возможно зависшая")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка проверки зависшей задачи {task_id}: {e}")
            return False
    
    def get_locked_tasks(self, worker_id: str = None) -> list:
        """Получить список заблокированных задач"""
        try:
            url = f"{self.base_url}/external-task"
            params = {}
            if worker_id:
                params['workerId'] = worker_id
            
            response = requests.get(url, auth=self.auth, params=params, verify=False, timeout=10)
            
            if response.status_code == 200:
                tasks = response.json()
                locked_tasks = [task for task in tasks if task.get('workerId') is not None]
                return locked_tasks
            else:
                logger.error(f"Ошибка получения задач: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка получения задач: {e}")
            return []
    
    def unlock_task(self, task_id: str) -> bool:
        """Разблокировать задачу"""
        try:
            url = f"{self.base_url}/external-task/{task_id}/unlock"
            response = requests.post(url, auth=self.auth, verify=False, timeout=10)
            
            if response.status_code == 204:
                logger.info(f"✅ Задача {task_id} успешно разблокирована")
                return True
            else:
                logger.error(f"❌ Ошибка разблокировки задачи {task_id}: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка разблокировки задачи {task_id}: {e}")
            return False
    
    def fail_task(self, task_id: str, error_message: str = "Task recovery: unlocked due to processing error") -> bool:
        """Пометить задачу как неудачную"""
        try:
            url = f"{self.base_url}/external-task/{task_id}/failure"
            payload = {
                "workerId": camunda_config.worker_id,
                "errorMessage": error_message,
                "errorDetails": "Task was unlocked due to processing error and marked as failed",
                "retries": 0,
                "retryTimeout": 0
            }
            
            response = requests.post(url, auth=self.auth, json=payload, verify=False, timeout=10)
            
            if response.status_code == 204:
                logger.info(f"✅ Задача {task_id} помечена как неудачная")
                return True
            else:
                logger.error(f"❌ Ошибка пометки задачи {task_id} как неудачной: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка пометки задачи {task_id} как неудачной: {e}")
            return False
    
    def recover_stuck_tasks(self, worker_id: str = None, max_age_minutes: int = 30) -> dict:
        """Восстановить зависшие задачи"""
        logger.info("🔍 Поиск зависших задач...")
        
        locked_tasks = self.get_locked_tasks(worker_id)
        if not locked_tasks:
            logger.info("✅ Заблокированных задач не найдено")
            return {"unlocked": 0, "failed": 0, "errors": 0, "checked": 0, "stuck": 0}
        
        logger.info(f"📋 Найдено заблокированных задач: {len(locked_tasks)}")
        
        current_time = time.time()
        results = {"unlocked": 0, "failed": 0, "errors": 0, "checked": 0, "stuck": 0}
        
        for task in locked_tasks:
            task_id = task.get('id')
            lock_time = task.get('lockExpirationTime')
            topic = task.get('topicName')
            task_worker_id = task.get('workerId')
            
            logger.info(f"🎯 Обработка задачи {task_id} (topic: {topic}, worker: {task_worker_id})")
            results["checked"] += 1
            
            # Проверяем возраст блокировки
            age_minutes = 0
            if lock_time:
                try:
                    # Парсим время блокировки (формат ISO 8601)
                    from datetime import datetime
                    lock_datetime = datetime.fromisoformat(lock_time.replace('Z', '+00:00'))
                    lock_timestamp = lock_datetime.timestamp()
                    age_minutes = (current_time - lock_timestamp) / 60
                    
                    logger.debug(f"Время блокировки задачи {task_id}: {lock_time} -> {age_minutes:.1f} минут назад")
                    
                    # Если время отрицательное (в будущем) - считаем задачу подозрительной
                    if age_minutes < 0:
                        logger.warning(f"⚠️ Задача {task_id} имеет время блокировки в будущем ({age_minutes:.1f} мин) - подозрительно!")
                        age_minutes = abs(age_minutes)  # Берем абсолютное значение для проверки
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки времени блокировки для задачи {task_id}: {e}")
                    results["errors"] += 1
                    continue
            else:
                logger.warning(f"⚠️ У задачи {task_id} нет времени блокировки - подозрительно!")
                # Если нет времени блокировки - считаем задачу зависшей
                age_minutes = max_age_minutes + 1
            
            # Проверяем, является ли задача зависшей
            is_stuck = False
            
            if age_minutes > max_age_minutes:
                logger.warning(f"⚠️ Задача {task_id} заблокирована уже {age_minutes:.1f} минут")
                
                # Дополнительная проверка через RabbitMQ
                rabbitmq_check_result = self.is_task_stuck(task_id, max_age_minutes)
                
                if rabbitmq_check_result is True:
                    logger.warning(f"🚨 Задача {task_id} действительно зависшая - нет сообщений в RabbitMQ очередях")
                    is_stuck = True
                    results["stuck"] += 1
                elif rabbitmq_check_result is False:
                    logger.info(f"✅ Задача {task_id} не зависшая - найдены сообщения в RabbitMQ очередях")
                else:
                    # Ошибка подключения к RabbitMQ - считаем задачу зависшей по времени
                    logger.warning(f"⚠️ Не удалось проверить RabbitMQ для задачи {task_id}, считаем зависшей по времени блокировки")
                    is_stuck = True
                    results["stuck"] += 1
            else:
                logger.info(f"✅ Задача {task_id} заблокирована недавно ({age_minutes:.1f} мин), пропускаем")
            
            # Разблокируем только действительно зависшие задачи
            if is_stuck:
                logger.warning(f"🔓 Разблокируем зависшую задачу {task_id}")
                
                if self.unlock_task(task_id):
                    results["unlocked"] += 1
                    
                    # Помечаем как неудачную
                    if self.fail_task(task_id, f"Task recovery: stuck task unlocked after {age_minutes:.1f} minutes"):
                        results["failed"] += 1
                    else:
                        results["errors"] += 1
                else:
                    results["errors"] += 1
        
        logger.info(f"📊 Результаты восстановления: проверено={results['checked']}, зависших={results['stuck']}, разблокировано={results['unlocked']}, помечено как неудачные={results['failed']}, ошибок={results['errors']}")
        return results


def main():
    """Главная функция"""
    print("🔧 ВОССТАНОВЛЕНИЕ ЗАВИСШИХ EXTERNAL TASKS")
    print("=" * 50)
    print(f"🔗 Camunda URL: {camunda_config.base_url}")
    print(f"🔐 Аутентификация: {'Включена' if camunda_config.auth_enabled else 'Отключена'}")
    print(f"🐰 RabbitMQ Host: {rabbitmq_config.host}")
    print()
    
    recovery = TaskRecovery()
    
    try:
        # Восстанавливаем задачи для universal-worker
        results = recovery.recover_stuck_tasks(worker_id="universal-worker", max_age_minutes=5)
        
        print("\n" + "=" * 50)
        print("✅ Восстановление завершено!")
        print(f"📊 Статистика:")
        print(f"   • Проверено задач: {results['checked']}")
        print(f"   • Найдено зависших: {results['stuck']}")
        print(f"   • Разблокировано: {results['unlocked']}")
        print(f"   • Помечено как неудачные: {results['failed']}")
        print(f"   • Ошибок: {results['errors']}")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при восстановлении задач: {e}")
        print(f"\n❌ Критическая ошибка: {e}")
    finally:
        # Закрываем соединение с RabbitMQ
        recovery.disconnect_rabbitmq()


if __name__ == "__main__":
    main()
