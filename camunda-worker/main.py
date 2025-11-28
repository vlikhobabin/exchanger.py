#!/usr/bin/env python3
"""
Точка входа для Universal Camunda Worker
"""
import sys
import os
import threading
import time

# Импорт env_loader ПЕРВЫМ для определения среды
sys.path.insert(0, "/opt/exchanger.py")
from env_loader import EXCHANGER_ENV, get_log_path, get_env_info

from loguru import logger

# SSL Patch - ДОЛЖЕН быть импортирован ДО ExternalTaskClient
import ssl_patch
from config import worker_config, camunda_config
from camunda_worker import UniversalCamundaWorker


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
    
    # Файловый вывод - путь зависит от среды
    logger.add(
        get_log_path("camunda-worker.log"),
        format=log_format,
        level=worker_config.log_level,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8"
    )
    
    # Файл ошибок - путь зависит от среды
    logger.add(
        get_log_path("camunda-worker-errors.log"),
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
        
        # Получаем информацию о среде
        env_info = get_env_info()
        env_label = EXCHANGER_ENV.upper()
        
        logger.info("=" * 60)
        logger.info(f"UNIVERSAL CAMUNDA WORKER [{env_label}]")
        logger.info("=" * 60)
        logger.info("Версия: 2.1.0")
        logger.info("Автор: EG-Holding")
        logger.info("Режим: Интегрированная обработка задач и ответов")
        logger.info(f"Среда: {env_info['environment']}")
        logger.info(f"Конфигурация: {env_info['env_file']}")
        logger.info(f"Директория логов: {env_info['logs_dir']}")
        
        # Информация о Camunda tenant
        if camunda_config.tenant_id:
            logger.info(f"🏢 Camunda Tenant: {camunda_config.tenant_id}")
        else:
            logger.warning("⚠️ Camunda Tenant: не указан (все тенанты)")
        
        logger.info("=" * 60)
        
        # Проверка применения SSL патча
        if ssl_patch.is_patch_applied():
            patch_info = ssl_patch.get_patch_info()
            logger.info("🔒 SSL Patch: Активен")
            logger.info(f"   - Описание: {patch_info['description']}")
            logger.info("   - Все HTTP запросы используют verify=False")
        else:
            logger.warning("⚠️  SSL Patch: НЕ применен!")
        
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