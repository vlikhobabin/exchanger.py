#!/usr/bin/env python3
"""
Скрипт для проверки правильности порядка элементов в BPMN файлах
Помогает диагностировать ошибки ENGINE-09005 "Invalid content was found starting with element"
"""
import sys
import os
import xml.etree.ElementTree as ET
from pathlib import Path

def check_bpmn_element_order(file_path):
    """Проверить порядок элементов в BPMN файле"""
    print(f"🔍 Проверка порядка элементов в файле: {file_path}")
    print("=" * 70)
    
    # Проверка существования файла
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        return False
    
    try:
        # Чтение и парсинг файла
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        root = ET.fromstring(content)
        namespaces = {
            'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL'
        }
        
        print(f"📄 Файл загружен, размер: {len(content):,} символов")
        
        # Список элементов для проверки
        elements_to_check = [
            'task', 'serviceTask', 'userTask', 'manualTask', 'businessRuleTask',
            'scriptTask', 'sendTask', 'receiveTask', 'callActivity',
            'startEvent', 'endEvent', 'intermediateCatchEvent', 'intermediateThrowEvent',
            'exclusiveGateway', 'parallelGateway', 'inclusiveGateway', 'eventBasedGateway',
            'complexGateway', 'subProcess'
        ]
        
        total_elements = 0
        problematic_elements = []
        
        # Проверяем каждый тип элементов
        for element_type in elements_to_check:
            elements = root.findall(f'.//bpmn:{element_type}', namespaces)
            total_elements += len(elements)
            
            for element in elements:
                issues = check_single_element_order(element, element_type)
                if issues:
                    problematic_elements.extend(issues)
        
        # Проверяем sequenceFlow элементы
        sequence_flows = root.findall('.//bpmn:sequenceFlow', namespaces)
        total_elements += len(sequence_flows)
        
        for flow in sequence_flows:
            issues = check_sequence_flow_order(flow)
            if issues:
                problematic_elements.extend(issues)
        
        print(f"📊 Всего проверено элементов: {total_elements}")
        print(f"⚠️  Найдено проблемных элементов: {len(problematic_elements)}")
        
        if problematic_elements:
            print("\n🚨 ПРОБЛЕМНЫЕ ЭЛЕМЕНТЫ:")
            print("-" * 50)
            
            for issue in problematic_elements:
                print(f"❌ {issue}")
            
            print("\n💡 РЕКОМЕНДАЦИИ:")
            print("1. Используйте обновленный конвертер BPMN")
            print("2. Или исправьте порядок элементов вручную:")
            print("   - Все <bpmn:incoming> должны идти ДО <bpmn:outgoing>")
            print("   - В sequenceFlow: <conditionExpression> после <extensionElements>")
            
            return False
        else:
            print("\n✅ ВСЕ ЭЛЕМЕНТЫ В ПРАВИЛЬНОМ ПОРЯДКЕ!")
            print("🚀 Файл готов для деплоя в Camunda")
            
            return True
            
    except ET.ParseError as e:
        print(f"❌ Ошибка парсинга XML: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при проверке: {e}")
        return False

def check_single_element_order(element, element_type):
    """Проверить порядок элементов в одном BPMN узле"""
    issues = []
    children = list(element)
    
    if len(children) <= 1:
        return issues
    
    element_id = element.get('id', 'unknown')
    
    # Отслеживаем позицию различных типов элементов
    incoming_positions = []
    outgoing_positions = []
    
    for i, child in enumerate(children):
        tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        
        if tag_name == 'incoming':
            incoming_positions.append(i)
        elif tag_name == 'outgoing':
            outgoing_positions.append(i)
    
    # Проверяем, что все incoming идут ДО всех outgoing
    if incoming_positions and outgoing_positions:
        max_incoming_pos = max(incoming_positions)
        min_outgoing_pos = min(outgoing_positions)
        
        if max_incoming_pos > min_outgoing_pos:
            issues.append(
                f"Элемент {element_type} (ID: {element_id}) - "
                f"<incoming> на позиции {max_incoming_pos} идет после <outgoing> на позиции {min_outgoing_pos}"
            )
    
    # Проверяем группировку incoming элементов
    if len(incoming_positions) > 1:
        for i in range(1, len(incoming_positions)):
            if incoming_positions[i] != incoming_positions[i-1] + 1:
                # Есть разрыв между incoming элементами
                gap_start = incoming_positions[i-1] + 1
                gap_end = incoming_positions[i] - 1
                
                # Проверяем, что между ними
                gap_elements = []
                for pos in range(gap_start, gap_end + 1):
                    gap_tag = children[pos].tag.split('}')[-1] if '}' in children[pos].tag else children[pos].tag
                    gap_elements.append(gap_tag)
                
                if gap_elements:
                    issues.append(
                        f"Элемент {element_type} (ID: {element_id}) - "
                        f"<incoming> элементы разделены элементами: {', '.join(gap_elements)}"
                    )
    
    return issues

def check_sequence_flow_order(flow):
    """Проверить порядок элементов в sequenceFlow"""
    issues = []
    children = list(flow)
    
    if len(children) <= 1:
        return issues
    
    flow_id = flow.get('id', 'unknown')
    
    # Для sequenceFlow правильный порядок: extensionElements -> conditionExpression -> остальное
    extension_pos = None
    condition_pos = None
    
    for i, child in enumerate(children):
        tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        
        if tag_name == 'extensionElements':
            extension_pos = i
        elif tag_name == 'conditionExpression':
            condition_pos = i
    
    if extension_pos is not None and condition_pos is not None:
        if extension_pos > condition_pos:
            issues.append(
                f"SequenceFlow (ID: {flow_id}) - "
                f"<extensionElements> на позиции {extension_pos} идет после <conditionExpression> на позиции {condition_pos}"
            )
    
    return issues

def main():
    """Основная функция"""
    if len(sys.argv) != 2:
        print("🔍 BPMN Element Order Checker")
        print("=" * 40)
        print("Проверка правильности порядка элементов в BPMN файлах")
        print()
        print("📖 Использование:")
        print("   python check_element_order.py <file.bpmn>")
        print()
        print("💡 Примеры:")
        print("   python check_element_order.py ../my_process.bpmn")
        print("   python check_element_order.py camunda_converted.bpmn")
        print()
        print("🎯 Назначение:")
        print("   Диагностика ошибок ENGINE-09005 при деплое в Camunda")
        print("   'Invalid content was found starting with element...'")
        return 1
    
    file_path = sys.argv[1]
    
    success = check_bpmn_element_order(file_path)
    
    if success:
        print("\n🎉 Проверка завершена успешно!")
        return 0
    else:
        print("\n💥 Обнаружены проблемы с порядком элементов!")
        print("🔧 Используйте обновленный конвертер для исправления")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 