#!/usr/bin/env python3
"""
Проверка состояния RabbitMQ очередей
"""

# Добавление родительского каталога в sys.path для импорта модулей проекта
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rabbitmq_client import RabbitMQClient

def main():
    """Проверить состояние всех очередей"""
    print("🐰 ПРОВЕРКА RABBITMQ ОЧЕРЕДЕЙ")
    print("=" * 40)
    
    client = RabbitMQClient()
    
    if client.connect():
        print("✅ Подключение к RabbitMQ успешно")
        
        # Получение информации об очередях
        queues_info = client.get_all_queues_info()
        
        # Получение информации об Alternate Exchange
        ae_info = client.get_alternate_exchange_info()
        
        if ae_info:
            print(f"\n🔄 Alternate Exchange: {ae_info.get('alternate_exchange')}")
            print(f"   Тип: {ae_info.get('type')}")
            print(f"   Описание: {ae_info.get('description')}")
        
        if queues_info:
            print(f"\n📊 Найдено очередей: {len(queues_info)}")
            
            for queue_name, info in queues_info.items():
                msg_count = info.get("message_count", 0)
                consumer_count = info.get("consumer_count", 0)
                source = info.get("source", "direct")
                
                status_icon = "📬" if msg_count > 0 else "📭"
                consumer_icon = "👥" if consumer_count > 0 else "🚫"
                source_icon = "🔄" if source == "alternate_exchange" else "🎯"
                
                print(f"\n{status_icon} {queue_name}: {source_icon}")
                print(f"   📨 Сообщений: {msg_count}")
                print(f"   {consumer_icon} Потребителей: {consumer_count}")
                
                if source == "alternate_exchange":
                    ae_name = info.get("alternate_exchange", "N/A")
                    print(f"   🔄 Источник: Alternate Exchange ({ae_name})")
                
                if msg_count > 0:
                    print(f"   ⚠️ В очереди есть необработанные сообщения!")
        else:
            print("❌ Не удалось получить информацию об очередях")
        
        client.disconnect()
    else:
        print("❌ Не удалось подключиться к RabbitMQ")

if __name__ == "__main__":
    main() 