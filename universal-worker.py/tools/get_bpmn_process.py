#!/usr/bin/env python3
"""
Утилита для загрузки BPMN процесса из Camunda и анализа условных выражений
"""

import sys
import os
import json
import requests
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config

def get_process_bpmn(process_key: str = "TestProcess"):
    """Загрузка BPMN процесса из Camunda"""
    print(f"📥 Загрузка BPMN процесса '{process_key}' из Camunda")
    print("=" * 60)
    
    try:
        # Формируем базовый URL
        base_url = camunda_config.base_url.rstrip('/')
        if base_url.endswith('/engine-rest'):
            api_base_url = base_url
        else:
            api_base_url = f"{base_url}/engine-rest"
        
        # Настраиваем аутентификацию
        auth = None
        if camunda_config.auth_enabled:
            auth = (camunda_config.auth_username, camunda_config.auth_password)
            print(f"🔐 Аутентификация: {camunda_config.auth_username}")
        else:
            print("🔐 Аутентификация: не используется")
        
        print(f"🌐 Camunda URL: {api_base_url}")
        print()
        
        # 1. Получаем список определений процессов
        print("1️⃣ Поиск определения процесса...")
        url = f"{api_base_url}/process-definition"
        params = {"key": process_key, "latestVersion": "true"}
        
        response = requests.get(url, auth=auth, timeout=10, params=params)
        print(f"   Статус ответа: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Ошибка: {response.text}")
            return False
        
        definitions = response.json()
        if not definitions:
            print(f"   ❌ Процесс '{process_key}' не найден")
            return False
        
        definition = definitions[0]
        process_definition_id = definition['id']
        print(f"   ✅ Найдено определение процесса: {process_definition_id}")
        print(f"   📝 Версия: {definition.get('version', 'N/A')}")
        print(f"   📝 Ключ: {definition.get('key', 'N/A')}")
        print(f"   📝 Название: {definition.get('name', 'N/A')}")
        print()
        
        # 2. Загружаем BPMN XML
        print("2️⃣ Загрузка BPMN XML...")
        url = f"{api_base_url}/process-definition/{process_definition_id}/xml"
        
        response = requests.get(url, auth=auth, timeout=10)
        print(f"   Статус ответа: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Ошибка: {response.text}")
            return False
        
        xml_data = response.json()
        bpmn_xml = xml_data.get('bpmn20Xml', '')
        
        if not bpmn_xml:
            print("   ❌ BPMN XML не найден в ответе")
            return False
        
        print(f"   ✅ BPMN XML загружен ({len(bpmn_xml)} символов)")
        print()
        
        # 3. Анализируем BPMN XML
        print("3️⃣ Анализ условных выражений...")
        analyze_bpmn_xml(bpmn_xml)
        
        # 4. Сохраняем BPMN в файл для анализа
        filename = f"tools/{process_key}_current.xml"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(bpmn_xml)
        print(f"💾 BPMN XML сохранен в: {filename}")
        
        return True
        
    except Exception as e:
        print(f"💥 Ошибка: {e}")
        return False

