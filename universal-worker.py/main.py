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
from response_handler import TaskResponseHandler


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
        logger.info("UNIVERSAL CAMUNDA WORKER (ASYNC MODE)")
        logger.info("=" * 60)
        logger.info("Версия: 2.0.0")
        logger.info("Автор: EG-Holding")
        logger.info("Режим: Асинхронное завершение задач")
        logger.info("=" * 60)
        
        # Создание компонентов
        worker = UniversalCamundaWorker()
        response_handler = TaskResponseHandler()
        
        # Флаги для управления потоками
        worker_running = threading.Event()
        response_handler_running = threading.Event()
        shutdown_event = threading.Event()
        
        def run_worker():
            """Запуск основного worker в отдельном потоке"""
            try:
                logger.info("Запуск Camunda Worker...")
                worker_running.set()
                worker.start()
            except Exception as e:
                logger.error(f"Ошибка в Camunda Worker: {e}")
            finally:
                worker_running.clear()
                shutdown_event.set()
        
        def run_response_handler():
            """Запуск response handler в отдельном потоке"""
            try:
                if not worker_config.response_handler_enabled:
                    logger.info("Response Handler отключен в конфигурации")
                    return
                
                # Ожидание инициализации основного worker
                time.sleep(5)
                
                logger.info("Запуск Task Response Handler...")
                response_handler_running.set()
                response_handler.start()
            except Exception as e:
                logger.error(f"Ошибка в Response Handler: {e}")
            finally:
                response_handler_running.clear()
                shutdown_event.set()
        
        # Запуск потоков
        worker_thread = threading.Thread(target=run_worker, daemon=True)
        response_thread = threading.Thread(target=run_response_handler, daemon=True)
        
        worker_thread.start()
        response_thread.start()
        
        logger.info("Оба компонента запущены")
        logger.info("- Camunda Worker: обработка External Tasks")
        logger.info("- Response Handler: асинхронное завершение задач")
        logger.info("Нажмите Ctrl+C для завершения")
        
        # Ожидание завершения
        try:
            while not shutdown_event.is_set():
                # Проверка состояния потоков каждые 10 секунд
                if shutdown_event.wait(10):
                    break
                
                # Логирование состояния
                worker_status = "работает" if worker_running.is_set() else "остановлен"
                handler_status = "работает" if response_handler_running.is_set() else "остановлен"
                logger.info(f"Статус - Worker: {worker_status}, Response Handler: {handler_status}")
                
                # Если один из компонентов упал, завершаем всё
                if not worker_running.is_set() and not response_handler_running.is_set():
                    logger.error("Все компоненты остановлены, завершение приложения")
                    break
                    
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания от пользователя")
        
        # Корректное завершение
        logger.info("Завершение работы компонентов...")
        
        if worker_running.is_set():
            worker.shutdown()
        
        if response_handler_running.is_set():
            response_handler.shutdown()
        
        # Ожидание завершения потоков
        worker_thread.join(timeout=10)
        response_thread.join(timeout=10)
        
        logger.info("Все компоненты корректно завершены")
            
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 