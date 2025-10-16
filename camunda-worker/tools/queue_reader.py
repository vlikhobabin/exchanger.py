#!/usr/bin/env python3
"""
Утилита для работы с сообщениями в очередях RabbitMQ
Позволяет просматривать, экспортировать и очищать очереди

КОМАНДЫ ДЛЯ РАБОТЫ:

# Список всех очередей с количеством сообщений
python queue_reader.py

# Просмотр первых 5 сообщений из очереди (по умолчанию)
python queue_reader.py bitrix24.queue

# Просмотр первых 10 сообщений из очереди
python queue_reader.py bitrix24.queue --count 10

# Просмотр сообщений из очереди ошибок
python queue_reader.py errors.camunda_tasks.queue --count 3

# Экспорт всех сообщений очереди в JSON файл
python queue_reader.py bitrix24.queue --output bitrix24_backup.json

# Экспорт сообщений из очереди ошибок
python queue_reader.py errors.camunda_tasks.queue --output errors_backup.json

# Очистка очереди с подтверждением
python queue_reader.py bitrix24.queue --clear

# Принудительная очистка очереди без подтверждения
python queue_reader.py bitrix24.sent.queue --clear --force
python '/opt/exchanger.py/camunda-worker/tools/queue_reader.py' bitrix24.sent.queue --clear --force

# Очистка очереди ошибок
python queue_reader.py errors.camunda_tasks.queue --clear --force

# Показать справку
python queue_reader.py --help
"""
import argparse
import json
import sys
import time
from typing import List, Dict, Any, Optional
import pika

# Добавление родительского каталога в sys.path для импорта модулей проекта
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import rabbitmq_config
from rabbitmq_client import RabbitMQClient


