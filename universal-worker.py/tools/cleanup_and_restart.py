#!/usr/bin/env python3
"""
Полная очистка и перезапуск для тестирования исправленного BPMN процесса TestProcess v5
"""

import sys
import os
import json
import requests
import pika
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config, rabbitmq_config

class CleanupAndRestart:
    def __init__(self):
        self.camunda_base_url = self._get_camunda_url()
        self.auth = self._get_camunda_auth()
        
    def _get_camunda_url(self):
        base_url = camunda_config.base_url.rstrip('/')
        if base_url.endswith('/engine-rest'):
            return base_url
        else:
            return f"{base_url}/engine-rest"
    
    def _get_camunda_auth(self):
        if camunda_config.auth_enabled:
            return (camunda_config.auth_username, camunda_config.auth_password)
        return None
    
    def _make_request(self, method, url, **kwargs):
        """Выполнение HTTP запроса к Camunda"""
        try:
            response = requests.request(method, url, auth=self.auth, timeout=30, **kwargs)
            return response
        except Exception as e:
            print(f"❌ Ошибка запроса {method} {url}: {e}")
            return None
    
    def cleanup_process_instances(self):
        """Очистка всех экземпляров процесса TestProcess"""
        print("🧹 Очистка экземпляров процесса TestProcess...")
        print("-" * 50)
        
        # 1. Получаем все экземпляры процесса TestProcess
        url = f"{self.camunda_base_url}/process-instance"
        params = {"processDefinitionKey": "TestProcess"}
        
        response = self._make_request("GET", url, params=params)
        if not response or response.status_code != 200:
            print("❌ Не удалось получить список экземпляров процесса")
            return False
        
        instances = response.json()
        print(f"📊 Найдено экземпляров процесса TestProcess: {len(instances)}")
        
        if not instances:
            print("✅ Экземпляры процесса не найдены")
            return True
        
        # 2. Удаляем каждый экземпляр
        deleted_count = 0
        for instance in instances:
            instance_id = instance.get('id')
            if instance_id:
                delete_url = f"{self.camunda_base_url}/process-instance/{instance_id}"
                response = self._make_request("DELETE", delete_url, 
                                            params={"reason": "Cleanup for new test"})
                
                if response and response.status_code == 204:
                    print(f"✅ Удален экземпляр: {instance_id}")
                    deleted_count += 1
                else:
                    print(f"❌ Не удалось удалить экземпляр: {instance_id}")
        
        print(f"📊 Удалено экземпляров: {deleted_count}/{len(instances)}")
        return deleted_count == len(instances)
    
    def cleanup_external_tasks(self):
        """Очистка всех External Tasks"""
        print("\n🧹 Очистка External Tasks...")
        print("-" * 50)
        
        # 1. Получаем все External Tasks
        url = f"{self.camunda_base_url}/external-task"
        
        response = self._make_request("GET", url)
        if not response or response.status_code != 200:
            print("❌ Не удалось получить список External Tasks")
            return False
        
        tasks = response.json()
        print(f"📊 Найдено External Tasks: {len(tasks)}")
        
        if not tasks:
            print("✅ External Tasks не найдены")
            return True
        
        # 2. Завершаем каждую задачу с ошибкой для очистки
        cleared_count = 0
        for task in tasks:
            task_id = task.get('id')
            if task_id:
                failure_url = f"{self.camunda_base_url}/external-task/{task_id}/failure"
                payload = {
                    "workerId": "cleanup-script",
                    "errorMessage": "Cleanup for new test",
                    "retries": 0,
                    "retryTimeout": 0
                }
                
                response = self._make_request("POST", failure_url, json=payload)
                
                if response and response.status_code == 204:
                    print(f"✅ Очищена задача: {task_id} (топик: {task.get('topicName', 'unknown')})")
                    cleared_count += 1
                else:
                    print(f"❌ Не удалось очистить задачу: {task_id}")
        
        print(f"📊 Очищено задач: {cleared_count}/{len(tasks)}")
        return cleared_count == len(tasks)
    
    def cleanup_rabbitmq_queues(self):
        """Очистка всех очередей RabbitMQ"""
        print("\n🧹 Очистка очередей RabbitMQ...")
        print("-" * 50)
        
        try:
            connection = pika.BlockingConnection(
                pika.URLParameters(rabbitmq_config.connection_url)
            )
            channel = connection.channel()
            
            # Список всех очередей для очистки
            queues_to_purge = [
                "camunda.responses.queue",
                "bitrix24.queue", 
                "openproject.queue",
                "1c.queue",
                "python-services.queue",
                "errors.camunda_tasks.queue",
                "camunda.default.queue"  # Если есть
            ]
            
            purged_count = 0
            for queue_name in queues_to_purge:
                try:
                    # Проверяем существование очереди
                    method = channel.queue_declare(queue=queue_name, passive=True)
                    message_count = method.method.message_count
                    
                    if message_count > 0:
                        # Очищаем очередь
                        channel.queue_purge(queue=queue_name)
                        print(f"✅ Очищена очередь: {queue_name} ({message_count} сообщений)")
                        purged_count += 1
                    else:
                        print(f"✅ Очередь уже пуста: {queue_name}")
                        
                except pika.exceptions.ChannelClosedByBroker:
                    # Очередь не существует
                    print(f"ℹ️  Очередь не существует: {queue_name}")
                    # Переоткрываем канал
                    channel = connection.channel()
                except Exception as e:
                    print(f"❌ Ошибка очистки очереди {queue_name}: {e}")
            
            connection.close()
            print(f"📊 Обработано очередей: {len(queues_to_purge)}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка подключения к RabbitMQ: {e}")
            return False
    
    def start_new_process(self):
        """Запуск нового экземпляра процесса TestProcess версии 5"""
        print("\n🚀 Запуск нового экземпляра TestProcess v5...")
        print("-" * 50)
        
        # 1. Сначала проверяем доступность версии 5
        url = f"{self.camunda_base_url}/process-definition"
        params = {"key": "TestProcess", "latestVersion": "true"}
        
        response = self._make_request("GET", url, params=params)
        if not response or response.status_code != 200:
            print("❌ Не удалось получить определения процесса")
            return False
        
        definitions = response.json()
        if not definitions:
            print("❌ Процесс TestProcess не найден")
            return False
        
        latest_def = definitions[0]
        latest_version = latest_def.get('version', 0)
        process_def_id = latest_def.get('id')
        
        print(f"📋 Найдена последняя версия процесса: {latest_version}")
        print(f"📋 ID определения процесса: {process_def_id}")
        
        if latest_version < 5:
            print(f"⚠️  Внимание: последняя версия {latest_version}, а ожидалась 5")
            print("   Возможно новая версия еще не развернута")
        
        # 2. Запускаем новый экземпляр
        start_url = f"{self.camunda_base_url}/process-definition/{process_def_id}/start"
        
        # Данные для запуска процесса
        start_payload = {
            "variables": {
                "Input_2khodeq": {
                    "value": "TestInputValue_v5",
                    "type": "String"
                },
                "user": {
                    "value": "TestUser_v5",
                    "type": "String"
                }
            },
            "businessKey": f"test-process-v{latest_version}-{int(time.time())}"
        }
        
        print(f"📤 Запуск процесса с данными:")
        print(json.dumps(start_payload, ensure_ascii=False, indent=2))
        
        response = self._make_request("POST", start_url, json=start_payload)
        
        if response and response.status_code == 200:
            result = response.json()
            instance_id = result.get('id')
            business_key = result.get('businessKey')
            
            print(f"✅ Процесс успешно запущен!")
            print(f"   Instance ID: {instance_id}")
            print(f"   Business Key: {business_key}")
            print(f"   Version: {latest_version}")
            
            return {
                "instance_id": instance_id,
                "business_key": business_key,
                "version": latest_version,
                "definition_id": process_def_id
            }
        else:
            print(f"❌ Не удалось запустить процесс")
            if response:
                print(f"   Статус: {response.status_code}")
                print(f"   Ответ: {response.text}")
            return False
    
    def verify_new_process(self, process_info):
        """Проверка состояния нового процесса"""
        print("\n🔍 Проверка состояния нового процесса...")
        print("-" * 50)
        
        if not process_info:
            return False
        
        instance_id = process_info['instance_id']
        
        # 1. Проверяем экземпляр процесса
        url = f"{self.camunda_base_url}/process-instance/{instance_id}"
        response = self._make_request("GET", url)
        
        if response and response.status_code == 200:
            instance = response.json()
            print(f"✅ Процесс активен: {instance_id}")
            print(f"   Business Key: {instance.get('businessKey')}")
            print(f"   Definition ID: {instance.get('definitionId')}")
        else:
            print(f"❌ Процесс не найден: {instance_id}")
            return False
        
        # 2. Проверяем активные External Tasks
        tasks_url = f"{self.camunda_base_url}/external-task"
        params = {"processInstanceId": instance_id}
        
        response = self._make_request("GET", tasks_url, params=params)
        
        if response and response.status_code == 200:
            tasks = response.json()
            print(f"📋 Найдено External Tasks: {len(tasks)}")
            
            for task in tasks:
                print(f"   🔧 Task ID: {task.get('id')}")
                print(f"      Topic: {task.get('topicName')}")
                print(f"      Activity: {task.get('activityId')}")
        else:
            print("❌ Не удалось получить External Tasks")
        
        return True