def analyze_bpmn_xml(bpmn_xml: str):
    """Анализ BPMN XML для поиска условных выражений"""
    try:
        # Определяем namespaces
        namespaces = {
            'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
            'camunda': 'http://camunda.org/schema/1.0/bpmn'
        }
        
        root = ET.fromstring(bpmn_xml)
        
        # Ищем все Gateways
        gateways = root.findall('.//bpmn:exclusiveGateway', namespaces) + \
                  root.findall('.//bpmn:inclusiveGateway', namespaces) + \
                  root.findall('.//bpmn:parallelGateway', namespaces)
        
        print(f"   📊 Найдено Gateway элементов: {len(gateways)}")
        
        for i, gateway in enumerate(gateways):
            gateway_id = gateway.get('id', 'unknown')
            gateway_name = gateway.get('name', 'Без названия')
            gateway_type = gateway.tag.split('}')[-1] if '}' in gateway.tag else gateway.tag
            
            print(f"\n   🔍 Gateway #{i+1}:")
            print(f"      ID: {gateway_id}")
            print(f"      Название: {gateway_name}")
            print(f"      Тип: {gateway_type}")
            
            # Ищем исходящие потоки из этого Gateway
            outgoing = gateway.findall('.//bpmn:outgoing', namespaces)
            print(f"      Исходящих потоков: {len(outgoing)}")
            
            # Ищем последовательные потоки с условными выражениями
            sequence_flows = root.findall('.//bpmn:sequenceFlow', namespaces)
            gateway_flows = []
            
            for flow in sequence_flows:
                if flow.get('sourceRef') == gateway_id:
                    gateway_flows.append(flow)
            
            print(f"      Потоков от этого Gateway: {len(gateway_flows)}")
            
            for j, flow in enumerate(gateway_flows):
                flow_id = flow.get('id', 'unknown')
                flow_name = flow.get('name', 'Без названия')
                target_ref = flow.get('targetRef', 'unknown')
                
                print(f"         Поток #{j+1}: {flow_id} -> {target_ref}")
                print(f"         Название: {flow_name}")
                
                # Ищем условное выражение
                condition = flow.find('bpmn:conditionExpression', namespaces)
                if condition is not None:
                    condition_text = condition.text or ''
                    condition_type = condition.get('{http://www.w3.org/2001/XMLSchema-instance}type', 'unknown')
                    
                    print(f"         🎯 Условное выражение:")
                    print(f"            Тип: {condition_type}")
                    print(f"            Выражение: '{condition_text.strip()}'")
                    
                    if condition_text.strip():
                        print(f"         ⚠️  ВНИМАНИЕ: Найдено условное выражение!")
                        analyze_condition_expression(condition_text.strip())
                else:
                    print(f"         ✅ Условное выражение: отсутствует (default path)")
        
        # Также ищем переменные в процессе
        print(f"\n   📋 Анализ переменных в процессе:")
        
        # Ищем формы
        forms = root.findall('.//camunda:formData', namespaces)
        if forms:
            print(f"      Найдено форм: {len(forms)}")
            for form in forms:
                fields = form.findall('.//camunda:formField', namespaces)
                for field in fields:
                    field_id = field.get('id', 'unknown')
                    field_type = field.get('type', 'unknown')
                    print(f"         Поле формы: {field_id} ({field_type})")
        
        # Ищем input/output параметры
        ios = root.findall('.//camunda:inputOutput', namespaces)
        if ios:
            print(f"      Найдено input/output блоков: {len(ios)}")
            for io in ios:
                inputs = io.findall('.//camunda:inputParameter', namespaces)
                outputs = io.findall('.//camunda:outputParameter', namespaces)
                for inp in inputs:
                    inp_name = inp.get('name', 'unknown')
                    print(f"         Input параметр: {inp_name}")
                for out in outputs:
                    out_name = out.get('name', 'unknown')
                    print(f"         Output параметр: {out_name}")
        
    except Exception as e:
        print(f"   ❌ Ошибка анализа XML: {e}")

def analyze_condition_expression(expression: str):
    """Анализ условного выражения для поиска переменных"""
    print(f"         🔍 Анализ выражения: '{expression}'")
    
    # Простой анализ для поиска переменных
    common_vars = ['result', 'success', 'completed', 'status', 'outcome', 'approved', 'valid']
    
    for var in common_vars:
        if var in expression.lower():
            print(f"         📝 Возможная переменная: {var}")
    
    # Анализ операторов
    if '==' in expression:
        print(f"         🔧 Найден оператор равенства ==")
    if '!=' in expression:
        print(f"         🔧 Найден оператор неравенства !=")
    if 'true' in expression.lower():
        print(f"         ✅ Ожидается Boolean: true")
    if 'false' in expression.lower():
        print(f"         ❌ Ожидается Boolean: false")

def main():
    """Главная функция"""
    process_key = "TestProcess"
    if len(sys.argv) > 1:
        process_key = sys.argv[1].strip()
    
    print(f"🔍 Анализ BPMN процесса: {process_key}")
    get_process_bpmn(process_key)

if __name__ == "__main__":
    main() 