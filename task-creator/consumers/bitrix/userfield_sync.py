#!/usr/bin/env python3
"""
Модуль для синхронизации пользовательских полей Bitrix24
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests
from loguru import logger


class BitrixUserFieldSync:
    """
    Класс для синхронизации пользовательских полей из Bitrix24 API.
    
    Основная функциональность:
    - Получение значений пользовательских полей через API Bitrix24
    - Кеширование полученных данных в файл
    - Fallback на кешированные значения при ошибках API
    """
    
    def __init__(self, config):
        """
        Инициализация синхронизатора пользовательских полей.
        
        Args:
            config: Конфигурация Bitrix24 с webhook_url и другими настройками
        """
        self.config = config
        self.cache_file = Path(__file__).parent / '.uf_result_answer_cache.json'
        
        # Используем стандартный webhook Bitrix24
        self.webhook_url = self.config.webhook_url
        
        logger.debug(f"BitrixUserFieldSync инициализирован, кеш-файл: {self.cache_file}")
        logger.debug(f"Webhook URL: {self.webhook_url}")
    
    def fetch_uf_result_answer_values(self) -> Optional[Dict[str, Any]]:
        """
        Запрос к стандартному webhook Bitrix24 для получения значений поля UF_RESULT_ANSWER.
        
        Returns:
            Dict с данными поля или None при ошибке
        """
        try:
            logger.debug(f"Попытка запроса к webhook Bitrix24: {self.webhook_url}")
            
            # Используем метод imena.camunda.userfield.list
            url = f"{self.webhook_url}/imena.camunda.userfield.list"
            response = requests.get(url, timeout=self.config.request_timeout)
            
            # Проверяем статус ответа
            response.raise_for_status()
            result = response.json()
            
            # Проверяем наличие ошибок в ответе
            if 'error' in result:
                logger.debug(f"API вернул ошибку: {result.get('error', 'Unknown error')}")
                return None
            
            # Проверяем наличие данных в API
            api_data = result.get('result', {})
            user_fields = api_data.get('userFields', [])
            
            # Ищем поле UF_RESULT_ANSWER
            for field in user_fields:
                if field.get('FIELD_NAME') == 'UF_RESULT_ANSWER':
                    logger.info(f"✅ Найдено поле UF_RESULT_ANSWER в webhook API")
                    return field
            
            logger.debug("Поле UF_RESULT_ANSWER не найдено в webhook API")
            return None
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"Ошибка запроса к webhook API: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.debug(f"Ошибка декодирования ответа от webhook API: {e}")
            return None
        except Exception as e:
            logger.debug(f"Неожиданная ошибка при запросе к webhook API: {e}")
            return None
    
    def parse_list_values(self, field_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Извлечение значений списка из данных поля webhook API.
        
        Args:
            field_data: Данные поля из webhook API Bitrix24
            
        Returns:
            Список значений или None при ошибке
        """
        try:
            # Получаем enum значения из webhook API
            enum_values = field_data.get('ENUM_VALUES', [])
            if enum_values:
                logger.debug(f"Найдено {len(enum_values)} enum значений в webhook API")
                
                for item in enum_values:
                    item_id = item.get('ID', 'unknown')
                    item_value = item.get('VALUE', 'unknown')
                    logger.debug(f"Enum значение: ID={item_id}, VALUE={item_value}")
                
                return enum_values
            
            logger.warning("Список значений поля UF_RESULT_ANSWER пуст")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге значений списка: {e}")
            return None
    
    def build_mapping(self, list_values: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """
        Создание маппинга ID -> текст для значений "ДА" и "НЕТ".
        
        Args:
            list_values: Список значений из API
            
        Returns:
            Словарь маппинга или None при ошибке
        """
        try:
            mapping = {}
            
            for item in list_values:
                item_id = str(item.get('ID', ''))
                item_value = item.get('VALUE', '').strip()
                
                if not item_id or not item_value:
                    logger.warning(f"Пропущено некорректное значение: ID={item_id}, VALUE={item_value}")
                    continue
                
                mapping[item_id] = item_value
                logger.debug(f"Добавлено в маппинг: {item_id} -> {item_value}")
            
            if not mapping:
                logger.error("Не удалось создать маппинг - нет корректных значений")
                return None
            
            
            logger.info(f"Создан маппинг для {len(mapping)} значений: {mapping}")
            return mapping
            
        except Exception as e:
            logger.error(f"Ошибка при создании маппинга: {e}")
            return None
    
    def save_to_cache_file(self, mapping: Dict[str, str]) -> bool:
        """
        Сохранение маппинга в кеш-файл.
        
        Args:
            mapping: Словарь маппинга для сохранения
            
        Returns:
            True если сохранение успешно, False иначе
        """
        try:
            cache_data = {
                "last_updated": datetime.now().isoformat(),
                "mapping": mapping
            }
            
            # Создаем директорию если не существует
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем в файл
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Маппинг сохранен в кеш-файл: {self.cache_file}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении в кеш-файл: {e}")
            return False
    
    def load_from_cache_file(self) -> Optional[Dict[str, str]]:
        """
        Загрузка маппинга из кеш-файла.
        
        Returns:
            Словарь маппинга или None при ошибке
        """
        try:
            if not self.cache_file.exists():
                logger.debug("Кеш-файл не существует")
                return None
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            mapping = cache_data.get('mapping', {})
            last_updated = cache_data.get('last_updated', 'unknown')
            
            if not mapping:
                logger.warning("Кеш-файл пуст или не содержит маппинг")
                return None
            
            logger.info(f"Загружен маппинг из кеш-файла (обновлен: {last_updated}): {mapping}")
            return mapping
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга кеш-файла: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при загрузке из кеш-файла: {e}")
            return None
    
    def sync_mapping(self) -> bool:
        """
        Синхронизация маппинга через webhook API и обновление кеша.
        
        Логика:
        1. Получает данные из webhook API Bitrix24
        2. При успехе: сохраняет в кеш и возвращает True
        3. При ошибке: инвалидирует кеш (очищает файл) и возвращает False
        
        Returns:
            bool: True если синхронизация успешна, False при ошибке
        """
        logger.info("Начало синхронизации маппинга UF_RESULT_ANSWER")
        
        try:
            field_data = self.fetch_uf_result_answer_values()
            if field_data:
                list_values = self.parse_list_values(field_data)
                if list_values:
                    mapping = self.build_mapping(list_values)
                    if mapping:
                        # Сохраняем в кеш
                        if self.save_to_cache_file(mapping):
                            logger.info("✅ Маппинг успешно получен из webhook API и сохранен в кеш")
                            return True
                        else:
                            logger.warning("⚠️ Маппинг получен из webhook API, но не удалось сохранить в кеш")
                            return False
            
            logger.error("❌ Не удалось получить данные из webhook API")
            self.invalidate_cache()
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных из webhook API: {e}")
            self.invalidate_cache()
            return False
    def invalidate_cache(self) -> None:
        """Инвалидирует кеш, удаляя кеш-файл."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                logger.info(f"Кеш-файл инвалидирован: {self.cache_file}")
        except Exception as e:
            logger.error(f"Ошибка при инвалидации кеш-файла: {e}")
    
    def get_mapping(self) -> Dict[str, str]:
        """
        Получает маппинг из кеша.
        
        Returns:
            Dict[str, str]: Словарь маппинга или пустой словарь если кеш невалиден
        """
        cached_mapping = self.load_from_cache_file()
        return cached_mapping if cached_mapping else {}
