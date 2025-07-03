#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Универсальный Worker для обработки сообщений RabbitMQ
Обрабатывает сообщения из RabbitMQ для различных внешних систем
"""
import sys
import os
from loguru import logger

from config import worker_config, rabbitmq_config, systems_config
from message_processor import MessageProcessor


def setup_logging():
    """Настройка логирования"""
    # Удаление стандартного обработчика
    logger.remove()
    
    # Настройка форматирования
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
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
    
    # Создание директории для логов
    os.makedirs("logs", exist_ok=True)
    
    # Файловый вывод
    logger.add(
        "logs/worker.log",
        format=log_format,
        level=worker_config.log_level,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8"
    )
    
    # Файл ошибок
    logger.add(
        "logs/worker_errors.log",
        format=log_format,
        level="ERROR",
        rotation="50 MB",
        retention="60 days",
        compression="zip",
        encoding="utf-8"
    )


def main():
    """Главная функция"""
    try:
        # Настройка логирования
        setup_logging()
        
        logger.info("=" * 60)
        logger.info("UNIVERSAL RABBITMQ WORKER")
        logger.info("=" * 60)
        logger.info("Версия: 1.0.0")
        logger.info("Универсальная обработка сообщений из RabbitMQ для внешних систем")
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