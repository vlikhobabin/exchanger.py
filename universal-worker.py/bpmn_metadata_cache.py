#!/usr/bin/env python3
"""
BPMN Metadata Cache
Кэширование и парсинг метаданных из BPMN XML схем для External Tasks
"""

import time
import threading
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Tuple
from loguru import logger
import requests
from requests.auth import HTTPBasicAuth


class BPMNMetadataCache:
    """
    Кэш для метаданных BPMN процессов с lazy loading
    Поддерживает версионирование и автоматическую очистку
    """
    
    def __init__(self, base_url: str, auth_username: str = None, auth_password: str = None, 
                 max_cache_size: int = 150, ttl_hours: int = 24):
        """
        Инициализация кэша
        
        Args:
            base_url: Базовый URL Camunda REST API
            auth_username: Имя пользователя для аутентификации
            auth_password: Пароль для аутентификации  
            max_cache_size: Максимальный размер кэша (по умолчанию 150 для ~100 процессов)
            ttl_hours: Время жизни записи в кэше в часах
        """
        self.base_url = base_url.rstrip('/')
        self.auth = HTTPBasicAuth(auth_username, auth_password) if auth_username else None
        self.max_cache_size = max_cache_size
        self.ttl_seconds = ttl_hours * 3600
        
        # Структура кэша: process_definition_id -> metadata
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        
        # Статистика
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "xml_requests": 0,
            "parse_operations": 0,
            "cache_evictions": 0
        }
        
        logger.info(f"Инициализирован BPMN Metadata Cache (max_size={max_cache_size}, ttl={ttl_hours}h)")
    
    def get_activity_metadata(self, process_definition_id: str, activity_id: str) -> Dict[str, Any]:
        """
        Получение метаданных для конкретной активности процесса
        
        Args:
            process_definition_id: ID определения процесса
            activity_id: ID активности в процессе
            
        Returns:
            Словарь с метаданными активности
        """
        with self._lock:
            # Проверка кэша
            cache_entry = self._get_from_cache(process_definition_id)
            
            if cache_entry:
                # Данные найдены в кэше
                self.stats["cache_hits"] += 1
                activity_metadata = cache_entry.get("activities", {}).get(activity_id, {})
                
                logger.debug(f"Cache HIT: {process_definition_id}/{activity_id}")
                return activity_metadata
            
            # Данных нет в кэше - загружаем
            self.stats["cache_misses"] += 1
            logger.debug(f"Cache MISS: {process_definition_id}/{activity_id}")
            
            # Загрузка и парсинг BPMN XML
            bpmn_xml = self._fetch_bpmn_xml(process_definition_id)
            if not bpmn_xml:
                return {}
            
            # Парсинг всех активностей процесса
            parsed_metadata = self._parse_bpmn_metadata(bpmn_xml)
            
            # Сохранение в кэш
            self._save_to_cache(process_definition_id, bpmn_xml, parsed_metadata)
            
            # Возврат метаданных конкретной активности
            return parsed_metadata.get(activity_id, {})
    
    def _get_from_cache(self, process_definition_id: str) -> Optional[Dict[str, Any]]:
        """Получение записи из кэша с проверкой TTL"""
        if process_definition_id not in self._cache:
            return None
        
        entry = self._cache[process_definition_id]
        current_time = time.time()
        
        # Проверка TTL
        if current_time - entry["cached_at"] > self.ttl_seconds:
            logger.debug(f"Cache entry expired: {process_definition_id}")
            del self._cache[process_definition_id]
            return None
        
        # Обновление времени последнего доступа для LRU
        entry["last_accessed"] = current_time
        return entry
    
    def _fetch_bpmn_xml(self, process_definition_id: str) -> Optional[str]:
        """Загрузка BPMN XML из Camunda REST API"""
        try:
            url = f"{self.base_url}/process-definition/{process_definition_id}/xml"
            self.stats["xml_requests"] += 1
            
            logger.info(f"Загрузка BPMN XML для процесса: {process_definition_id}")
            
            response = requests.get(url, auth=self.auth, timeout=10)
            response.raise_for_status()
            
            xml_data = response.json()
            bpmn_xml = xml_data.get('bpmn20Xml', '')
            
            if not bpmn_xml:
                logger.warning(f"Пустой BPMN XML для процесса: {process_definition_id}")
                return None
            
            logger.info(f"Успешно загружен BPMN XML для процесса: {process_definition_id} ({len(bpmn_xml)} символов)")
            return bpmn_xml
            
        except Exception as e:
            logger.error(f"Ошибка загрузки BPMN XML для {process_definition_id}: {e}")
            return None
    
    def _parse_bpmn_metadata(self, bpmn_xml: str) -> Dict[str, Dict[str, Any]]:
        """
        Парсинг BPMN XML для извлечения метаданных всех активностей
        
        Returns:
            Словарь: activity_id -> metadata
        """
        try:
            self.stats["parse_operations"] += 1
            root = ET.fromstring(bpmn_xml)
            
            # Namespace mapping
            namespaces = {
                'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
                'camunda': 'http://camunda.org/schema/1.0/bpmn'
            }
            
            activities_metadata = {}
            
            # Поиск всех serviceTask элементов
            service_tasks = root.findall(".//bpmn:serviceTask", namespaces)
            
            for task in service_tasks:
                activity_id = task.get('id')
                if not activity_id:
                    continue
                
                activity_metadata = {}
                
                # Extension Properties
                properties = task.findall(".//camunda:property", namespaces)
                if properties:
                    activity_metadata['extensionProperties'] = {}
                    for prop in properties:
                        name = prop.get('name')
                        value = prop.get('value')
                        if name and value:
                            activity_metadata['extensionProperties'][name] = value
                
                # Field Injections
                fields = task.findall(".//camunda:field", namespaces)
                if fields:
                    activity_metadata['fieldInjections'] = {}
                    for field in fields:
                        name = field.get('name')
                        # Проверяем атрибут stringValue
                        value = field.get('stringValue')
                        if not value:
                            # Ищем child element camunda:string
                            string_elem = field.find('camunda:string', namespaces)
                            if string_elem is not None and string_elem.text:
                                value = string_elem.text
                        
                        if name and value:
                            activity_metadata['fieldInjections'][name] = value
                
                # Input/Output Parameters
                input_output = task.find(".//camunda:inputOutput", namespaces)
                if input_output is not None:
                    # Input Parameters
                    input_params = input_output.findall("camunda:inputParameter", namespaces)
                    if input_params:
                        activity_metadata['inputParameters'] = {}
                        for param in input_params:
                            name = param.get('name')
                            value = param.text
                            if name and value:
                                activity_metadata['inputParameters'][name] = value
                    
                    # Output Parameters
                    output_params = input_output.findall("camunda:outputParameter", namespaces)
                    if output_params:
                        activity_metadata['outputParameters'] = {}
                        for param in output_params:
                            name = param.get('name')
                            value = param.text
                            if name and value:
                                activity_metadata['outputParameters'][name] = value
                
                # Основные атрибуты активности
                activity_metadata['activityInfo'] = {
                    'id': activity_id,
                    'name': task.get('name', ''),
                    'type': task.get('{http://camunda.org/schema/1.0/bpmn}type', ''),
                    'topic': task.get('{http://camunda.org/schema/1.0/bpmn}topic', '')
                }
                
                activities_metadata[activity_id] = activity_metadata
                
            logger.info(f"Извлечены метаданные для {len(activities_metadata)} активностей")
            return activities_metadata
            
        except Exception as e:
            logger.error(f"Ошибка парсинга BPMN XML: {e}")
            return {}
    
    def _save_to_cache(self, process_definition_id: str, bpmn_xml: str, activities_metadata: Dict[str, Dict[str, Any]]):
        """Сохранение данных в кэш с управлением размером"""
        current_time = time.time()
        
        # Проверка размера кэша и очистка если необходимо
        if len(self._cache) >= self.max_cache_size:
            self._cleanup_cache()
        
        # Сохранение новой записи
        self._cache[process_definition_id] = {
            "bpmn_xml": bpmn_xml,
            "activities": activities_metadata,
            "cached_at": current_time,
            "last_accessed": current_time,
            "size_bytes": len(bpmn_xml)
        }
        
        logger.info(f"Сохранен в кэш: {process_definition_id} ({len(activities_metadata)} активностей)")
    
    def _cleanup_cache(self):
        """Очистка кэша по LRU стратегии"""
        if not self._cache:
            return
        
        # Сортировка по времени последнего доступа (LRU)
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1]["last_accessed"]
        )
        
        # Удаление 25% самых старых записей
        entries_to_remove = max(1, len(sorted_entries) // 4)
        
        for i in range(entries_to_remove):
            process_id, _ = sorted_entries[i]
            del self._cache[process_id]
            self.stats["cache_evictions"] += 1
            logger.debug(f"Удален из кэша (LRU): {process_id}")
        
        logger.info(f"Очистка кэша: удалено {entries_to_remove} записей")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша"""
        with self._lock:
            cache_size = len(self._cache)
            total_size_mb = sum(entry.get("size_bytes", 0) for entry in self._cache.values()) / (1024 * 1024)
            
            hit_rate = 0
            total_requests = self.stats["cache_hits"] + self.stats["cache_misses"]
            if total_requests > 0:
                hit_rate = (self.stats["cache_hits"] / total_requests) * 100
            
            return {
                **self.stats,
                "cache_size": cache_size,
                "max_cache_size": self.max_cache_size,
                "cache_size_mb": round(total_size_mb, 2),
                "hit_rate_percent": round(hit_rate, 2),
                "total_requests": total_requests
            }
    
    def clear_cache(self):
        """Очистка всего кэша"""
        with self._lock:
            cleared_count = len(self._cache)
            self._cache.clear()
            logger.info(f"Кэш полностью очищен: удалено {cleared_count} записей")
    
    def remove_from_cache(self, process_definition_id: str) -> bool:
        """Удаление конкретной записи из кэша"""
        with self._lock:
            if process_definition_id in self._cache:
                del self._cache[process_definition_id]
                logger.info(f"Удален из кэша: {process_definition_id}")
                return True
            return False 