#!/usr/bin/env python3
"""
Модуль настройки логирования для утилит camunda-sync.py
Обеспечивает полноценное логирование (консоль + файлы) для всех утилит в папке tools/
"""
import os
import sys
from pathlib import Path
from loguru import logger


def setup_tool_logging(tool_name: str, log_level: str = "INFO") -> bool:
    """
    Настроить полноценное логирование для утилиты (консоль + файлы)
    Аналогично логированию в main.py, но адаптировано для утилит в tools/
    
    Args:
        tool_name: Имя утилиты (используется в логах)
        log_level: Уровень логирования
        
    Returns:
        True если настройка успешна
    """
    try:
        # Удаление существующих обработчиков
        logger.remove()
        
        # Единый формат логирования (такой же как в main.py)
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        
        # Консольный вывод с цветами (только указанный уровень)
        logger.add(
            sys.stdout,
            format=log_format,
            level=log_level,  # Консоль: INFO, WARNING, ERROR
            colorize=True
        )
        
        # Определяем путь к папке logs (относительно tools/)
        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        # Основной файл логов (ВСЕ сообщения включая DEBUG)
        main_log_file = logs_dir / f"tool_{tool_name}.log"
        logger.add(
            str(main_log_file),
            format=log_format,
            level="DEBUG",  # Файл: ВСЕ сообщения (DEBUG, INFO, WARNING, ERROR)
            rotation="50 MB",  # Меньше чем для основного сервиса
            retention="14 days",  # Короче период хранения для утилит
            compression="zip",
            encoding="utf-8"
        )
        
        # Отдельный файл для ошибок
        error_log_file = logs_dir / f"tool_{tool_name}_errors.log"
        logger.add(
            str(error_log_file),
            format=log_format,
            level="ERROR",
            rotation="25 MB",
            retention="30 days",  # Ошибки храним дольше
            compression="zip",
            encoding="utf-8"
        )
        
        # Логируем успешную настройку
        logger.info(f"✅ Полноценное логирование настроено для утилиты '{tool_name}'")
        logger.info(f"   Основной лог: {main_log_file} (уровень: DEBUG - все сообщения)")
        logger.info(f"   Лог ошибок: {error_log_file}")
        logger.info(f"   Консоль: уровень {log_level} и выше")
        
        return True
        
    except Exception as e:
        # Аварийный fallback - базовое консольное логирование
        logger.remove()
        logger.add(sys.stdout, level="ERROR", format="{time:HH:mm:ss} | {level} | {message}")
        logger.error(f"❌ Ошибка настройки логирования для утилиты '{tool_name}': {e}")
        return False


def setup_simple_console_logging(log_level: str = "INFO"):
    """
    Настроить упрощенное консольное логирование (без файлов)
    Для случаев, когда нужно быстро настроить логирование без файлов
    
    Args:
        log_level: Уровень логирования
    """
    try:
        logger.remove()
        
        # Упрощенный формат для консоли
        simple_format = "{time:HH:mm:ss} | <level>{level}</level> | <level>{message}</level>"
        
        logger.add(
            sys.stdout,
            format=simple_format,
            level=log_level,
            colorize=True
        )
        
        logger.debug(f"Упрощенное консольное логирование настроено (уровень: {log_level})")
        
    except Exception as e:
        # Совсем аварийный fallback
        logger.remove()
        logger.add(sys.stdout, level="ERROR")
        logger.error(f"Ошибка настройки упрощенного логирования: {e}")


def get_logs_directory() -> Path:
    """
    Получить путь к папке логов для утилит
    
    Returns:
        Path: Путь к папке logs/
    """
    return Path(__file__).parent.parent / "logs"


def list_tool_log_files() -> list:
    """
    Получить список файлов логов утилит
    
    Returns:
        list: Список файлов логов утилит
    """
    try:
        logs_dir = get_logs_directory()
        if not logs_dir.exists():
            return []
        
        # Ищем файлы с префиксом tool_
        tool_logs = []
        for log_file in logs_dir.glob("tool_*.log*"):
            tool_logs.append(log_file)
        
        return sorted(tool_logs, key=lambda x: x.stat().st_mtime, reverse=True)
        
    except Exception as e:
        logger.error(f"Ошибка получения списка файлов логов: {e}")
        return []


# Демонстрация использования
if __name__ == "__main__":
    print("=== Демонстрация модуля логирования для camunda-sync.py/tools/ ===\n")
    
    # Настройка полноценного логирования
    print("1. Настройка полноценного логирования:")
    setup_tool_logging("demo_tool", "INFO")  # Консоль: INFO+, файлы: все
    
    logger.debug("Это отладочное сообщение (только в файле)")
    logger.info("Это информационное сообщение (консоль + файл)")
    logger.warning("Это предупреждение (консоль + файл)") 
    logger.error("Это ошибка (консоль + файл)")
    
    print(f"\n2. Информация о папке логов:")
    logs_dir = get_logs_directory()
    print(f"   Папка логов: {logs_dir}")
    print(f"   Существует: {logs_dir.exists()}")
    
    if logs_dir.exists():
        tool_logs = list_tool_log_files()
        print(f"   Найдено файлов логов утилит: {len(tool_logs)}")
        for log_file in tool_logs[:3]:  # Показываем первые 3
            print(f"     - {log_file.name}")
    
    print("\n3. Упрощенное консольное логирование:")
    setup_simple_console_logging("INFO")
    logger.info("Упрощенное сообщение")
    
    print("\n✅ Демонстрация завершена.")
    print("📁 Проверьте папку 'logs/' для файлов логов утилит.")
