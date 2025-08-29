#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль синхронизации схем процессов между StormBPMN и Camunda
"""
import sys
from loguru import logger

from config import worker_config, stormbpmn_config, camunda_config, sync_config


def setup_logging():
    """Настройка логирования"""
    import os
    
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
        "logs/camunda_sync.log",
        format=log_format,
        level=worker_config.log_level,
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8"
    )
    
    # Отдельный файл для ошибок
    logger.add(
        "logs/camunda_sync_errors.log",
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
        logger.info("CAMUNDA-STORMBPMN SYNC MODULE")
        logger.info("=" * 60)
        logger.info("Версия: 1.0.0")
        logger.info("Синхронизация схем процессов между StormBPMN и Camunda")
        logger.info("=" * 60)
        
        # Вывод конфигурации
        logger.info("Конфигурация:")
        logger.info(f"  StormBPMN URL: {stormbpmn_config.base_url}")
        logger.info(f"  Camunda URL: {camunda_config.base_url}")
        logger.info(f"  Синхронизация включена: {sync_config.sync_enabled}")
        logger.info(f"  Интервал синхронизации: {sync_config.sync_interval}s")
        logger.info(f"  Log Level: {worker_config.log_level}")
        
        # Проверка токена StormBPMN
        if not stormbpmn_config.bearer_token:
            logger.warning("STORMBPMN_BEARER_TOKEN не установлен!")
            logger.info("Для работы модуля необходимо установить переменную окружения STORMBPMN_BEARER_TOKEN")
            
        # TODO: Здесь будет инициализация и запуск сервисов синхронизации
        logger.info("Инициализация модуля синхронизации...")
        
        # Пример тестирования первого класса
        from stormbpmn_client import StormBPMNClient
        
        client = StormBPMNClient()
        logger.info("StormBPMN Client создан успешно")
        
        # Тестовый запрос списка диаграмм
        if stormbpmn_config.bearer_token:
            logger.info("Тестирование получения списка диаграмм...")
            try:
                diagrams = client.get_diagrams_list(size=5)
                logger.info(f"Получено {len(diagrams.get('content', []))} диаграмм")
                
                # Показать информацию о первой диаграмме
                if diagrams.get('content'):
                    first_diagram = diagrams['content'][0]
                    logger.info(f"Первая диаграмма: {first_diagram.get('name')} (ID: {first_diagram.get('id')})")
                    
            except Exception as e:
                logger.error(f"Ошибка при получении списка диаграмм: {e}")
        else:
            logger.warning("Тестирование пропущено - не установлен токен")
        
        logger.info("Camunda-StormBPMN Sync Module инициализирован")
        logger.info("Нажмите Ctrl+C для завершения")
        
        # Основной цикл (пока только заглушка)
        try:
            import time
            while True:
                time.sleep(10)
                logger.debug("Heartbeat...")
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания от пользователя")
            
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания от пользователя")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 