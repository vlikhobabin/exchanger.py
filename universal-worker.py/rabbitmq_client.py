"""
RabbitMQ клиент для отправки задач от Camunda
"""
import json
import pika
import time
from typing import Dict, Any, Optional
from loguru import logger
from config import rabbitmq_config, routing_config, response_config


class RabbitMQClient:
    """Клиент для работы с RabbitMQ"""
    
    def __init__(self):
        self.config = rabbitmq_config
        self.routing = routing_config
        self.response_config = response_config
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        
    def connect(self) -> bool:
        """Подключение к RabbitMQ"""
        try:
            # Настройка подключения
            credentials = pika.PlainCredentials(
                username=self.config.username,
                password=self.config.password
            )
            
            parameters = pika.ConnectionParameters(
                host=self.config.host,
                port=self.config.port,
                virtual_host=self.config.virtual_host,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            logger.info(f"Подключение к RabbitMQ успешно: {self.config.host}:{self.config.port}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к RabbitMQ: {e}")
            return False
    
    def setup_infrastructure(self) -> bool:
        """Создание exchange, очередей и привязок с Alternate Exchange"""
        try:
            if not self.channel:
                logger.error("Нет активного соединения с RabbitMQ")
                return False
            
            # 1. Создание Alternate Exchange (сначала!)
            self.channel.exchange_declare(
                exchange=self.config.alternate_exchange_name,
                exchange_type=self.config.alternate_exchange_type,
                durable=True
            )
            logger.info(f"Alternate Exchange создан: {self.config.alternate_exchange_name}")
            
            # 2. Создание основного exchange с указанием Alternate Exchange
            self.channel.exchange_declare(
                exchange=self.config.tasks_exchange_name,
                exchange_type=self.config.tasks_exchange_type,
                durable=True,
                arguments={
                    'alternate-exchange': self.config.alternate_exchange_name
                }
            )
            logger.info(f"Tasks Exchange создан с AE: {self.config.tasks_exchange_name}")
            
            # 3. Создание exchange для ответов (без изменений)
            self.channel.exchange_declare(
                exchange=self.config.responses_exchange_name,
                exchange_type=self.config.responses_exchange_type,
                durable=True
            )
            logger.info(f"Responses Exchange создан: {self.config.responses_exchange_name}")
            
            # 4. Создание очереди для ответов (без изменений)
            self.channel.queue_declare(queue=self.config.responses_queue_name, durable=True)
            self.channel.queue_bind(
                exchange=self.config.responses_exchange_name,
                queue=self.config.responses_queue_name,
                routing_key=self.config.responses_queue_name
            )
            logger.info(f"Очередь ответов создана: {self.config.responses_queue_name}")
            
            # 5. Создание очередей для задач с обычными привязками
            for queue_name, routing_keys in self.routing.ROUTING_BINDINGS.items():
                # Создание очереди
                self.channel.queue_declare(queue=queue_name, durable=True)
                logger.info(f"Очередь создана: {queue_name}")
                
                # Привязка очереди к основному exchange
                for routing_key in routing_keys:
                    self.channel.queue_bind(
                        exchange=self.config.tasks_exchange_name,
                        queue=queue_name,
                        routing_key=routing_key
                    )
                    logger.info(f"Привязка создана: {queue_name} <- {routing_key}")
            
            # 6. Создание default.queue и привязка к Alternate Exchange
            self.channel.queue_declare(queue="default.queue", durable=True)
            self.channel.queue_bind(
                exchange=self.config.alternate_exchange_name,
                queue="default.queue",
                routing_key=""  # Fanout не использует routing key
            )
            logger.info(f"Default queue привязана к Alternate Exchange")
            
            # 7. Создание очереди для ошибок (без изменений)
            error_queue = "errors.camunda_tasks.queue"
            self.channel.queue_declare(queue=error_queue, durable=True)
            self.channel.queue_bind(
                exchange=self.config.tasks_exchange_name,
                queue=error_queue,
                routing_key="errors.camunda_tasks"
            )
            logger.info(f"Очередь ошибок создана: {error_queue}")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка создания инфраструктуры RabbitMQ: {e}")
            return False
    
    def publish_task(self, topic: str, task_data: Dict[str, Any]) -> bool:
        """Публикация задачи в соответствующую очередь"""
        try:
            if not self.channel:
                logger.error("Нет активного соединения с RabbitMQ")
                return False
            
            # Определение routing key
            routing_key = self.routing.get_routing_key(topic)
            system = self.routing.get_system_for_topic(topic)
            
            # Подготовка сообщения
            message = {
                "task_id": task_data.get("id"),
                "topic": topic,
                "system": system,
                "variables": task_data.get("variables", {}),
                "process_instance_id": task_data.get("processInstanceId"),
                "activity_id": task_data.get("activityId"),
                "activity_instance_id": task_data.get("activityInstanceId"),
                "worker_id": task_data.get("workerId"),
                "retries": task_data.get("retries"),
                "created_time": task_data.get("createTime"),
                "priority": task_data.get("priority", 0),
                "tenant_id": task_data.get("tenantId"),
                "business_key": task_data.get("businessKey"),
                "timestamp": int(time.time() * 1000),
                # Добавляем метаданные BPMN
                "metadata": task_data.get("metadata", {})
            }
            
            # Публикация сообщения
            self.channel.basic_publish(
                exchange=self.config.tasks_exchange_name,
                routing_key=routing_key,
                body=json.dumps(message, ensure_ascii=False),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Устойчивое сообщение
                    timestamp=int(time.time()),
                    content_type='application/json',
                    headers={
                        'camunda_topic': topic,
                        'target_system': system,
                        'task_id': task_data.get("id"),
                        'process_instance_id': task_data.get("processInstanceId")
                    }
                )
            )
            
            logger.info(f"Задача опубликована: {topic} -> {routing_key} (система: {system})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка публикации задачи {topic}: {e}")
            return False
    
    def publish_error(self, topic: str, task_id: str, error_message: str) -> bool:
        """Публикация сообщения об ошибке"""
        try:
            if not self.channel:
                return False
            
            error_data = {
                "task_id": task_id,
                "topic": topic,
                "error": error_message,
                "timestamp": int(time.time() * 1000),
                "type": "task_error"
            }
            
            # Отправка в очередь ошибок
            self.channel.basic_publish(
                exchange=self.config.tasks_exchange_name,
                routing_key="errors.camunda_tasks",
                body=json.dumps(error_data, ensure_ascii=False),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            
            logger.warning(f"Ошибка задачи опубликована: {task_id} - {error_message}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка публикации ошибки: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Проверка активности соединения"""
        try:
            return (
                self.connection is not None and 
                not self.connection.is_closed and
                self.channel is not None and
                not self.channel.is_closed
            )
        except:
            return False
    
    def reconnect(self) -> bool:
        """Переподключение к RabbitMQ"""
        logger.info("Попытка переподключения к RabbitMQ...")
        self.disconnect()
        time.sleep(5)  # Задержка перед переподключением
        return self.connect() and self.setup_infrastructure()
    
    def disconnect(self):
        """Закрытие соединения"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
                
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                
            logger.info("Соединение с RabbitMQ закрыто")
            
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединения RabbitMQ: {e}")
        finally:
            self.connection = None
            self.channel = None
    
    def get_queue_info(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Получение информации об очереди"""
        try:
            if not self.channel:
                return None
                
            method = self.channel.queue_declare(queue=queue_name, passive=True)
            return {
                "queue": queue_name,
                "message_count": method.method.message_count,
                "consumer_count": method.method.consumer_count
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации об очереди {queue_name}: {e}")
            return None
    
    def get_all_queues_info(self) -> Dict[str, Dict[str, Any]]:
        """Получение информации о всех очередях включая alternate"""
        info = {}
        
        # Информация об очередях задач
        for queue_name in self.routing.ROUTING_BINDINGS.keys():
            queue_info = self.get_queue_info(queue_name)
            if queue_info:
                info[queue_name] = queue_info
        
        # Информация об очереди ответов
        response_queue_info = self.get_queue_info(self.config.responses_queue_name)
        if response_queue_info:
            info[self.config.responses_queue_name] = response_queue_info
            
        # Информация об очереди ошибок
        error_queue_info = self.get_queue_info("errors.camunda_tasks.queue")
        if error_queue_info:
            info["errors.camunda_tasks.queue"] = error_queue_info
        
        # Информация о default queue (теперь через AE)
        default_queue_info = self.get_queue_info("default.queue")
        if default_queue_info:
            info["default.queue"] = default_queue_info
            info["default.queue"]["source"] = "alternate_exchange"
            info["default.queue"]["alternate_exchange"] = self.config.alternate_exchange_name
            
        return info
    
    def consume_responses(self, callback_function, auto_ack: bool = False):
        """Запуск потребления сообщений из очереди ответов"""
        try:
            if not self.channel:
                logger.error("Нет активного соединения с RabbitMQ")
                return False
            
            self.channel.basic_consume(
                queue=self.config.responses_queue_name,
                on_message_callback=callback_function,
                auto_ack=auto_ack
            )
            
            logger.info(f"Начато потребление ответов из очереди: {self.config.responses_queue_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка запуска потребления ответов: {e}")
            return False
    
    def start_consuming(self):
        """Запуск блокирующего потребления сообщений"""
        try:
            if not self.channel:
                logger.error("Нет активного соединения с RabbitMQ")
                return
                
            logger.info("Запуск потребления сообщений...")
            self.channel.start_consuming()
            
        except Exception as e:
            logger.error(f"Ошибка потребления сообщений: {e}")
    
    def stop_consuming(self):
        """Остановка потребления сообщений"""
        try:
            if self.channel:
                self.channel.stop_consuming()
                logger.info("Потребление сообщений остановлено")
                
        except Exception as e:
            logger.error(f"Ошибка остановки потребления: {e}")
    
    def send_task_response(self, response_data: Dict[str, Any]) -> bool:
        """Отправка ответа на задачу в очередь ответов"""
        try:
            if not self.channel:
                logger.error("Нет активного соединения с RabbitMQ")
                return False
            
            # Добавление метаинформации
            response_message = {
                **response_data,
                "timestamp": int(time.time() * 1000),
                "response_source": "external_system"
            }
            
            # Публикация ответа
            self.channel.basic_publish(
                exchange=self.config.responses_exchange_name,
                routing_key=self.config.responses_queue_name,
                body=json.dumps(response_message, ensure_ascii=False),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Устойчивое сообщение
                    timestamp=int(time.time()),
                    content_type='application/json',
                    headers={
                        'response_type': response_data.get('response_type'),
                        'task_id': response_data.get('task_id'),
                        'worker_id': response_data.get('worker_id')
                    }
                )
            )
            
            logger.info(f"Ответ на задачу отправлен: {response_data.get('task_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки ответа на задачу: {e}")
            return False
    
    def get_alternate_exchange_info(self) -> Dict[str, Any]:
        """Получение информации об Alternate Exchange"""
        try:
            return {
                "alternate_exchange": self.config.alternate_exchange_name,
                "type": self.config.alternate_exchange_type,
                "main_exchange": self.config.tasks_exchange_name,
                "status": "configured",
                "description": "Обрабатывает неопознанные сообщения"
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации об AE: {e}")
            return {} 