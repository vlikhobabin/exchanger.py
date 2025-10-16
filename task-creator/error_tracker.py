#!/usr/bin/env python3
"""
Система отслеживания критических ошибок для предотвращения лавины ошибок
"""
import time
from typing import List, Dict, Any
from loguru import logger


class ErrorTracker:
    """Класс для отслеживания критических ошибок"""
    
    def __init__(self, max_errors: int = 10, error_window: int = 300):
        """
        Инициализация трекера ошибок
        
        Args:
            max_errors: Максимальное количество ошибок за окно времени
            error_window: Окно времени в секундах для подсчета ошибок
        """
        self.max_errors = max_errors
        self.error_window = error_window
        self.errors: List[float] = []
        self.critical_threshold_reached = False
        
        # Статистика
        self.stats = {
            "total_errors": 0,
            "critical_events": 0,
            "last_critical_time": None,
            "error_types": {}
        }
    
    def add_error(self, error_type: str = "general", error_message: str = "") -> bool:
        """
        Добавление ошибки в трекер
        
        Args:
            error_type: Тип ошибки для категоризации
            error_message: Сообщение об ошибке
            
        Returns:
            bool: True если достигнут критический порог ошибок
        """
        current_time = time.time()
        
        # Удаляем старые ошибки (старше error_window)
        self.errors = [t for t in self.errors if current_time - t < self.error_window]
        
        # Добавляем новую ошибку
        self.errors.append(current_time)
        self.stats["total_errors"] += 1
        
        # Обновляем статистику по типам ошибок
        if error_type not in self.stats["error_types"]:
            self.stats["error_types"][error_type] = 0
        self.stats["error_types"][error_type] += 1
        
        # Проверяем, достигнут ли критический порог
        if len(self.errors) >= self.max_errors:
            if not self.critical_threshold_reached:
                self.critical_threshold_reached = True
                self.stats["critical_events"] += 1
                self.stats["last_critical_time"] = current_time
                
                logger.critical(
                    f"КРИТИЧЕСКИЙ ПОРОГ ОШИБОК ДОСТИГНУТ! "
                    f"Ошибок за {self.error_window}с: {len(self.errors)}/{self.max_errors}. "
                    f"Тип: {error_type}. Сообщение: {error_message}"
                )
                
                # Логируем детальную статистику
                self._log_critical_stats()
                
                return True
        
        # Логируем ошибку если не критическая
        logger.warning(f"Ошибка зафиксирована: {error_type} - {error_message}")
        
        return False
    
    def add_critical_error(self, error_type: str, error_message: str) -> bool:
        """
        Добавление критической ошибки (сразу увеличивает счетчик на 3)
        
        Args:
            error_type: Тип критической ошибки
            error_message: Сообщение об ошибке
            
        Returns:
            bool: True если достигнут критический порог
        """
        # Критические ошибки считаются как 3 обычные
        for _ in range(3):
            if self.add_error(error_type, error_message):
                return True
        
        return False
    
    def reset(self):
        """Сброс счетчика ошибок"""
        self.errors.clear()
        self.critical_threshold_reached = False
        logger.info("Счетчик ошибок сброшен")
    
    def get_error_rate(self) -> float:
        """
        Получение текущей частоты ошибок (ошибок в минуту)
        
        Returns:
            float: Частота ошибок в минуту
        """
        if not self.errors:
            return 0.0
        
        current_time = time.time()
        recent_errors = [t for t in self.errors if current_time - t < 60]  # За последнюю минуту
        return len(recent_errors)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики ошибок
        
        Returns:
            dict: Статистика ошибок
        """
        current_time = time.time()
        
        return {
            "total_errors": self.stats["total_errors"],
            "recent_errors_count": len(self.errors),
            "critical_events": self.stats["critical_events"],
            "error_rate_per_minute": self.get_error_rate(),
            "critical_threshold_reached": self.critical_threshold_reached,
            "last_critical_time": self.stats["last_critical_time"],
            "error_types": self.stats["error_types"].copy(),
            "time_until_reset": max(0, self.error_window - (current_time - (self.errors[0] if self.errors else current_time)))
        }
    
    def is_healthy(self) -> bool:
        """
        Проверка, находится ли система в здоровом состоянии
        
        Returns:
            bool: True если система здорова, False если есть проблемы
        """
        return len(self.errors) < self.max_errors * 0.7  # 70% от критического порога
    
    def _log_critical_stats(self):
        """Логирование критической статистики"""
        stats = self.get_stats()
        
        logger.critical("=== КРИТИЧЕСКАЯ СТАТИСТИКА ОШИБОК ===")
        logger.critical(f"Всего ошибок: {stats['total_errors']}")
        logger.critical(f"Ошибок за окно: {stats['recent_errors_count']}/{self.max_errors}")
        logger.critical(f"Частота ошибок: {stats['error_rate_per_minute']:.1f}/мин")
        logger.critical(f"Критических событий: {stats['critical_events']}")
        
        if stats['error_types']:
            logger.critical("Типы ошибок:")
            for error_type, count in stats['error_types'].items():
                logger.critical(f"  {error_type}: {count}")
        
        logger.critical("=== РЕКОМЕНДАЦИЯ: ПЕРЕЗАПУСК СЕРВИСА ===")
    
    def should_shutdown(self) -> bool:
        """
        Определение, нужно ли завершить работу сервиса
        
        Returns:
            bool: True если рекомендуется завершение работы
        """
        return self.critical_threshold_reached and len(self.errors) >= self.max_errors
