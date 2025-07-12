#!/usr/bin/env python3
"""
Утилита для автоматического обновления ID полей в JavaScript коде
на основе конфигурации из config.json
"""

import json
import re
from pathlib import Path

def load_config():
    """Загружает конфигурацию из файла config.json"""
    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Файл конфигурации {config_path} не найден")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка в файле конфигурации: {e}")
        return None

def update_js_config(js_file_path, config):
    """Обновляет конфигурацию в JavaScript файле"""
    if not js_file_path.exists():
        print(f"❌ JavaScript файл {js_file_path} не найден")
        return False
    
    # Читаем текущий JS файл
    with open(js_file_path, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    # Извлекаем ID из конфигурации
    yes_id = config['bitrix_field_config']['UF_RESULT_ANSWER']['values']['yes']
    no_id = config['bitrix_field_config']['UF_RESULT_ANSWER']['values']['no']
    
    # Обновляем строку с присваиванием значения
    pattern = r"data: \{ 'UF_RESULT_ANSWER': answer \? \d+ : \d+ \}"
    replacement = f"data: {{ 'UF_RESULT_ANSWER': answer ? {yes_id} : {no_id} }}"
    
    updated_content = re.sub(pattern, replacement, js_content)
    
    # Обновляем комментарий с ID
    comment_pattern = r"// UF_RESULT_ANSWER - поле типа \"Список\": ID \d+ = \"ДА\", ID \d+ = \"НЕТ\""
    comment_replacement = f"// UF_RESULT_ANSWER - поле типа \"Список\": ID {yes_id} = \"ДА\", ID {no_id} = \"НЕТ\""
    
    updated_content = re.sub(comment_pattern, comment_replacement, updated_content)
    
    # Проверяем, были ли изменения
    if updated_content == js_content:
        print("ℹ️  Конфигурация в JavaScript файле актуальна")
        return True
    
    # Записываем обновленный файл
    with open(js_file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"✅ Конфигурация в {js_file_path.name} обновлена")
    print(f"   ДА: {yes_id}")
    print(f"   НЕТ: {no_id}")
    return True

def main():
    """Основная функция"""
    print("🔧 Обновление конфигурации в JavaScript файле...")
    
    # Загружаем конфигурацию
    config = load_config()
    if not config:
        return 1
    
    # Обновляем JS файл
    js_file_path = Path(__file__).parent / "global_task_modifier.js"
    if update_js_config(js_file_path, config):
        print("🎉 Обновление завершено!")
        return 0
    else:
        print("❌ Ошибка при обновлении")
        return 1

if __name__ == "__main__":
    exit(main()) 