#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для конвертации BPMN схем из StormBPMN в Camunda формат
Использование: python convert.py <input_file.bpmn>
"""

import sys
import os
import json
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from bpmn_converter import BPMNConverter


def main():
    """Основная функция скрипта"""
    print("🔄 BPMN Converter - StormBPMN → Camunda")
    print("=" * 50)
    
    if len(sys.argv) != 2:
        print("❌ Неверное количество аргументов!")
        print("\n📖 Использование:")
        print("   python convert.py <input_file.bpmn>")
        print("\n💡 Примеры:")
        print("   python convert.py ../my_process.bpmn")
        print("   python convert.py process_diagram.bpmn")
        print("\n📝 Описание:")
        print("   Скрипт конвертирует BPMN схему из формата StormBPMN в формат Camunda.")
        print("   Результат сохраняется в той же папке с префиксом 'camunda_'.")
        return 1
        
    input_file = sys.argv[1]
    
    # Проверяем существование файла
    if not os.path.exists(input_file):
        print(f"❌ Файл не найден: {input_file}")
        return 1
        
    # Проверяем расширение файла
    if not input_file.lower().endswith('.bpmn'):
        print(f"⚠️ Предупреждение: файл не имеет расширения .bpmn")
        print(f"   Продолжаем обработку...")
    
    try:
        # Ищем JSON файл с ответственными
        assignees_data = None
        input_path = Path(input_file)
        
        # Формируем имя JSON файла: берем имя BPMN файла и добавляем суффикс _assignees.json
        base_name = input_path.stem  # имя без расширения
        assignees_json_path = input_path.parent / f"{base_name}_assignees.json"
        
        if assignees_json_path.exists():
            try:
                print(f"📋 Найден файл с ответственными: {assignees_json_path}")
                with open(assignees_json_path, 'r', encoding='utf-8') as f:
                    assignees_data = json.load(f)
                print(f"   ✅ Загружено {len(assignees_data)} ответственных")
            except Exception as e:
                print(f"   ⚠️ Ошибка при загрузке ответственных: {e}")
                print(f"   Продолжаем конвертацию без ответственных...")
        else:
            print(f"📋 Файл с ответственными не найден: {assignees_json_path}")
            print(f"   Продолжаем конвертацию без ответственных...")
        
        # Запускаем конвертацию
        converter = BPMNConverter()
        output_file = converter.convert_file(input_file, assignees_data)
        
        print(f"\n🎉 Конвертация завершена успешно!")
        print(f"📁 Исходный файл: {input_file}")
        print(f"📁 Результат: {output_file}")
        
        # Показываем размеры файлов
        input_size = os.path.getsize(input_file)
        output_size = os.path.getsize(output_file)
        print(f"📊 Размер исходного файла: {input_size:,} байт")
        print(f"📊 Размер результата: {output_size:,} байт")
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка при конвертации: {e}")
        print(f"🔍 Тип ошибки: {type(e).__name__}")
        
        # Дополнительная информация для отладки
        if hasattr(e, '__traceback__'):
            import traceback
            print(f"📍 Детали ошибки:")
            traceback.print_exc()
            
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 