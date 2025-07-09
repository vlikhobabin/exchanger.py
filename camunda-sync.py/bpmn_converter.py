#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BPMN Converter - конвертация схем из StormBPMN в Camunda формат
Автор: AI Assistant
Дата: 2024
"""

import sys
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Set, Optional
import uuid
import re
from pathlib import Path


class BPMNConverter:
    """Класс для конвертации BPMN схем из StormBPMN в Camunda формат"""
    
    def __init__(self):
        self.namespaces = {
            'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
            'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
            'di': 'http://www.omg.org/spec/DD/20100524/DI',
            'dc': 'http://www.omg.org/spec/DD/20100524/DC',
            'camunda': 'http://camunda.org/schema/1.0/bpmn',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        
        # Регистрируем пространства имен для ElementTree
        for prefix, uri in self.namespaces.items():
            ET.register_namespace(prefix, uri)
        
        # Элементы для удаления
        self.elements_to_remove = {
            'intermediateCatchEvent',
            'intermediateThrowEvent', 
            'messageEventDefinition',
            'timerEventDefinition'
        }
        
        # Типы задач для преобразования в serviceTask
        self.task_types_to_convert = {
            'userTask', 'manualTask', 'callActivity', 'task'
        }
        
        # Отслеживание удаленных элементов
        self.removed_elements: Set[str] = set()
        self.removed_flows: Set[str] = set()
        
    def convert_file(self, input_file: str, assignees_data: Optional[List[Dict]] = None) -> str:
        """Конвертировать BPMN файл"""
        print(f"🔄 Загрузка файла: {input_file}")
        
        # Сохраняем данные об ответственных
        self.assignees_data = assignees_data or []
        if self.assignees_data:
            print(f"📋 Загружено {len(self.assignees_data)} ответственных для встраивания")
        
        # Проверяем существование файла
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Файл не найден: {input_file}")
        
        # Создаем путь для результата
        input_path = Path(input_file)
        output_file = str(input_path.parent / f"camunda_{input_path.name}")
        
        # Загружаем и парсим XML
        try:
            tree = ET.parse(input_file)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Ошибка парсинга XML: {e}")
        
        print("✅ Файл загружен успешно")
        
        # Применяем трансформации
        self._add_camunda_namespaces(root)
        self._update_process_attributes(root)
        self._remove_collaboration_section(root)
        self._remove_intermediate_events(root)
        self._convert_tasks_to_service_tasks(root)
        self._add_assignee_properties(root)
        self._add_condition_expressions(root)
        self._fix_element_order(root)
        self._fix_default_flows(root)
        self._clean_diagram_elements(root)
        self._update_bpmn_plane(root)
        
        # Сохраняем результат
        self._save_result(tree, output_file)
        
        print(f"✅ Конвертация завершена")
        print(f"📁 Результат сохранен: {output_file}")
        
        return output_file
    
    def _find_parent(self, root, element):
        """Находит родительский элемент для ElementTree"""
        for parent in root.iter():
            if element in parent:
                return parent
        return None
    
    def _add_camunda_namespaces(self, root):
        """Добавить Camunda namespaces"""
        print("🔧 Добавление Camunda namespaces...")
        
        # Получаем текущие атрибуты
        current_attribs = dict(root.attrib)
        
        # Добавляем только если их еще нет
        camunda_ns = "xmlns:camunda"
        xsi_ns = "xmlns:xsi"
        
        if camunda_ns not in current_attribs:
            root.set(camunda_ns, self.namespaces['camunda'])
        
        if xsi_ns not in current_attribs:
            root.set(xsi_ns, self.namespaces['xsi'])
        
        print("✅ Namespaces добавлены")
    
    def _update_process_attributes(self, root):
        """Обновить атрибуты процесса"""
        print("🔧 Обновление атрибутов процесса...")
        
        # Ищем элемент process
        process = root.find('.//bpmn:process', self.namespaces)
        if process is not None:
            # Сохраняем оригинальный ID (не изменяем согласно требованиям)
            original_id = process.get('id', 'Process_1d4oa6g46')
            
            # Устанавливаем isExecutable в true
            process.set('isExecutable', 'true')
            
            # Добавляем только необходимые Camunda атрибуты
            process.set('{http://camunda.org/schema/1.0/bpmn}historyTimeToLive', '1')
            
            # Добавляем name процесса из исходной схемы (если есть)
            if not process.get('name'):
                process.set('name', 'Разработка и получение разрешительной документации')
            
            print(f"✅ Процесс обновлен (ID: {original_id})")
        else:
            print("⚠️ Элемент process не найден")
    
    def _remove_collaboration_section(self, root):
        """Удалить секцию collaboration"""
        print("🔧 Удаление collaboration секции...")
        
        removed_count = 0
        
        # Удаляем collaboration и связанные элементы
        for element in root.findall('.//bpmn:collaboration', self.namespaces):
            # Запоминаем ID удаляемых элементов
            collab_id = element.get('id')
            if collab_id:
                self.removed_elements.add(collab_id)
            
            # Запоминаем все вложенные элементы
            for child in element.iter():
                child_id = child.get('id')
                if child_id:
                    self.removed_elements.add(child_id)
            
            root.remove(element)
            removed_count += 1
        
        # Удаляем textAnnotation, group, association
        for tag in ['textAnnotation', 'group', 'association']:
            for element in root.findall(f'.//bpmn:{tag}', self.namespaces):
                element_id = element.get('id')
                if element_id:
                    self.removed_elements.add(element_id)
                
                parent = self._find_parent(root, element)
                if parent is not None:
                    parent.remove(element)
                    removed_count += 1
        
        print(f"✅ Удалено {removed_count} элементов collaboration")
    
    def _remove_intermediate_events(self, root):
        """Удалить промежуточные события"""
        print("🔧 Удаление промежуточных событий...")
        
        removed_count = 0
        flows_to_redirect = {}  # incoming_flow_id -> new_target_ref
        
        # Находим все промежуточные события для удаления
        for event_type in self.elements_to_remove:
            for event in root.findall(f'.//bpmn:{event_type}', self.namespaces):
                event_id = event.get('id')
                if event_id:
                    self.removed_elements.add(event_id)
                    
                    # Для промежуточных событий находим входящие и исходящие потоки
                    if event_type in ['intermediateCatchEvent', 'intermediateThrowEvent']:
                        incoming = event.find('bpmn:incoming', self.namespaces)
                        outgoing = event.find('bpmn:outgoing', self.namespaces)
                        
                        if incoming is not None and outgoing is not None:
                            incoming_flow_id = incoming.text
                            outgoing_flow_id = outgoing.text
                            
                            # Находим исходящий поток для получения target
                            outgoing_seq = root.find(f'.//bpmn:sequenceFlow[@id="{outgoing_flow_id}"]', self.namespaces)
                            if outgoing_seq is not None:
                                new_target_ref = outgoing_seq.get('targetRef')
                                if new_target_ref:
                                    # Запоминаем, что нужно перенаправить входящий поток
                                    flows_to_redirect[incoming_flow_id] = new_target_ref
                            
                            # Помечаем исходящий поток для удаления
                            self.removed_flows.add(outgoing_flow_id)
                
                # Удаляем событие
                parent = self._find_parent(root, event)
                if parent is not None:
                    parent.remove(event)
                    removed_count += 1
        
        # Перенаправляем входящие потоки на новые цели
        for flow_id, new_target in flows_to_redirect.items():
            flow = root.find(f'.//bpmn:sequenceFlow[@id="{flow_id}"]', self.namespaces)
            if flow is not None:
                old_target = flow.get('targetRef')
                flow.set('targetRef', new_target)
                print(f"   ↪️ Поток {flow_id} перенаправлен: {old_target} → {new_target}")
                
                # Обновляем диаграммные координаты для этого потока
                self._update_flow_diagram_coordinates(root, flow_id, new_target)
        
        # Удаляем исходящие потоки промежуточных событий
        for flow in root.findall('.//bpmn:sequenceFlow', self.namespaces):
            flow_id = flow.get('id')
            if flow_id in self.removed_flows:
                parent = self._find_parent(root, flow)
                if parent is not None:
                    parent.remove(flow)
                    removed_count += 1
        
        # Обновляем ссылки в элементах процесса
        self._update_element_references(root)
        
        print(f"✅ Удалено {removed_count} промежуточных событий и потоков")
        
    def _update_flow_diagram_coordinates(self, root, flow_id, new_target_ref):
        """Обновить диаграммные координаты потока при перенаправлении"""
        print(f"   🎨 Обновление диаграммных координат для потока {flow_id}")
        
        # Находим диаграммный элемент потока
        flow_edge = root.find(f'.//bpmndi:BPMNEdge[@bpmnElement="{flow_id}"]', self.namespaces)
        if flow_edge is None:
            return
        
        # Находим диаграммный элемент нового целевого элемента
        target_shape = root.find(f'.//bpmndi:BPMNShape[@bpmnElement="{new_target_ref}"]', self.namespaces)
        if target_shape is None:
            return
        
        # Получаем координаты нового целевого элемента
        bounds = target_shape.find('dc:Bounds', self.namespaces)
        if bounds is None:
            return
        
        target_x = int(bounds.get('x', 0))
        target_y = int(bounds.get('y', 0))
        target_height = int(bounds.get('height', 80))
        
        # Вычисляем центр левой стороны целевого элемента
        new_x = target_x
        new_y = target_y + target_height // 2
        
        # Обновляем waypoints потока
        waypoints = flow_edge.findall('di:waypoint', self.namespaces)
        if len(waypoints) >= 2:
            # Обновляем последний waypoint (конечную точку)
            last_waypoint = waypoints[-1]
            last_waypoint.set('x', str(new_x))
            last_waypoint.set('y', str(new_y))
            print(f"      📍 Waypoint обновлен: x={new_x}, y={new_y}")
    
    def _update_element_references(self, root):
        """Обновить ссылки incoming/outgoing в элементах процесса"""
        print("🔧 Обновление ссылок элементов...")
        
        updated_count = 0
        
        # Для каждого элемента процесса обновляем ссылки
        for element in root.findall('.//*[@id]', self.namespaces):
            # Обновляем incoming ссылки
            for incoming in element.findall('bpmn:incoming', self.namespaces):
                flow_id = incoming.text
                if flow_id in self.removed_flows:
                    # Удаляем ссылку на удаленный поток
                    element.remove(incoming)
                    updated_count += 1
            
            # Обновляем outgoing ссылки
            for outgoing in element.findall('bpmn:outgoing', self.namespaces):
                flow_id = outgoing.text
                if flow_id in self.removed_flows:
                    # Удаляем ссылку на удаленный поток
                    element.remove(outgoing)
                    updated_count += 1
        
        # Добавляем недостающие incoming ссылки для элементов, на которые теперь указывают перенаправленные потоки
        for flow in root.findall('.//bpmn:sequenceFlow', self.namespaces):
            flow_id = flow.get('id')
            target_ref = flow.get('targetRef')
            
            if target_ref:
                # Находим целевой элемент
                target_element = root.find(f'.//*[@id="{target_ref}"]', self.namespaces)
                if target_element is not None:
                    # Проверяем, есть ли уже ссылка на этот поток
                    has_incoming = False
                    for incoming in target_element.findall('bpmn:incoming', self.namespaces):
                        if incoming.text == flow_id:
                            has_incoming = True
                            break
                    
                    if not has_incoming:
                        # Добавляем недостающую ссылку
                        incoming_element = ET.SubElement(target_element, f'{{{self.namespaces["bpmn"]}}}incoming')
                        incoming_element.text = flow_id
                        updated_count += 1
        
        print(f"✅ Обновлено {updated_count} ссылок")
    
    def _convert_tasks_to_service_tasks(self, root):
        """Конвертировать все типы задач в serviceTask"""
        print("🔧 Конвертация задач в serviceTask...")
        
        converted_count = 0
        
        for task_type in self.task_types_to_convert:
            for task in root.findall(f'.//bpmn:{task_type}', self.namespaces):
                # Создаем новый serviceTask элемент
                service_task = ET.Element(f'{{{self.namespaces["bpmn"]}}}serviceTask')
                
                # Копируем все атрибуты
                for key, value in task.attrib.items():
                    service_task.set(key, value)
                
                # Добавляем обязательные Camunda атрибуты для external tasks
                service_task.set(f'{{{self.namespaces["camunda"]}}}type', 'external')
                service_task.set(f'{{{self.namespaces["camunda"]}}}topic', 'bitrix_create_task')
                
                # Копируем все дочерние элементы
                for child in task:
                    service_task.append(child)
                
                # Заменяем элемент
                parent = self._find_parent(root, task)
                if parent is not None:
                    parent.insert(list(parent).index(task), service_task)
                    parent.remove(task)
                    converted_count += 1
        
        print(f"✅ Конвертировано {converted_count} задач")
    
    def _add_assignee_properties(self, root):
        """Добавить свойства ответственных к serviceTask элементам"""
        if not self.assignees_data:
            print("📋 Данные об ответственных отсутствуют, пропускаем встраивание")
            return
        
        print("🔧 Встраивание ответственных в serviceTask элементы...")
        
        added_count = 0
        
        # Создаем словарь для быстрого поиска ответственных по elementId
        assignees_by_element = {}
        for assignee in self.assignees_data:
            element_id = assignee.get('elementId')
            if element_id:
                if element_id not in assignees_by_element:
                    assignees_by_element[element_id] = []
                assignees_by_element[element_id].append(assignee)
        
        print(f"   📊 Найдено ответственных для {len(assignees_by_element)} элементов")
        
        # Обрабатываем все serviceTask элементы
        for service_task in root.findall('.//bpmn:serviceTask', self.namespaces):
            task_id = service_task.get('id')
            
            if task_id and task_id in assignees_by_element:
                assignees_list = assignees_by_element[task_id]
                
                # Берем первого ответственного (обычно один на элемент)
                assignee = assignees_list[0]
                assignee_name = assignee.get('assigneeName', '')
                assignee_id = str(assignee.get('assigneeId', ''))
                
                if assignee_name and assignee_id:
                    # Ищем или создаем extensionElements
                    extension_elements = service_task.find('bpmn:extensionElements', self.namespaces)
                    if extension_elements is None:
                        extension_elements = ET.SubElement(
                            service_task, 
                            f'{{{self.namespaces["bpmn"]}}}extensionElements'
                        )
                    
                    # Ищем или создаем camunda:properties
                    properties = extension_elements.find('camunda:properties', self.namespaces)
                    if properties is None:
                        properties = ET.SubElement(
                            extension_elements,
                            f'{{{self.namespaces["camunda"]}}}properties'
                        )
                    
                    # Добавляем свойство assigneeName
                    assignee_name_prop = ET.SubElement(
                        properties,
                        f'{{{self.namespaces["camunda"]}}}property'
                    )
                    assignee_name_prop.set('name', 'assigneeName')
                    assignee_name_prop.set('value', assignee_name)
                    
                    # Добавляем свойство assigneeId
                    assignee_id_prop = ET.SubElement(
                        properties,
                        f'{{{self.namespaces["camunda"]}}}property'
                    )
                    assignee_id_prop.set('name', 'assigneeId')
                    assignee_id_prop.set('value', assignee_id)
                    
                    print(f"   ✅ Добавлен ответственный для {task_id}: {assignee_name} ({assignee_id})")
                    added_count += 1
                    
                    # Если есть несколько ответственных, предупреждаем
                    if len(assignees_list) > 1:
                        print(f"   ⚠️ Элемент {task_id} имеет {len(assignees_list)} ответственных, добавлен только первый")
        
        print(f"✅ Встроено {added_count} ответственных")
    
    def _add_condition_expressions(self, root):
        """Добавить условные выражения к потокам"""
        print("🔧 Добавление условных выражений...")
        
        added_count = 0
        
        for flow in root.findall('.//bpmn:sequenceFlow', self.namespaces):
            name = flow.get('name', '').lower()
            
            # Проверяем, нет ли уже conditionExpression
            existing_condition = flow.find('bpmn:conditionExpression', self.namespaces)
            
            if not existing_condition:
                condition_expr = None
                
                if name == 'да':
                    condition_expr = '${result == "ok"}'
                elif name == 'нет':
                    condition_expr = '${result != "ok"}'
                
                if condition_expr:
                    # Создаем элемент conditionExpression
                    condition_element = ET.SubElement(
                        flow, 
                        f'{{{self.namespaces["bpmn"]}}}conditionExpression'
                    )
                    condition_element.set(
                        f'{{{self.namespaces["xsi"]}}}type',
                        'bpmn:tFormalExpression'
                    )
                    condition_element.text = condition_expr
                    added_count += 1
        
        print(f"✅ Добавлено {added_count} условных выражений")
    
    def _fix_element_order(self, root):
        """Исправить порядок элементов внутри BPMN узлов согласно спецификации"""
        print("🔧 Исправление порядка элементов...")
        
        fixed_count = 0
        
        # Элементы процесса, которые могут содержать incoming/outgoing
        process_elements = [
            'task', 'serviceTask', 'userTask', 'manualTask', 'businessRuleTask',
            'scriptTask', 'sendTask', 'receiveTask', 'callActivity',
            'startEvent', 'endEvent', 'intermediateCatchEvent', 'intermediateThrowEvent',
            'exclusiveGateway', 'parallelGateway', 'inclusiveGateway', 'eventBasedGateway',
            'complexGateway', 'subProcess'
        ]
        
        for element_type in process_elements:
            for element in root.findall(f'.//bpmn:{element_type}', self.namespaces):
                if self._fix_single_element_order(element):
                    fixed_count += 1
        
        # Также исправляем sequenceFlow элементы
        for flow in root.findall('.//bpmn:sequenceFlow', self.namespaces):
            if self._fix_sequence_flow_order(flow):
                fixed_count += 1
        
        print(f"✅ Исправлен порядок элементов в {fixed_count} узлах")
    
    def _fix_single_element_order(self, element):
        """Исправить порядок элементов в одном BPMN узле"""
        # Получаем все дочерние элементы
        children = list(element)
        
        if len(children) <= 1:
            return False  # Нечего исправлять
        
        # Категоризируем элементы
        extension_elements = []
        io_specification = []
        properties = []
        data_associations = []
        resource_roles = []
        loop_characteristics = []
        incoming_elements = []
        outgoing_elements = []
        other_elements = []
        
        for child in children:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            
            if tag_name == 'extensionElements':
                extension_elements.append(child)
            elif tag_name == 'ioSpecification':
                io_specification.append(child)
            elif tag_name == 'property':
                properties.append(child)
            elif tag_name in ['dataInputAssociation', 'dataOutputAssociation']:
                data_associations.append(child)
            elif tag_name in ['resourceRole', 'performer', 'humanPerformer', 'potentialOwner']:
                resource_roles.append(child)
            elif tag_name in ['loopCharacteristics', 'multiInstanceLoopCharacteristics']:
                loop_characteristics.append(child)
            elif tag_name == 'incoming':
                incoming_elements.append(child)
            elif tag_name == 'outgoing':
                outgoing_elements.append(child)
            else:
                other_elements.append(child)
        
        # Проверяем, нужно ли исправление
        current_order = [child.tag.split('}')[-1] if '}' in child.tag else child.tag for child in children]
        
        # Строим правильный порядок
        correct_order = []
        
        # 1. Специальные элементы в начале
        correct_order.extend(extension_elements)
        correct_order.extend(io_specification)
        correct_order.extend(properties)
        correct_order.extend(data_associations)
        correct_order.extend(resource_roles)
        correct_order.extend(loop_characteristics)
        
        # 2. Все incoming элементы
        correct_order.extend(incoming_elements)
        
        # 3. Все outgoing элементы
        correct_order.extend(outgoing_elements)
        
        # 4. Остальные элементы
        correct_order.extend(other_elements)
        
        # Проверяем, отличается ли порядок
        new_order = [child.tag.split('}')[-1] if '}' in child.tag else child.tag for child in correct_order]
        
        if current_order != new_order:
            # Удаляем все дочерние элементы
            for child in children:
                element.remove(child)
            
            # Добавляем в правильном порядке
            for child in correct_order:
                element.append(child)
            
            return True
        
        return False
    
    def _fix_sequence_flow_order(self, flow):
        """Исправить порядок элементов в sequenceFlow"""
        children = list(flow)
        
        if len(children) <= 1:
            return False
        
        # Для sequenceFlow правильный порядок:
        # 1. extensionElements (если есть)
        # 2. conditionExpression (если есть)
        # 3. все остальное
        
        extension_elements = []
        condition_expressions = []
        other_elements = []
        
        for child in children:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            
            if tag_name == 'extensionElements':
                extension_elements.append(child)
            elif tag_name == 'conditionExpression':
                condition_expressions.append(child)
            else:
                other_elements.append(child)
        
        # Строим правильный порядок
        correct_order = []
        correct_order.extend(extension_elements)
        correct_order.extend(condition_expressions)
        correct_order.extend(other_elements)
        
        # Проверяем, нужно ли исправление
        if len(correct_order) != len(children) or any(correct_order[i] != children[i] for i in range(len(children))):
            # Удаляем все дочерние элементы
            for child in children:
                flow.remove(child)
            
            # Добавляем в правильном порядке
            for child in correct_order:
                flow.append(child)
            
            return True
        
        return False
    
    def _fix_default_flows(self, root):
        """Исправить конфликты default flow - убрать атрибут default у потоков с условиями"""
        print("🔧 Исправление default flow конфликтов...")
        
        fixed_count = 0
        
        # Находим все exclusiveGateway элементы
        for gateway in root.findall('.//bpmn:exclusiveGateway', self.namespaces):
            gateway_id = gateway.get('id')
            default_flow_id = gateway.get('default')
            
            # Если у шлюза есть атрибут default
            if default_flow_id:
                # Находим соответствующий sequenceFlow
                default_flow = root.find(f'.//bpmn:sequenceFlow[@id="{default_flow_id}"]', self.namespaces)
                
                if default_flow is not None:
                    # Проверяем, есть ли у потока условие
                    condition = default_flow.find('bpmn:conditionExpression', self.namespaces)
                    
                    if condition is not None:
                        # Поток помечен как default И имеет условие - это конфликт!
                        print(f"   ⚠️ Найден конфликт: Gateway '{gateway_id}' → Flow '{default_flow_id}' (default + условие)")
                        
                        # Убираем атрибут default у шлюза
                        gateway.attrib.pop('default', None)
                        
                        print(f"   ✅ Убран атрибут default у шлюза '{gateway_id}'")
                        fixed_count += 1
                
                else:
                    print(f"   ⚠️ Default flow '{default_flow_id}' не найден для шлюза '{gateway_id}'")
        
        if fixed_count > 0:
            print(f"✅ Исправлено {fixed_count} конфликтов default flow")
        else:
            print("✅ Конфликтов default flow не найдено")
    
    def _clean_diagram_elements(self, root):
        """Очистить диаграммные элементы, ссылающиеся на удаленные элементы"""
        print("🔧 Очистка диаграммных элементов...")
        
        removed_count = 0
        
        # Находим BPMNDiagram
        bpmn_diagram = root.find('.//bpmndi:BPMNDiagram', self.namespaces)
        if bpmn_diagram is None:
            print("⚠️ BPMNDiagram не найден")
            return
        
        # Удаляем диаграммные элементы для удаленных элементов процесса
        for shape in bpmn_diagram.findall('.//bpmndi:BPMNShape', self.namespaces):
            bpmn_element = shape.get('bpmnElement')
            if bpmn_element in self.removed_elements:
                parent = self._find_parent(root, shape)
                if parent is not None:
                    parent.remove(shape)
                    removed_count += 1
        
        for edge in bpmn_diagram.findall('.//bpmndi:BPMNEdge', self.namespaces):
            bpmn_element = edge.get('bpmnElement')
            if bpmn_element in self.removed_elements or bpmn_element in self.removed_flows:
                parent = self._find_parent(root, edge)
                if parent is not None:
                    parent.remove(edge)
                    removed_count += 1
        
        print(f"✅ Удалено {removed_count} диаграммных элементов")
    
    def _update_bpmn_plane(self, root):
        """Обновить BPMNPlane с правильным bpmnElement"""
        print("🔧 Обновление BPMNPlane...")
        
        # Находим процесс
        process = root.find('.//bpmn:process', self.namespaces)
        if process is None:
            print("⚠️ Process не найден")
            return
        
        process_id = process.get('id')
        if not process_id:
            print("⚠️ Process ID не найден")
            return
        
        # Находим BPMNPlane
        bpmn_plane = root.find('.//bpmndi:BPMNPlane', self.namespaces)
        if bpmn_plane is None:
            print("⚠️ BPMNPlane не найден")
            return
        
        # Устанавливаем правильный bpmnElement
        bpmn_plane.set('bpmnElement', process_id)
        
        print(f"✅ BPMNPlane обновлен (bpmnElement: {process_id})")
    
    def _save_result(self, tree, output_file):
        """Сохранить результат"""
        print(f"💾 Сохранение результата...")
        
        # Сохраняем с правильным форматированием
        tree.write(
            output_file,
            encoding='utf-8',
            xml_declaration=True,
            method='xml'
        )
        
        # Читаем файл и исправляем форматирование
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Исправляем форматирование первой строки
        content = content.replace(
            "<?xml version='1.0' encoding='utf-8'?>",
            '<?xml version="1.0" encoding="UTF-8"?>'
        )
        
        # Удаляем дублированные namespace-ы если они есть
        content = self._remove_duplicate_namespaces(content)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Файл сохранен")
    
    def _remove_duplicate_namespaces(self, content):
        """Удалить дублированные namespace-ы"""
        # Ищем строку с definitions
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '<bpmn:definitions' in line:
                # Удаляем дублированные xmlns:camunda и xmlns:xsi более точно
                # Сначала находим все вхождения и заменяем на одно
                import re
                
                # Удаляем все вхождения xmlns:camunda кроме первого
                camunda_matches = list(re.finditer(r'xmlns:camunda="[^"]*"', line))
                if len(camunda_matches) > 1:
                    # Оставляем только первое вхождение
                    for match in reversed(camunda_matches[1:]):
                        line = line[:match.start()] + line[match.end():]
                
                # Удаляем все вхождения xmlns:xsi кроме первого
                xsi_matches = list(re.finditer(r'xmlns:xsi="[^"]*"', line))
                if len(xsi_matches) > 1:
                    # Оставляем только первое вхождение
                    for match in reversed(xsi_matches[1:]):
                        line = line[:match.start()] + line[match.end():]
                
                # Убираем лишние пробелы
                line = re.sub(r'\s+', ' ', line)
                
                lines[i] = line
                break
        
        return '\n'.join(lines)


def main():
    """Функция для тестирования"""
    if len(sys.argv) > 1:
        converter = BPMNConverter()
        try:
            result = converter.convert_file(sys.argv[1])
            print(f"\n🎉 Конвертация успешна: {result}")
        except Exception as e:
            print(f"\n❌ Ошибка при конвертации: {e}")
            print(f"🔍 Тип ошибки: {type(e).__name__}")
            
            # Добавляем детальную информацию об ошибке
            import traceback
            print("📍 Детали ошибки:")
            traceback.print_exc(limit=3)
            return 1
    else:
        print("Использование: python bpmn_converter.py <input_file.bpmn>")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 