class QueueReader:
    """Класс для работы с сообщениями в очередях RabbitMQ"""
    
    def __init__(self):
        self.config = rabbitmq_config
        self.connection = None
        self.channel = None
        
    def connect(self) -> bool:
        """Подключение к RabbitMQ"""
        try:
            # Создание соединения
            credentials = pika.PlainCredentials(
                self.config.username, 
                self.config.password
            )
            
            parameters = pika.ConnectionParameters(
                host=self.config.host,
                port=self.config.port,
                virtual_host=self.config.virtual_host,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка подключения к RabbitMQ: {e}")
            return False
    
    def disconnect(self):
        """Закрытие соединения"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
        except Exception as e:
            print(f"⚠️ Ошибка при закрытии соединения: {e}")
    
    def list_queues(self):
        """Отображение списка очередей с количеством сообщений"""
        print("🐰 ОЧЕРЕДИ RABBITMQ")
        print("=" * 60)
        
        # Используем существующий RabbitMQClient для получения информации об очередях
        client = RabbitMQClient()
        
        if not client.connect():
            print("❌ Не удалось подключиться к RabbitMQ")
            return False
        
        queues_info = client.get_all_queues_info()
        
        if not queues_info:
            print("❌ Не удалось получить информацию об очередях")
            client.disconnect()
            return False
        
        total_messages = 0
        
        for queue_name, info in sorted(queues_info.items()):
            msg_count = info.get("message_count", 0)
            consumer_count = info.get("consumer_count", 0)
            total_messages += msg_count
            
            # Иконки статуса
            msg_icon = "📬" if msg_count > 0 else "📭"
            consumer_icon = "👥" if consumer_count > 0 else "🚫"
            
            print(f"\n{msg_icon} {queue_name}")
            print(f"   📨 Сообщений: {msg_count:,}")
            print(f"   {consumer_icon} Потребителей: {consumer_count}")
            
            if msg_count > 100:
                print(f"   ⚠️ Большое количество сообщений!")
            elif msg_count > 0:
                print(f"   ℹ️ Есть необработанные сообщения")
        
        print(f"\n📊 ИТОГО:")
        print(f"   Очередей: {len(queues_info)}")
        print(f"   Сообщений: {total_messages:,}")
        
        client.disconnect()
        return True
    
    def peek_messages(self, queue_name: str, count: int = 5) -> bool:
        """Просмотр первых N сообщений из очереди (без удаления)"""
        if not self.connect():
            return False
        
        try:
            print(f"👀 ПРОСМОТР СООБЩЕНИЙ ИЗ ОЧЕРЕДИ: {queue_name}")
            print("=" * 80)
            
            # Проверяем существование очереди
            try:
                method = self.channel.queue_declare(queue=queue_name, passive=True)
                msg_count = method.method.message_count
                print(f"📊 Всего сообщений в очереди: {msg_count:,}")
                
                if msg_count == 0:
                    print("📭 Очередь пуста")
                    return True
                    
            except pika.exceptions.ChannelClosedByBroker:
                print(f"❌ Очередь '{queue_name}' не существует")
                return False
            
            # Ограничиваем количество просматриваемых сообщений
            max_to_read = min(count, msg_count)
            messages_read = 0
            delivery_tags = []  # Собираем delivery_tag для возврата в конце
            
            while messages_read < max_to_read:
                # Получаем сообщение без автоподтверждения
                method_frame, header_frame, body = self.channel.basic_get(
                    queue=queue_name, 
                    auto_ack=False
                )
                
                if method_frame is None:
                    break  # Нет больше сообщений
                
                messages_read += 1
                delivery_tags.append(method_frame.delivery_tag)
                
                # Парсим сообщение
                try:
                    message_data = json.loads(body.decode('utf-8'))
                    formatted_message = json.dumps(message_data, ensure_ascii=False, indent=2)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    formatted_message = body.decode('utf-8', errors='replace')
                
                # Информация о сообщении
                print(f"\n📨 СООБЩЕНИЕ #{messages_read}")
                print(f"├─ Delivery Tag: {method_frame.delivery_tag}")
                print(f"├─ Exchange: {method_frame.exchange}")
                print(f"├─ Routing Key: {method_frame.routing_key}")
                print(f"├─ Redelivered: {'Да' if method_frame.redelivered else 'Нет'}")
                
                if header_frame:
                    print(f"├─ Content Type: {header_frame.content_type}")
                    if header_frame.timestamp:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', 
                                               time.localtime(header_frame.timestamp))
                        print(f"├─ Timestamp: {timestamp}")
                    if header_frame.headers:
                        print(f"├─ Headers: {header_frame.headers}")
                
                print(f"└─ Содержимое:")
                print(f"   {formatted_message}")
            
            # Возвращаем ВСЕ сообщения в очередь в конце
            for delivery_tag in delivery_tags:
                self.channel.basic_nack(
                    delivery_tag=delivery_tag, 
                    requeue=True
                )
            
            if messages_read > 0:
                print(f"\n✅ Просмотрено {messages_read} из {max_to_read} сообщений")
                print("ℹ️ Сообщения возвращены в очередь")
            else:
                print("📭 Сообщения не найдены")
                
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при просмотре сообщений: {e}")
            return False
        finally:
            self.disconnect()
    
    def export_messages(self, queue_name: str, output_file: str) -> bool:
        """Экспорт всех сообщений из очереди в JSON файл"""
        if not self.connect():
            return False
        
        try:
            print(f"💾 ЭКСПОРТ СООБЩЕНИЙ ИЗ ОЧЕРЕДИ: {queue_name}")
            print(f"📄 Файл: {output_file}")
            print("=" * 80)
            
            # Проверяем существование очереди
            try:
                method = self.channel.queue_declare(queue=queue_name, passive=True)
                msg_count = method.method.message_count
                print(f"📊 Всего сообщений в очереди: {msg_count:,}")
                
                if msg_count == 0:
                    print("📭 Очередь пуста, нечего экспортировать")
                    return True
                    
            except pika.exceptions.ChannelClosedByBroker:
                print(f"❌ Очередь '{queue_name}' не существует")
                return False
            
            messages = []
            messages_read = 0
            delivery_tags = []  # Собираем delivery_tag для возврата в конце
            
            print("🔄 Чтение сообщений...")
            
            # Читаем не больше сообщений, чем есть в очереди
            while messages_read < msg_count:
                method_frame, header_frame, body = self.channel.basic_get(
                    queue=queue_name, 
                    auto_ack=False
                )
                
                if method_frame is None:
                    break  # Нет больше сообщений
                
                messages_read += 1
                delivery_tags.append(method_frame.delivery_tag)
                
                # Формируем данные сообщения
                message_info = {
                    "message_number": messages_read,
                    "delivery_tag": method_frame.delivery_tag,
                    "exchange": method_frame.exchange,
                    "routing_key": method_frame.routing_key,
                    "redelivered": method_frame.redelivered,
                    "properties": {},
                    "body": None,
                    "body_raw": body.decode('utf-8', errors='replace')
                }
                
                # Свойства сообщения
                if header_frame:
                    if header_frame.content_type:
                        message_info["properties"]["content_type"] = header_frame.content_type
                    if header_frame.timestamp:
                        message_info["properties"]["timestamp"] = header_frame.timestamp
                        message_info["properties"]["timestamp_human"] = time.strftime(
                            '%Y-%m-%d %H:%M:%S', time.localtime(header_frame.timestamp)
                        )
                    if header_frame.headers:
                        message_info["properties"]["headers"] = header_frame.headers
                
                # Пытаемся парсить JSON
                try:
                    message_info["body"] = json.loads(body.decode('utf-8'))
                    message_info["body_type"] = "json"
                except (json.JSONDecodeError, UnicodeDecodeError):
                    message_info["body"] = body.decode('utf-8', errors='replace')
                    message_info["body_type"] = "text"
                
                messages.append(message_info)
                
                # Показываем прогресс каждые 100 сообщений
                if messages_read % 100 == 0:
                    print(f"   Прочитано: {messages_read:,} сообщений...")
            
            # Возвращаем ВСЕ сообщения в очередь в конце
            for delivery_tag in delivery_tags:
                self.channel.basic_nack(
                    delivery_tag=delivery_tag, 
                    requeue=True
                )
            
            # Сохраняем в файл
            export_data = {
                "export_info": {
                    "queue_name": queue_name,
                    "timestamp": int(time.time() * 1000),
                    "timestamp_human": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "total_messages": len(messages),
                    "rabbitmq_host": self.config.host,
                    "rabbitmq_port": self.config.port
                },
                "messages": messages
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Экспорт завершен:")
            print(f"   📊 Сообщений: {len(messages):,}")
            print(f"   📄 Файл: {output_file}")
            print(f"   💾 Размер: {os.path.getsize(output_file):,} байт")
            print("ℹ️ Сообщения возвращены в очередь")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при экспорте: {e}")
            return False
        finally:
            self.disconnect()
    
    def clear_queue(self, queue_name: str, force: bool = False) -> bool:
        """Очистка очереди с подтверждением"""
        if not self.connect():
            return False
        
        try:
            print(f"🗑️ ОЧИСТКА ОЧЕРЕДИ: {queue_name}")
            print("=" * 60)
            
            # Проверяем существование очереди и количество сообщений
            try:
                method = self.channel.queue_declare(queue=queue_name, passive=True)
                msg_count = method.method.message_count
                print(f"📊 Сообщений в очереди: {msg_count:,}")
                
                if msg_count == 0:
                    print("📭 Очередь уже пуста")
                    return True
                    
            except pika.exceptions.ChannelClosedByBroker:
                print(f"❌ Очередь '{queue_name}' не существует")
                return False
            
            # Подтверждение удаления
            if not force:
                print(f"\n⚠️ ВНИМАНИЕ!")
                print(f"Вы собираетесь УДАЛИТЬ {msg_count:,} сообщений из очереди '{queue_name}'")
                print("Это действие НЕОБРАТИМО!")
                
                confirmation = input("\nВведите 'YES' для подтверждения: ").strip()
                
                if confirmation != 'YES':
                    print("❌ Операция отменена")
                    return False
            
            # Очистка очереди
            print(f"\n🔄 Очистка очереди...")
            self.channel.queue_purge(queue=queue_name)
            
            # Проверяем результат
            method = self.channel.queue_declare(queue=queue_name, passive=True)
            remaining_count = method.method.message_count
            
            if remaining_count == 0:
                print(f"✅ Очередь '{queue_name}' успешно очищена")
                print(f"🗑️ Удалено сообщений: {msg_count:,}")
                return True
            else:
                print(f"⚠️ В очереди осталось {remaining_count:,} сообщений")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка при очистке очереди: {e}")
            return False
        finally:
            self.disconnect()


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Утилита для работы с сообщениями в очередях RabbitMQ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Список всех очередей с количеством сообщений
  python queue_reader.py

  # Просмотр первых 5 сообщений из очереди
  python queue_reader.py errors.camunda_tasks.queue

  # Просмотр первых 10 сообщений из очереди
  python queue_reader.py errors.camunda_tasks.queue --count 10

  # Экспорт всех сообщений в JSON файл
  python queue_reader.py errors.camunda_tasks.queue --output errors_backup.json

  # Очистка очереди (с подтверждением)
  python queue_reader.py errors.camunda_tasks.queue --clear

  # Принудительная очистка очереди (без подтверждения)
  python queue_reader.py errors.camunda_tasks.queue --clear --force
        """
    )
    
    parser.add_argument(
        "queue", 
        nargs="?", 
        help="Имя очереди для работы"
    )
    
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=5,
        help="Количество сообщений для просмотра (по умолчанию: 5)"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Экспорт всех сообщений в JSON файл"
    )
    
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Очистить очередь (удалить все сообщения)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительная очистка без подтверждения"
    )
    
    args = parser.parse_args()
    
    reader = QueueReader()
    
    try:
        # Если очередь не указана - показываем список очередей
        if not args.queue:
            return reader.list_queues()
        
        # Очистка очереди
        if args.clear:
            return reader.clear_queue(args.queue, args.force)
        
        # Экспорт в файл
        if args.output:
            return reader.export_messages(args.queue, args.output)
        
        # Просмотр сообщений
        return reader.peek_messages(args.queue, args.count)
        
    except KeyboardInterrupt:
        print("\n⚠️ Операция прервана пользователем")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)