#!/usr/bin/env python3
"""
Скрипт для очистки очереди ответов от проблемных сообщений
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rabbitmq_client import RabbitMQClient
from config import rabbitmq_config

def clear_response_queue():
    """Очистка очереди ответов"""
    client = RabbitMQClient()
    
    try:
        if not client.connect():
            print("❌ Не удалось подключиться к RabbitMQ")
            return False
        
        # Проверяем количество сообщений
        queue_info = client.get_queue_info(rabbitmq_config.responses_queue_name)
        if not queue_info:
            print("❌ Не удалось получить информацию об очереди")
            return False
        
        message_count = queue_info.get("message_count", 0)
        print(f"📊 В очереди {rabbitmq_config.responses_queue_name}: {message_count} сообщений")
        
        if message_count == 0:
            print("✅ Очередь уже пуста")
            return True
        
        # Подтверждение очистки
        print(f"\n⚠️  ВНИМАНИЕ: Будут удалены ВСЕ {message_count} сообщений из очереди!")
        response = input("Продолжить? (введите 'yes' для подтверждения): ").lower().strip()
        
        if response not in ['yes', 'y', 'да', 'д']:
            print("❌ Операция отменена")
            return False
        
        # Очистка очереди
        print(f"\n🗑️ Очистка очереди...")
        cleared_count = 0
        
        while True:
            # Получаем сообщение без автоподтверждения
            method_frame, header_frame, body = client.channel.basic_get(
                queue=rabbitmq_config.responses_queue_name,
                auto_ack=True  # Автоматически удаляем
            )
            
            if method_frame is None:
                break  # Нет больше сообщений
            
            cleared_count += 1
            
            # Показываем прогресс каждые 10 сообщений
            if cleared_count % 10 == 0 or cleared_count == message_count:
                print(f"   Удалено: {cleared_count}/{message_count}")
        
        print(f"\n✅ Очистка завершена: удалено {cleared_count} сообщений")
        
        # Проверяем что очередь действительно пуста
        final_queue_info = client.get_queue_info(rabbitmq_config.responses_queue_name)
        if final_queue_info:
            final_count = final_queue_info.get("message_count", 0)
            if final_count == 0:
                print("✅ Очередь полностью очищена")
            else:
                print(f"⚠️ В очереди осталось {final_count} сообщений")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        client.disconnect()

def peek_messages(count=5):
    """Просмотр нескольких сообщений без удаления"""
    client = RabbitMQClient()
    
    try:
        if not client.connect():
            print("❌ Не удалось подключиться к RabbitMQ")
            return
        
        print(f"\n👀 Просмотр первых {count} сообщений:")
        print("=" * 50)
        
        viewed_count = 0
        
        for i in range(count):
            # Получаем сообщение без удаления
            method_frame, header_frame, body = client.channel.basic_get(
                queue=rabbitmq_config.responses_queue_name,
                auto_ack=False
            )
            
            if method_frame is None:
                print("(больше сообщений нет)")
                break
            
            viewed_count += 1
            
            try:
                message_data = json.loads(body.decode('utf-8'))
                task_id = message_data.get("original_message", {}).get("task_id", "unknown")
                status = message_data.get("processing_status", "unknown")
                
                print(f"\n📨 Сообщение #{viewed_count}:")
                print(f"   Task ID: {task_id}")
                print(f"   Status: {status}")
                print(f"   Size: {len(body)} bytes")
                
                # Возвращаем сообщение обратно в очередь
                client.channel.basic_nack(
                    delivery_tag=method_frame.delivery_tag, 
                    requeue=True
                )
                
            except Exception as e:
                print(f"   ❌ Ошибка парсинга: {e}")
                # Возвращаем проблемное сообщение обратно
                client.channel.basic_nack(
                    delivery_tag=method_frame.delivery_tag, 
                    requeue=True
                )
        
        if viewed_count == 0:
            print("📭 Очередь пуста")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        client.disconnect()

def main():
    """Главная функция"""
    print("🧹 Очистка очереди ответов Universal Camunda Worker")
    print("=" * 60)
    
    while True:
        print("\nВыберите действие:")
        print("1. Просмотреть сообщения в очереди")
        print("2. Очистить очередь полностью")
        print("3. Выход")
        
        choice = input("\nВведите номер (1-3): ").strip()
        
        if choice == "1":
            peek_messages()
        elif choice == "2":
            clear_response_queue()
        elif choice == "3":
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор, попробуйте снова")

if __name__ == "__main__":
    main() 