#!/usr/bin/env python3
"""
Скрипт для валидации BPMN файла перед деплоем в Camunda
"""
import sys
import os
import xml.etree.ElementTree as ET
from pathlib import Path

def validate_bpmn_file(file_path):
    """Валидация BPMN файла"""
    print(f"🔍 Валидация файла: {file_path}")
    print("=" * 50)
    
    # Проверка существования файла
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        return False
    
    file_size = os.path.getsize(file_path)
    print(f"📁 Размер файла: {file_size:,} байт")
    
    try:
        # Чтение файла как текст
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"📄 Содержимое файла: {len(content):,} символов")
        
        # Проверка XML декларации
        if content.strip().startswith('<?xml'):
            print("✅ XML декларация найдена")
        else:
            print("⚠️  XML декларация отсутствует")
        
        # Проверка BPMN namespace
        if 'bpmn:definitions' in content:
            print("✅ BPMN definitions найден")
        else:
            print("❌ BPMN definitions НЕ найден")
            return False
        
        # Проверка Camunda namespace
        if 'xmlns:camunda' in content:
            print("✅ Camunda namespace найден")
        else:
            print("⚠️  Camunda namespace отсутствует")
        
        # Парсинг XML
        try:
            root = ET.fromstring(content)
            print("✅ XML структура корректна")
            
            # Проверка пространств имен
            namespaces = {
                'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
                'camunda': 'http://camunda.org/schema/1.0/bpmn'
            }
            
            # Поиск процессов
            processes = root.findall('.//bpmn:process', namespaces)
            print(f"📋 Найдено процессов: {len(processes)}")
            
            for i, process in enumerate(processes, 1):
                process_id = process.get('id', 'N/A')
                process_name = process.get('name', 'Без названия')
                is_executable = process.get('isExecutable', 'false')
                
                print(f"   {i}. {process_name}")
                print(f"      ID: {process_id}")
                print(f"      Исполняемый: {is_executable}")
                
                # Подсчет элементов в процессе
                tasks = process.findall('.//bpmn:serviceTask', namespaces) + \
                        process.findall('.//bpmn:userTask', namespaces) + \
                        process.findall('.//bpmn:task', namespaces)
                
                gateways = process.findall('.//bpmn:exclusiveGateway', namespaces) + \
                          process.findall('.//bpmn:parallelGateway', namespaces) + \
                          process.findall('.//bpmn:inclusiveGateway', namespaces)
                
                events = process.findall('.//bpmn:startEvent', namespaces) + \
                        process.findall('.//bpmn:endEvent', namespaces) + \
                        process.findall('.//bpmn:intermediateCatchEvent', namespaces) + \
                        process.findall('.//bpmn:intermediateThrowEvent', namespaces)
                
                flows = process.findall('.//bpmn:sequenceFlow', namespaces)
                
                print(f"      Задачи: {len(tasks)}")
                print(f"      Шлюзы: {len(gateways)}")
                print(f"      События: {len(events)}")
                print(f"      Потоки: {len(flows)}")
                print()
            
            # Проверка диаграммы
            diagrams = root.findall('.//bpmndi:BPMNDiagram', {
                'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI'
            })
            print(f"🎨 Диаграмм: {len(diagrams)}")
            
            return True
            
        except ET.ParseError as e:
            print(f"❌ Ошибка парсинга XML: {e}")
            print(f"   Строка: {e.lineno if hasattr(e, 'lineno') else 'N/A'}")
            print(f"   Позиция: {e.offset if hasattr(e, 'offset') else 'N/A'}")
            return False
        
    except UnicodeDecodeError as e:
        print(f"❌ Ошибка кодировки: {e}")
        print("   Попробуйте сохранить файл в UTF-8")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def main():
    """Основная функция"""
    if len(sys.argv) != 2:
        print("Использование: python validate_bpmn.py <file.bpmn>")
        return 1
    
    file_path = sys.argv[1]
    
    if validate_bpmn_file(file_path):
        print("✅ Файл прошел валидацию!")
        print("🚀 Можно попробовать деплой в Camunda")
        return 0
    else:
        print("❌ Файл НЕ прошел валидацию!")
        print("🔧 Исправьте ошибки перед деплоем")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 