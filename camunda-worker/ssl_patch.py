#!/usr/bin/env python3
"""
SSL Patch для camunda-external-task-client-python3
Monkey patching библиотеки для решения SSL проблем
"""
import requests
import urllib3
from loguru import logger
from functools import wraps

# Отключение SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Флаг для отслеживания применения патча
_patch_applied = False


def _add_verify_false(kwargs):
    """Добавить verify=False к параметрам запроса если не указано"""
    if 'verify' not in kwargs:
        kwargs['verify'] = False
    return kwargs


def _patch_requests_method(original_method):
    """Декоратор для monkey patching методов requests"""
    @wraps(original_method)
    def wrapper(*args, **kwargs):
        # Добавляем verify=False если не указано
        kwargs = _add_verify_false(kwargs)
        return original_method(*args, **kwargs)
    return wrapper


def _patch_session_method(original_method):
    """Декоратор для monkey patching методов requests.Session"""
    @wraps(original_method)
    def wrapper(self, *args, **kwargs):
        # Добавляем verify=False если не указано
        kwargs = _add_verify_false(kwargs)
        return original_method(self, *args, **kwargs)
    return wrapper


def apply_ssl_patch():
    """
    Применить SSL патч к библиотеке requests
    
    Monkey patches:
    - requests.post
    - requests.get  
    - requests.put
    - requests.delete
    - requests.patch
    - requests.Session.request
    """
    global _patch_applied
    
    if _patch_applied:
        logger.debug("SSL патч уже применен")
        return
    
    try:
        # Патчинг основных HTTP методов requests
        requests.post = _patch_requests_method(requests.post)
        requests.get = _patch_requests_method(requests.get)
        requests.put = _patch_requests_method(requests.put)
        requests.delete = _patch_requests_method(requests.delete)
        requests.patch = _patch_requests_method(requests.patch)
        
        # Патчинг Session.request для всех запросов через сессию
        requests.Session.request = _patch_session_method(requests.Session.request)
        
        _patch_applied = True
        logger.info("✅ SSL патч успешно применен к библиотеке requests")
        logger.info("   - Все HTTP запросы теперь используют verify=False")
        logger.info("   - SSL warnings отключены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при применении SSL патча: {e}")
        raise


def is_patch_applied():
    """Проверить, применен ли SSL патч"""
    return _patch_applied


def get_patch_info():
    """Получить информацию о примененном патче"""
    return {
        "applied": _patch_applied,
        "description": "SSL patch for camunda-external-task-client-python3",
        "changes": [
            "requests.post -> verify=False",
            "requests.get -> verify=False", 
            "requests.put -> verify=False",
            "requests.delete -> verify=False",
            "requests.patch -> verify=False",
            "requests.Session.request -> verify=False"
        ],
        "warnings_disabled": True
    }


# Автоматическое применение патча при импорте модуля
if __name__ != "__main__":
    apply_ssl_patch()
