#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Универсальный Worker для обработки сообщений RabbitMQ
Обрабатывает сообщения из RabbitMQ для различных внешних систем
"""
import sys
import os

# Импорт env_loader ПЕРВЫМ для определения среды
sys.path.insert(0, "/opt/exchanger.py")
from env_loader import EXCHANGER_ENV, get_log_path, get_env_info

from loguru import logger

from config import worker_config, rabbitmq_config, systems_config
from message_processor import MessageProcessor
from instance_lock import InstanceLock


def setup_logging():
    """Настройка логирования с учетом среды выполнения"""
    # Удаление стандартного обработчика
    logger.remove()
    
    # Получаем метку среды для логов
    env_label = EXCHANGER_ENV.upper()
    
    # Настройка форматирования с меткой среды
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        f"<magenta>[{env_label}]</magenta> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Консольный вывод
    logger.add(
        sys.stdout,
        format=log_format,
        level=worker_config.log_level,
        colorize=True
    )
    
    # Файловый вывод с оптимизированной ротацией - путь зависит от среды
    logger.add(
        get_log_path("task-creator.log"),
        format=log_format,
        level=worker_config.log_level,
        rotation="20 MB",  # Уменьшено с 100MB для более частой ротации
        retention="14 days",  # Уменьшено с 30 дней
        compression="zip",
        encoding="utf-8"
    )
    
    # Файл ошибок - путь зависит от среды
    logger.add(
        get_log_path("task-creator-errors.log"),
        format=log_format,
        level="ERROR",
        rotation="20 MB",
        retention="14 days",
        compression="zip",
        encoding="utf-8"
    )


def main():
    """Главная функция"""
    try:
        # Настройка логирования
        setup_logging()
        
        # Получаем информацию о среде
        env_info = get_env_info()
        env_label = EXCHANGER_ENV.upper()
        
        logger.info("=" * 60)
        logger.info(f"UNIVERSAL RABBITMQ WORKER [{env_label}]")
        logger.info("=" * 60)
        logger.info("Версия: 1.0.0")
        logger.info("Универсальная обработка сообщений из RabbitMQ для внешних систем")
        logger.info(f"Среда: {env_info['environment']}")
        logger.info(f"Конфигурация: {env_info['env_file']}")
        logger.info(f"Директория логов: {env_info['logs_dir']}")
        logger.info("=" * 60)
        
        # Вывод конфигурации
        logger.info("Конфигурация:")
        logger.info(f"  RabbitMQ Host: {rabbitmq_config.host}:{rabbitmq_config.port}")
        logger.info(f"  RabbitMQ User: {rabbitmq_config.username}")
        logger.info(f"  Heartbeat Interval: {worker_config.heartbeat_interval}s")
        logger.info(f"  Log Level: {worker_config.log_level}")
        logger.info(f"  Retry Attempts: {worker_config.retry_attempts}")
        
        # Вывод информации о доступных системах
        systems_status = systems_config.get_systems_status()
        logger.info("Статус интеграций:")
        for queue_name, status_info in systems_status.items():
            status_icon = "✓" if status_info["status"] == "active" else "✗"
            logger.info(f"  {status_icon} {queue_name} - {status_info['description']} ({status_info['status']})")
            if status_info["error"]:
                logger.warning(f"    Ошибка: {status_info['error']}")
        
        active_queues = systems_config.get_active_queues()
        logger.info(f"Активных интеграций: {len(active_queues)}")
        
        # Проверка и захват файловой блокировки для предотвращения наложения инстансов
        with InstanceLock() as instance_lock:
            logger.info("Файловая блокировка захвачена успешно")
            
            # Создание и запуск обработчика сообщений
            processor = MessageProcessor()
            
            logger.info("Запуск Universal RabbitMQ Worker...")
            logger.info("Нажмите Ctrl+C для завершения")
            
            # Запуск основного цикла
            success = processor.start()
        
        if success:
            logger.info("Universal RabbitMQ Worker завершен успешно")
        else:
            logger.error("Universal RabbitMQ Worker завершен с ошибками")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания от пользователя")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 