#!/usr/bin/env python3
"""
Утилита для проверки состояния Universal Camunda Worker
"""
import json
import requests
from typing import Dict, Any
from loguru import logger

# Добавление родительского каталога в sys.path для импорта модулей проекта
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config, rabbitmq_config, routing_config
from rabbitmq_client import RabbitMQClient


class StatusChecker:
    """Проверка состояния системы"""
    
    def __init__(self):
        self.camunda_config = camunda_config
        self.rabbitmq_config = rabbitmq_config
        self.routing_config = routing_config
    
    def check_camunda_connection(self) -> Dict[str, Any]:
        """Проверка соединения с Camunda"""
        try:
            # Проверяем доступность Camunda Engine REST API
            # Формируем правильный URL с учетом возможного /engine-rest в base_url
            base_url = self.camunda_config.base_url.rstrip('/')
            if base_url.endswith('/engine-rest'):
                url = f"{base_url}/engine"
            else:
                url = f"{base_url}/engine-rest/engine"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                engines = response.json()
                return {
                    "status": "connected",
                    "engines": engines,
                    "url": url
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}",
                    "url": url
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": self.camunda_config.base_url
            }
    
    def check_rabbitmq_connection(self) -> Dict[str, Any]:
        """Проверка соединения с RabbitMQ"""
        try:
            client = RabbitMQClient()
            if client.connect():
                queues_info = client.get_all_queues_info()
                client.disconnect()
                
                return {
                    "status": "connected",
                    "host": self.rabbitmq_config.host,
                    "port": self.rabbitmq_config.port,
                    "queues": queues_info
                }
            else:
                return {
                    "status": "error",
                    "error": "Не удалось подключиться",
                    "host": self.rabbitmq_config.host,
                    "port": self.rabbitmq_config.port
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "host": self.rabbitmq_config.host,
                "port": self.rabbitmq_config.port
            }
    
    def get_external_tasks_count(self) -> Dict[str, Any]:
        """Получение количества External Tasks в Camunda"""
        try:
            base_url = self.camunda_config.base_url.rstrip('/')
            if base_url.endswith('/engine-rest'):
                url = f"{base_url}/external-task/count"
            else:
                url = f"{base_url}/engine-rest/external-task/count"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                count_data = response.json()
                return {
                    "status": "success",
                    "count": count_data.get("count", 0)
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_external_tasks_list(self, max_results: int = 10) -> Dict[str, Any]:
        """Получение списка External Tasks"""
        try:
            base_url = self.camunda_config.base_url.rstrip('/')
            if base_url.endswith('/engine-rest'):
                url = f"{base_url}/external-task"
            else:
                url = f"{base_url}/engine-rest/external-task"
            params = {"maxResults": max_results}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                tasks = response.json()
                return {
                    "status": "success",
                    "tasks": tasks,
                    "count": len(tasks)
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_full_status(self) -> Dict[str, Any]:
        """Получение полного статуса системы"""
        logger.info("Проверка состояния системы...")
        
        status = {
            "timestamp": None,
            "camunda": self.check_camunda_connection(),
            "rabbitmq": self.check_rabbitmq_connection(),
            "external_tasks": {
                "count": self.get_external_tasks_count(),
                "list": self.get_external_tasks_list()
            },
            "routing_config": {
                "systems": list(self.routing_config.SYSTEM_QUEUES.keys()),
                "queues": list(self.routing_config.SYSTEM_QUEUES.values()),
                "topic_mapping_count": len(self.routing_config.TOPIC_TO_SYSTEM_MAPPING)
            }
        }
        
        import time
        status["timestamp"] = int(time.time() * 1000)
        
        return status
    
    def print_status_report(self):
        """Вывод отчета о состоянии"""
        status = self.get_full_status()
        
        print("=" * 80)
        print("UNIVERSAL CAMUNDA WORKER - STATUS REPORT")
        print("=" * 80)
        
        # Camunda
        print(f"\n🔗 CAMUNDA CONNECTION:")
        camunda_status = status["camunda"]
        if camunda_status["status"] == "connected":
            print(f"  ✅ Подключение: OK")
            print(f"  🌐 URL: {camunda_status['url']}")
            print(f"  🚀 Engines: {len(camunda_status.get('engines', []))}")
        else:
            print(f"  ❌ Подключение: FAILED")
            print(f"  🌐 URL: {camunda_status.get('url', 'N/A')}")
            print(f"  ⚠️  Ошибка: {camunda_status.get('error', 'Unknown')}")
        
        # External Tasks
        print(f"\n📋 EXTERNAL TASKS:")
        tasks_count = status["external_tasks"]["count"]
        if tasks_count["status"] == "success":
            print(f"  📊 Количество: {tasks_count['count']}")
        else:
            print(f"  ❌ Ошибка получения: {tasks_count.get('error', 'Unknown')}")
        
        tasks_list = status["external_tasks"]["list"]
        if tasks_list["status"] == "success" and tasks_list["count"] > 0:
            print(f"  📝 Последние задачи:")
            for task in tasks_list["tasks"][:5]:
                print(f"    - {task.get('id', 'N/A')[:8]}... | {task.get('topicName', 'N/A')}")
        
        # RabbitMQ
        print(f"\n🐰 RABBITMQ CONNECTION:")
        rabbitmq_status = status["rabbitmq"]
        if rabbitmq_status["status"] == "connected":
            print(f"  ✅ Подключение: OK")
            print(f"  🌐 Host: {rabbitmq_status['host']}:{rabbitmq_status['port']}")
            print(f"  📥 Очереди:")
            queues = rabbitmq_status.get("queues", {})
            for queue_name, queue_info in queues.items():
                msg_count = queue_info.get("message_count", 0)
                consumer_count = queue_info.get("consumer_count", 0)
                print(f"    - {queue_name}: {msg_count} сообщений, {consumer_count} потребителей")
        else:
            print(f"  ❌ Подключение: FAILED")
            print(f"  🌐 Host: {rabbitmq_status.get('host', 'N/A')}:{rabbitmq_status.get('port', 'N/A')}")
            print(f"  ⚠️  Ошибка: {rabbitmq_status.get('error', 'Unknown')}")
        
        # Конфигурация маршрутизации
        print(f"\n🔀 ROUTING CONFIGURATION:")
        routing = status["routing_config"]
        print(f"  🎯 Поддерживаемые системы: {', '.join(routing['systems'])}")
        print(f"  📮 Очереди: {len(routing['queues'])}")
        print(f"  🗺️  Маппинг топиков: {routing['topic_mapping_count']} правил")
        
        print("=" * 80)
        
        # Общий статус
        camunda_ok = camunda_status["status"] == "connected"
        rabbitmq_ok = rabbitmq_status["status"] == "connected"
        
        if camunda_ok and rabbitmq_ok:
            print("🟢 ОБЩИЙ СТАТУС: ГОТОВ К РАБОТЕ")
        elif camunda_ok:
            print("🟡 ОБЩИЙ СТАТУС: CAMUNDA OK, ПРОБЛЕМЫ С RABBITMQ")
        elif rabbitmq_ok:
            print("🟡 ОБЩИЙ СТАТУС: RABBITMQ OK, ПРОБЛЕМЫ С CAMUNDA")
        else:
            print("🔴 ОБЩИЙ СТАТУС: ПРОБЛЕМЫ С ПОДКЛЮЧЕНИЯМИ")
        
        print("=" * 80)


def main():
    """Основная функция"""
    try:
        checker = StatusChecker()
        checker.print_status_report()
        
    except Exception as e:
        logger.error(f"Ошибка проверки статуса: {e}")
        print(f"❌ Ошибка проверки статуса: {e}")


if __name__ == "__main__":
    main() 