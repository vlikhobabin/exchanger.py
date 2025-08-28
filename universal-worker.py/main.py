#!/usr/bin/env python3
"""
Точка входа для Universal Camunda Worker
"""
import sys
import os
import threading
import time
from loguru import logger

from config import worker_config
from camunda_worker import UniversalCamundaWorker


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
    
    # Файловый вывод
    logger.add(
        "logs/camunda_worker.log",
        format=log_format,
        level=worker_config.log_level,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8"
    )
    
    # Файл ошибок
    logger.add(
        "logs/camunda_worker_errors.log",
        format=log_format,
        level="ERROR",
        rotation="50 MB",
        retention="60 days",
        compression="zip",
        encoding="utf-8"
    )


def create_directories():
    """Создание необходимых директорий"""
    directories = ["logs"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def main():
    """Основная функция"""
    try:
        # Создание директорий
        create_directories()
        
        # Настройка логирования
        setup_logging()
        
        logger.info("=" * 60)
        logger.info("UNIVERSAL CAMUNDA WORKER (INTEGRATED MODE)")
        logger.info("=" * 60)
        logger.info("Версия: 2.1.0")
        logger.info("Автор: EG-Holding")
        logger.info("Режим: Интегрированная обработка задач и ответов")
        logger.info("=" * 60)
        
        # Создание основного worker
        worker = UniversalCamundaWorker()
        
        # Флаг для управления работой
        worker_running = threading.Event()
        shutdown_event = threading.Event()
        
        def run_worker():
            """Запуск основного worker в отдельном потоке"""
            try:
                logger.info("Запуск Universal Camunda Worker...")
                worker_running.set()
                worker.start()
            except Exception as e:
                logger.error(f"Ошибка в Universal Camunda Worker: {e}")
            finally:
                worker_running.clear()
                shutdown_event.set()
        
        # Запуск worker
        worker_thread = threading.Thread(target=run_worker, daemon=True)
        worker_thread.start()
        
        logger.info("Universal Camunda Worker запущен")
        logger.info("- External Tasks: обработка задач из Camunda")
        logger.info("- Response Processing: встроенная обработка ответов из RabbitMQ")
        logger.info(f"- Heartbeat Interval: {worker_config.heartbeat_interval}s")
        logger.info("Нажмите Ctrl+C для завершения")
        
        # Ожидание завершения
        try:
            while not shutdown_event.is_set():
                # Проверка состояния worker с интервалом HEARTBEAT_INTERVAL
                if shutdown_event.wait(worker_config.heartbeat_interval):
                    break
                
                # Логирование состояния только при изменении или проблемах
                if not worker_running.is_set():
                    logger.error("Worker остановлен, завершение приложения")
                    break
                    
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания от пользователя")
        
        # Корректное завершение
        logger.info("Завершение работы...")
        
        if worker_running.is_set():
            worker.shutdown()
        
        # Ожидание завершения потока
        worker_thread.join(timeout=10)
        
        logger.info("Universal Camunda Worker корректно завершен")
            
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 