def main():
    """Главная функция"""
    print("🔄 ПОЛНАЯ ОЧИСТКА И ПЕРЕЗАПУСК ДЛЯ TESTPROCESS V5")
    print("=" * 60)
    print("📝 Цель: тестирование исправленного BPMN с явными условиями Gateway")
    print("   Gateway теперь использует: ${result == \"ok\"} и ${result != \"ok\"}")
    print()
    
    cleanup = CleanupAndRestart()
    
    # Подтверждение
    response = input("⚠️  Это удалит ВСЕ экземпляры TestProcess и очистит очереди. Продолжить? (yes/N): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ Операция отменена")
        return
    
    print("\n🚀 Начинаем операцию очистки и перезапуска...")
    
    # 1. Очистка экземпляров процесса
    if not cleanup.cleanup_process_instances():
        print("❌ Не удалось очистить экземпляры процесса")
        return
    
    # 2. Очистка External Tasks
    if not cleanup.cleanup_external_tasks():
        print("❌ Не удалось очистить External Tasks")
        return
    
    # 3. Очистка очередей RabbitMQ
    if not cleanup.cleanup_rabbitmq_queues():
        print("❌ Не удалось очистить очереди RabbitMQ")
        return
    
    # Пауза для стабилизации
    print("\n⏳ Пауза 3 секунды для стабилизации...")
    time.sleep(3)
    
    # 4. Запуск нового процесса
    process_info = cleanup.start_new_process()
    if not process_info:
        print("❌ Не удалось запустить новый процесс")
        return
    
    # 5. Проверка нового процесса
    if not cleanup.verify_new_process(process_info):
        print("❌ Не удалось проверить новый процесс")
        return
    
    print("\n" + "=" * 60)
    print("✅ ОПЕРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
    print(f"🎯 Новый процесс TestProcess v{process_info['version']} запущен")
    print(f"📋 Instance ID: {process_info['instance_id']}")
    print()
    print("🚀 Следующие шаги:")
    print("1. Запустите Universal Worker: python main.py")
    print("2. External Task будет отправлена в Bitrix24")
    print("3. После завершения в Bitrix - тестируйте новые условия Gateway")
    print("4. Gateway теперь ожидает переменную 'result' = \"ok\" для успеха")

if __name__ == "__main__":
    main() 