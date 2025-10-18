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
        self.api_url = f"{self.config.webhook_url}/user.userfield.list.json"
        
        logger.debug(f"BitrixUserFieldSync инициализирован, кеш-файл: {self.cache_file}")
    
    def fetch_uf_result_answer_values(self) -> Optional[Dict[str, Any]]:
        """
        Запрос к API Bitrix24 для получения значений поля UF_RESULT_ANSWER.
        
        Returns:
            Dict с данными поля или None при ошибке
        """
        try:
            # Параметры запроса для получения пользовательского поля
            params = {
                'filter': {
                    'ENTITY_ID': 'TASKS_TASK',
                    'FIELD_NAME': 'UF_RESULT_ANSWER'
                }
            }
            
            logger.debug(f"Запрос к API Bitrix24: {self.api_url}")
            logger.debug(f"Параметры: {params}")
            
            # Выполняем запрос к API
            response = requests.post(
                self.api_url,
                json=params,
                headers={'Content-Type': 'application/json'},
                timeout=self.config.request_timeout
            )
            
            # Проверяем статус ответа
            response.raise_for_status()
            result = response.json()
            
            # Проверяем наличие ошибок в ответе
            if result.get('error'):
                logger.error(f"Ошибка API Bitrix24: {result['error']}")
                logger.error(f"Описание ошибки: {result.get('error_description', 'Не указано')}")
                return None
            
            # Проверяем наличие данных
            api_result = result.get('result', [])
            if not api_result:
                logger.warning("Поле UF_RESULT_ANSWER не найдено в Bitrix24")
                return None
            
            logger.info(f"Успешно получены данные поля UF_RESULT_ANSWER из API")
            return api_result[0]  # Возвращаем первое (и единственное) поле
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к API Bitrix24: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования ответа от API Bitrix24: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к API Bitrix24: {e}")
            return None
    
    def parse_list_values(self, field_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Извлечение значений списка из данных поля.
        
        Args:
            field_data: Данные поля из API Bitrix24
            
        Returns:
            Список значений или None при ошибке
        """
        try:
            # Извлекаем список значений из поля
            list_values = field_data.get('LIST', [])
            
            if not list_values:
                logger.warning("Список значений поля UF_RESULT_ANSWER пуст")
                return None
            
            logger.debug(f"Найдено {len(list_values)} значений в списке поля UF_RESULT_ANSWER")
            
            # Логируем найденные значения для отладки
            for item in list_values:
                item_id = item.get('ID', 'unknown')
                item_value = item.get('VALUE', 'unknown')
                logger.debug(f"Значение списка: ID={item_id}, VALUE={item_value}")
            
            return list_values
            
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
            
            # Проверяем наличие ожидаемых значений
            values = list(mapping.values())
            if "ДА" not in values and "НЕТ" not in values:
                logger.warning(f"Не найдены ожидаемые значения 'ДА'/'НЕТ' в списке: {values}")
            
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
    
    def sync_mapping(self) -> Optional[Dict[str, str]]:
        """
        Основной метод синхронизации маппинга.
        
        Логика работы:
        1. Попытка получить данные из API Bitrix24
        2. При успехе: сохранить в кеш и вернуть маппинг
        3. При ошибке: загрузить из кеш-файла
        4. Если кеш отсутствует: вернуть None
        
        Returns:
            Словарь маппинга или None при ошибке
        """
        logger.info("Начало синхронизации маппинга UF_RESULT_ANSWER")
        
        # Шаг 1: Попытка получить данные из API
        try:
            field_data = self.fetch_uf_result_answer_values()
            if field_data:
                list_values = self.parse_list_values(field_data)
                if list_values:
                    mapping = self.build_mapping(list_values)
                    if mapping:
                        # Сохраняем в кеш
                        if self.save_to_cache_file(mapping):
                            logger.info("✅ Маппинг успешно получен из API и сохранен в кеш")
                            return mapping
                        else:
                            logger.warning("⚠️ Маппинг получен из API, но не удалось сохранить в кеш")
                            return mapping
        except Exception as e:
            logger.error(f"Ошибка при получении данных из API: {e}")
        
        # Шаг 2: При ошибке API - загружаем из кеша
        logger.warning("API недоступен, попытка загрузки из кеш-файла")
        try:
            cached_mapping = self.load_from_cache_file()
            if cached_mapping:
                logger.info("✅ Маппинг загружен из кеш-файла")
                return cached_mapping
        except Exception as e:
            logger.error(f"Ошибка при загрузке из кеш-файла: {e}")
        
        # Шаг 3: Если кеш недоступен - возвращаем None
        logger.error("❌ Не удалось получить маппинг ни из API, ни из кеш-файла")
        return None
