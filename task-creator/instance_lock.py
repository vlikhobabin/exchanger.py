#!/usr/bin/env python3
"""
Файловая блокировка для предотвращения запуска нескольких инстансов
"""
import fcntl
import os
import sys
import time
from typing import Optional
from loguru import logger

# Импорт env_loader для определения среды
sys.path.insert(0, "/opt/exchanger.py")
from env_loader import EXCHANGER_ENV


class InstanceLock:
    """Класс для файловой блокировки инстанса"""
    
    def __init__(self, lock_file: str = None):
        # Разные lock-файлы для разных сред (prod/dev)
        if lock_file is None:
            lock_file = f"/tmp/exchanger-task-creator-{EXCHANGER_ENV}.lock"
        self.lock_file = lock_file
        self.lock_fd: Optional[int] = None
        self.pid: int = os.getpid()
    
    def acquire(self) -> bool:
        """
        Попытка захвата блокировки
        
        Returns:
            bool: True если блокировка захвачена, False если уже заблокировано
        """
        try:
            # Открываем файл для записи
            self.lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
            
            # Пытаемся захватить эксклюзивную блокировку (неблокирующая)
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Записываем PID процесса в lock file
            lock_info = f"PID: {self.pid}\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            os.write(self.lock_fd, lock_info.encode('utf-8'))
            os.fsync(self.lock_fd)  # Принудительная запись на диск
            
            logger.info(f"Файловая блокировка захвачена: {self.lock_file} (PID: {self.pid})")
            return True
            
        except (OSError, IOError) as e:
            # Блокировка уже захвачена другим процессом
            if self.lock_fd is not None:
                os.close(self.lock_fd)
                self.lock_fd = None
            
            logger.error(f"Не удалось захватить блокировку {self.lock_file}: {e}")
            logger.error("Возможно, уже запущен другой инстанс exchanger-task-creator")
            return False
    
    def release(self):
        """Освобождение блокировки"""
        try:
            if self.lock_fd is not None:
                # Снимаем блокировку
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                self.lock_fd = None
                
                # Удаляем lock file
                if os.path.exists(self.lock_file):
                    os.unlink(self.lock_file)
                
                logger.info(f"Файловая блокировка освобождена: {self.lock_file}")
                
        except (OSError, IOError) as e:
            logger.error(f"Ошибка при освобождении блокировки: {e}")
    
    def is_locked(self) -> bool:
        """
        Проверка, заблокирован ли файл другим процессом
        
        Returns:
            bool: True если заблокировано, False если свободно
        """
        try:
            test_fd = os.open(self.lock_file, os.O_RDONLY)
            fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(test_fd, fcntl.LOCK_UN)
            os.close(test_fd)
            return False  # Файл свободен
        except (OSError, IOError):
            return True  # Файл заблокирован
    
    def get_lock_info(self) -> Optional[dict]:
        """
        Получение информации о текущей блокировке
        
        Returns:
            dict: Информация о блокировке или None если не заблокировано
        """
        try:
            if not os.path.exists(self.lock_file):
                return None
            
            with open(self.lock_file, 'r') as f:
                content = f.read().strip()
            
            info = {}
            for line in content.split('\n'):
                if line.startswith('PID:'):
                    info['pid'] = line.split(':', 1)[1].strip()
                elif line.startswith('Time:'):
                    info['time'] = line.split(':', 1)[1].strip()
            
            return info if info else None
            
        except (OSError, IOError) as e:
            logger.error(f"Ошибка чтения информации о блокировке: {e}")
            return None
    
    def __enter__(self):
        """Context manager entry"""
        if not self.acquire():
            logger.critical("Не удалось захватить блокировку инстанса. Завершение работы.")
            sys.exit(1)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
    
    def __del__(self):
        """Деструктор - освобождение блокировки при удалении объекта"""
        self.release()
