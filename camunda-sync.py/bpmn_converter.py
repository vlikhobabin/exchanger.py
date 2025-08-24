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
        
        # ВРЕМЕННО ОТКЛЮЧЕНЫ: Определяем ID процесса и загружаем расширения
        # process_id = self._get_process_id(root)
        # extension_module = None
        
        # if process_id:
        #     extension_module = self._load_process_extension(process_id)
        
        # # Выполняем предобработку (если есть расширение)  
        # if extension_module:
        #     try:
        #         print("🔧 Выполнение предобработки расширения...")
        #         extension_module.pre_process(root, self)
        #         print("✅ Предобработка расширения завершена")
        #     except Exception as e:
        #         print(f"⚠️ Ошибка при выполнении предобработки: {e}")
        #         print("Продолжаем стандартную обработку...")
        
        # Встроенная логика из расширения Process_1d4oa6g46 (предобработка)
        self._insert_intermediate_tasks_for_yes_flows(root)
        
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
        
        # ВРЕМЕННО ОТКЛЮЧЕНО: Выполняем постобработку (если есть расширение)
        # if extension_module:
        #     try:
        #         print("🔧 Выполнение постобработки расширения...")
        #         extension_module.post_process(root, self)
        #         print("✅ Постобработка расширения завершена")
        #     except Exception as e:
        #         print(f"⚠️ Ошибка при выполнении постобработки: {e}")
        #         print("Сохраняем результат...")
        
        # Встроенная логика из расширения Process_1d4oa6g46 (постобработка)
        self._assign_responsible_to_unassigned_tasks(root)
        
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
        
        # Извлекаем данные из Collaboration/Participant
        process_data = self._extract_process_data_from_collaboration(root)
        
        # Ищем элемент process
        process = root.find('.//bpmn:process', self.namespaces)
        if process is not None:
            # Получаем ID процесса
            current_id = process.get('id')
            
            # Если из Collaboration получили новый ID, используем его
            if process_data['id'] and process_data['id'] != current_id:
                print(f"🔄 Обновляем ID процесса: {current_id} → {process_data['id']}")
                process.set('id', process_data['id'])
                current_id = process_data['id']
            elif not current_id:
                # Если вообще нет ID, ставим дефолтный (маловероятно)
                current_id = 'Process_default'
                process.set('id', current_id)
                print(f"⚠️ Установлен дефолтный ID процесса: {current_id}")
            
            # Устанавливаем isExecutable в true
            process.set('isExecutable', 'true')
            
            # Добавляем только необходимые Camunda атрибуты
            process.set('{http://camunda.org/schema/1.0/bpmn}historyTimeToLive', '1')
            
            # Обновляем name процесса из данных Collaboration/Participant
            if process_data['name']:
                print(f"🔄 Обновляем название процесса: {process_data['name']}")
                process.set('name', process_data['name'])
            elif not process.get('name'):
                # Если нет названия вообще, ставим дефолтное
                default_name = 'Автоматически сконвертированный процесс'
                process.set('name', default_name)
                print(f"⚠️ Установлено дефолтное название: {default_name}")
            
            print(f"✅ Процесс обновлен (ID: {current_id})")
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
        updated_tasks = set()  # Отслеживание задач, к которым уже добавили свойства
        
        for flow in root.findall('.//bpmn:sequenceFlow', self.namespaces):
            name = flow.get('name', '').lower()
            
            # Проверяем, нет ли уже conditionExpression
            existing_condition = flow.find('bpmn:conditionExpression', self.namespaces)
            
            if not existing_condition and name in ['да', 'нет']:
                source_ref = flow.get('sourceRef')
                
                if source_ref:
                    # Ищем serviceTask, который привел к этому шлюзу
                    service_task_id = self._find_source_service_task(root, source_ref)
                    
                    if service_task_id:
                        # Формируем условное выражение с использованием ID serviceTask
                        if name == 'да':
                            condition_expr = '${' + service_task_id + ' == "ok"}'
                        elif name == 'нет':
                            condition_expr = '${' + service_task_id + ' != "ok"}'
                        
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
                        
                        print(f"   ✅ Поток {flow.get('id')} ({name}): {condition_expr}")
                        
                        # Добавляем свойства к исходной задаче
                        if service_task_id not in updated_tasks:
                            gateway_name = self._get_gateway_name(root, source_ref)
                            if gateway_name:
                                self._add_result_properties_to_task(root, service_task_id, gateway_name)
                                updated_tasks.add(service_task_id)
                                print(f"   🔧 Добавлены свойства результата к задаче {service_task_id}")
                    else:
                        print(f"   ⚠️ Не найден serviceTask для потока {flow.get('id')} из шлюза {source_ref}")
        
        print(f"✅ Добавлено {added_count} условных выражений")
        print(f"✅ Обновлено {len(updated_tasks)} задач с свойствами результата")
    
    def _find_source_service_task(self, root, gateway_id, visited=None):
        """Найти serviceTask, который привел к указанному шлюзу (с рекурсивным поиском)"""
        if visited is None:
            visited = set()
        
        # Защита от бесконечной рекурсии
        if gateway_id in visited:
            print(f"   ⚠️ Обнаружена циклическая зависимость для {gateway_id}")
            return None
        
        visited.add(gateway_id)
        
        # Находим шлюз (inclusiveGateway или exclusiveGateway)
        gateway = None
        for gateway_type in ['inclusiveGateway', 'exclusiveGateway']:
            gateway = root.find(f'.//bpmn:{gateway_type}[@id="{gateway_id}"]', self.namespaces)
            if gateway is not None:
                break
        
        if gateway is None:
            print(f"   ⚠️ Шлюз {gateway_id} не найден")
            return None
        
        # Получаем входящий поток шлюза (берем первый, если их несколько)
        incoming_element = gateway.find('bpmn:incoming', self.namespaces)
        if incoming_element is None:
            print(f"   ⚠️ Входящий поток для шлюза {gateway_id} не найден")
            return None
        
        incoming_flow_id = incoming_element.text
        
        # Находим sequenceFlow с этим ID
        incoming_flow = root.find(f'.//bpmn:sequenceFlow[@id="{incoming_flow_id}"]', self.namespaces)
        if incoming_flow is None:
            print(f"   ⚠️ Входящий sequenceFlow {incoming_flow_id} не найден")
            return None
        
        # Получаем sourceRef входящего потока
        source_ref = incoming_flow.get('sourceRef')
        if not source_ref:
            print(f"   ⚠️ sourceRef для входящего потока {incoming_flow_id} не найден")
            return None
        
        # Рекурсивно ищем ближайшую задачу
        return self._find_task_recursively(root, source_ref, visited.copy())
    
    def _find_task_recursively(self, root, element_id, visited):
        """Рекурсивно найти ближайшую задачу в цепочке элементов"""
        
        # Защита от бесконечной рекурсии
        if element_id in visited:
            print(f"   ⚠️ Обнаружена циклическая зависимость для элемента {element_id}")
            return None
        
        visited.add(element_id)
        
        # Типы задач, которые мы принимаем как источники
        task_types = ['task', 'serviceTask', 'userTask', 'manualTask', 'businessRuleTask',
                     'scriptTask', 'sendTask', 'receiveTask', 'callActivity']
        
        # Сначала проверяем, является ли элемент задачей
        for task_type in task_types:
            task = root.find(f'.//bpmn:{task_type}[@id="{element_id}"]', self.namespaces)
            if task is not None:
                task_name = task.get('name', 'Без имени')
                print(f"   🔍 Найдена задача {task_type} {element_id} ({task_name})")
                return element_id
        
        # Если не задача, ищем элемент и определяем его тип
        element = root.find(f'.//*[@id="{element_id}"]', self.namespaces)
        if element is None:
            print(f"   ❌ Элемент {element_id} не найден")
            return None
        
        element_type = element.tag.split('}')[-1] if '}' in element.tag else element.tag
        element_name = element.get('name', 'Без имени')
        
        print(f"   🔗 Анализируем промежуточный элемент: {element_type} {element_id} ({element_name})")
        
        # Обрабатываем промежуточные элементы
        if element_type in ['inclusiveGateway', 'exclusiveGateway', 'parallelGateway']:
            # Для шлюзов ищем их входящие потоки
            return self._find_source_through_gateway(root, element_id, element_type, visited)
        
        elif element_type in ['intermediateCatchEvent', 'intermediateThrowEvent', 'startEvent']:
            # Для событий ищем их входящие потоки
            return self._find_source_through_event(root, element_id, element_type, visited)
        
        else:
            print(f"   ⚠️ Неподдерживаемый тип элемента: {element_type}")
            return None
    
    def _find_source_through_gateway(self, root, gateway_id, gateway_type, visited):
        """Найти источник через промежуточный шлюз"""
        
        gateway = root.find(f'.//bpmn:{gateway_type}[@id="{gateway_id}"]', self.namespaces)
        if gateway is None:
            return None
        
        # Получаем входящие потоки
        incoming_elements = gateway.findall('bpmn:incoming', self.namespaces)
        
        if not incoming_elements:
            print(f"   ⚠️ Нет входящих потоков для {gateway_type} {gateway_id}")
            return None
        
        # Для каждого входящего потока пытаемся найти задачу
        for incoming in incoming_elements:
            flow_id = incoming.text
            flow = root.find(f'.//bpmn:sequenceFlow[@id="{flow_id}"]', self.namespaces)
            
            if flow is not None:
                source_ref = flow.get('sourceRef')
                if source_ref:
                    print(f"   🔄 Рекурсивный поиск через поток {flow_id} → {source_ref}")
                    result = self._find_task_recursively(root, source_ref, visited.copy())
                    if result:
                        return result
        
        return None
    
    def _find_source_through_event(self, root, event_id, event_type, visited):
        """Найти источник через промежуточное событие"""
        
        event = root.find(f'.//bpmn:{event_type}[@id="{event_id}"]', self.namespaces)
        if event is None:
            return None
        
        # Получаем входящие потоки события
        incoming_elements = event.findall('bpmn:incoming', self.namespaces)
        
        if not incoming_elements:
            print(f"   ⚠️ Нет входящих потоков для {event_type} {event_id}")
            return None
        
        # Берем первый входящий поток (события обычно имеют один входящий поток)
        flow_id = incoming_elements[0].text
        flow = root.find(f'.//bpmn:sequenceFlow[@id="{flow_id}"]', self.namespaces)
        
        if flow is not None:
            source_ref = flow.get('sourceRef')
            if source_ref:
                print(f"   🔄 Рекурсивный поиск через событие {flow_id} → {source_ref}")
                return self._find_task_recursively(root, source_ref, visited.copy())
        
        return None
    
    def _get_gateway_name(self, root, gateway_id):
        """Получить name шлюза по его ID"""
        for gateway_type in ['inclusiveGateway', 'exclusiveGateway', 'parallelGateway']:
            gateway = root.find(f'.//bpmn:{gateway_type}[@id="{gateway_id}"]', self.namespaces)
            if gateway is not None:
                return gateway.get('name', '')
        return None
    
    def _add_result_properties_to_task(self, root, service_task_id, gateway_name):
        """Добавить свойства UF_RESULT_EXPECTED и UF_RESULT_QUESTION к serviceTask"""
        
        # Находим serviceTask
        service_task = root.find(f'.//bpmn:serviceTask[@id="{service_task_id}"]', self.namespaces)
        if service_task is None:
            print(f"   ⚠️ ServiceTask {service_task_id} не найден")
            return
        
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
        
        # Проверяем, нет ли уже свойства UF_RESULT_EXPECTED
        existing_expected = None
        existing_question = None
        for prop in properties.findall('camunda:property', self.namespaces):
            prop_name = prop.get('name')
            if prop_name == 'UF_RESULT_EXPECTED':
                existing_expected = prop
            elif prop_name == 'UF_RESULT_QUESTION':
                existing_question = prop
        
        # Добавляем UF_RESULT_EXPECTED если его нет
        if existing_expected is None:
            result_expected_prop = ET.SubElement(
                properties,
                f'{{{self.namespaces["camunda"]}}}property'
            )
            result_expected_prop.set('name', 'UF_RESULT_EXPECTED')
            result_expected_prop.set('value', 'true')
        else:
            # Обновляем существующее значение
            existing_expected.set('value', 'true')
        
        # Добавляем UF_RESULT_QUESTION если его нет
        if existing_question is None:
            result_question_prop = ET.SubElement(
                properties,
                f'{{{self.namespaces["camunda"]}}}property'
            )
            result_question_prop.set('name', 'UF_RESULT_QUESTION')
            result_question_prop.set('value', gateway_name)
        else:
            # Обновляем существующее значение
            existing_question.set('value', gateway_name)
    
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
    
    def _get_process_id(self, root) -> Optional[str]:
        """Извлечь ID процесса из BPMN XML"""
        try:
            process = root.find('.//bpmn:process', self.namespaces)
            if process is not None:
                process_id = process.get('id')
                if process_id:
                    print(f"🔍 Обнаружен процесс с ID: {process_id}")
                    return process_id
            print("⚠️ ID процесса не найден в BPMN схеме")
            return None
        except Exception as e:
            print(f"⚠️ Ошибка при извлечении ID процесса: {e}")
            return None

    def _extract_process_data_from_collaboration(self, root) -> Dict[str, Optional[str]]:
        """
        Извлечь данные процесса из Collaboration/Participant
        
        Returns:
            Dict с ключами 'id' и 'name' процесса, извлеченными из первого participant
        """
        try:
            # Ищем collaboration
            collaboration = root.find('.//bpmn:collaboration', self.namespaces)
            if collaboration is None:
                print("📋 Collaboration не найден, используем существующие данные процесса")
                # Если нет collaboration, берем данные из самого процесса
                process = root.find('.//bpmn:process', self.namespaces)
                if process is not None:
                    return {
                        'id': process.get('id'),
                        'name': process.get('name')
                    }
                return {'id': None, 'name': None}
            
            # Ищем первого participant
            participants = collaboration.findall('bpmn:participant', self.namespaces)
            if not participants:
                print("⚠️ Participant не найден в Collaboration")
                return {'id': None, 'name': None}
            
            first_participant = participants[0]
            participant_id = first_participant.get('id')
            participant_name = first_participant.get('name', '')
            process_ref = first_participant.get('processRef')
            
            print(f"🔍 Найден первый participant:")
            print(f"   ID: {participant_id}")
            print(f"   Name: {participant_name}")
            print(f"   ProcessRef: {process_ref}")
            
            # Очистка имени от HTML символов если есть
            if participant_name:
                import html
                participant_name = html.unescape(participant_name)
                # Заменяем переносы строк на пробелы
                participant_name = participant_name.replace('\n', ' ').replace('\r', ' ')
                # Убираем лишние пробелы
                participant_name = ' '.join(participant_name.split())
            
            return {
                'id': participant_id,  # Используем ID самого participant как ID процесса
                'name': participant_name
            }
            
        except Exception as e:
            print(f"⚠️ Ошибка при извлечении данных из Collaboration: {e}")
            return {'id': None, 'name': None}
    
    def _load_process_extension(self, process_id: str):
        """
        Загрузить модуль расширения для конкретного процесса
        
        Args:
            process_id: ID процесса
            
        Returns:
            Модуль расширения или None если не найден
        """
        try:
            import importlib.util
            from pathlib import Path
            
            # Путь к файлу расширения
            extension_path = Path(__file__).parent / "extensions" / process_id / "process_extension.py"
            
            if not extension_path.exists():
                print(f"📋 Расширение для процесса {process_id} не найдено")
                return None
            
            print(f"🔧 Загружаем расширение для процесса {process_id}...")
            
            # Динамическая загрузка модуля
            spec = importlib.util.spec_from_file_location(
                f"process_extension_{process_id}", 
                extension_path
            )
            
            if spec is None or spec.loader is None:
                print(f"⚠️ Не удалось создать спецификацию для модуля {process_id}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Проверяем наличие обязательных методов
            if not hasattr(module, 'pre_process') or not hasattr(module, 'post_process'):
                print(f"⚠️ Расширение {process_id} не содержит методов pre_process/post_process")
                return None
            
            # Вывод информации о расширении (если есть)
            if hasattr(module, 'EXTENSION_INFO'):
                info = module.EXTENSION_INFO
                print(f"   📋 Название: {info.get('process_name', 'Не указано')}")
                print(f"   📦 Версия: {info.get('version', 'Не указано')}")
                print(f"   📝 Описание: {info.get('description', 'Не указано')}")
            
            print(f"   ✅ Расширение загружено успешно")
            return module
            
        except Exception as e:
            print(f"⚠️ Ошибка при загрузке расширения для {process_id}: {e}")
            return None
    
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

    def _insert_intermediate_tasks_for_yes_flows(self, root):
        """
        Вставить промежуточные задачи между шлюзами для разрыва цепочек Gateway → Gateway
        (перенесено из расширения Process_1d4oa6g46)
        """
        print("🔧 Вставка промежуточных задач между шлюзами...")
        
        # Поиск всех sequenceFlow с name="да" и вставка промежуточных задач
        inserted_tasks = self._insert_intermediate_tasks_for_yes_flows_impl(root)
        
        if inserted_tasks > 0:
            print(f"✅ Вставлено промежуточных задач: {inserted_tasks}")
        else:
            print("✅ Промежуточные задачи не требуются")
    
    def _insert_intermediate_tasks_for_yes_flows_impl(self, root) -> int:
        """
        Найти все sequenceFlow с name="да" и вставить промежуточные задачи между шлюзами
        
        Returns:
            int: Количество вставленных задач
        """
        print("   🔍 Поиск sequenceFlow с name='да' для вставки промежуточных задач...")
        
        inserted_count = 0
        
        # Найти все sequenceFlow с name="да"
        yes_flows = []
        for flow in root.findall('.//bpmn:sequenceFlow', self.namespaces):
            name = flow.get('name', '').lower()
            if name == 'да':
                yes_flows.append(flow)
        
        print(f"   📊 Найдено sequenceFlow с name='да': {len(yes_flows)}")
        
        for flow in yes_flows:
            flow_id = flow.get('id')
            source_ref = flow.get('sourceRef')
            
            if not source_ref:
                print(f"      ⚠️ Поток {flow_id} не имеет sourceRef")
                continue
            
            print(f"   🔍 Анализируем поток {flow_id}: sourceRef={source_ref}")
            
            # Найти исходный Gateway
            source_gateway = self._find_gateway_by_id(root, source_ref)
            if not source_gateway:
                print(f"      ⚠️ Gateway {source_ref} не найден")
                continue
            
            print(f"      ✅ Gateway {source_ref} найден: {source_gateway.tag}")
            
            # Получить incoming flows этого Gateway
            incoming_flows = source_gateway.findall('bpmn:incoming', self.namespaces)
            print(f"      📊 Найдено incoming потоков для {source_ref}: {len(incoming_flows)}")
            
            for i, incoming_element in enumerate(incoming_flows):
                incoming_flow_id = incoming_element.text
                print(f"      🔗 Анализируем incoming поток #{i+1}: {incoming_flow_id}")
                
                # Найти incoming sequenceFlow
                incoming_flow = root.find(f'.//bpmn:sequenceFlow[@id="{incoming_flow_id}"]', self.namespaces)
                
                if incoming_flow is None:
                    print(f"         ❌ sequenceFlow {incoming_flow_id} не найден")
                    continue
                
                incoming_source_ref = incoming_flow.get('sourceRef')
                print(f"         📍 Источник incoming потока: {incoming_source_ref}")
                
                # Проверить, является ли источник входящего потока Gateway
                if incoming_source_ref and incoming_source_ref.startswith('Gateway_'):
                    print(f"         🎯 Найдена цепочка Gateway→Gateway: {incoming_source_ref} → {source_ref}")
                    
                    # Вставить промежуточную задачу
                    print(f"         🔧 Попытка вставки промежуточной задачи...")
                    task_inserted = self._insert_task_between_gateways(
                        root, incoming_flow, source_gateway, source_ref
                    )
                    
                    if task_inserted:
                        inserted_count += 1
                        print(f"         ✅ Вставлена промежуточная задача (всего: {inserted_count})")
                    else:
                        print(f"         ❌ Не удалось вставить промежуточную задачу")
                else:
                    print(f"         ℹ️ Источник не Gateway ('{incoming_source_ref}'), пропускаем")
        
        print(f"   📊 Итого вставлено промежуточных задач: {inserted_count}")
        return inserted_count

    def _find_gateway_by_id(self, root, gateway_id: str):
        """Найти Gateway по ID"""
        for gateway_type in ['exclusiveGateway', 'inclusiveGateway', 'parallelGateway']:
            gateway = root.find(f'.//bpmn:{gateway_type}[@id="{gateway_id}"]', self.namespaces)
            if gateway is not None:
                return gateway
        return None

    def _insert_task_between_gateways(self, root, incoming_flow, target_gateway, target_gateway_id: str) -> bool:
        """
        Вставить промежуточную задачу между двумя Gateway
        
        Args:
            root: Корневой элемент BPMN XML
            incoming_flow: sequenceFlow который нужно перенаправить
            target_gateway: Gateway, в который нужно вставить задачу
            target_gateway_id: ID целевого Gateway
        
        Returns:
            bool: True если задача была вставлена
        """
        try:
            incoming_flow_id = incoming_flow.get('id')
            print(f"         🔧 Начинаем вставку задачи для incoming_flow: {incoming_flow_id}")
            
            # Генерировать уникальные ID
            new_task_id = self._generate_unique_activity_id(root)
            new_flow_id = self._generate_unique_flow_id(root)
            print(f"         🆔 Сгенерированы ID: task={new_task_id}, flow={new_flow_id}")
            
            # Получить name целевого Gateway для формирования имени задачи
            gateway_name = target_gateway.get('name', 'условие')
            task_name = f"Выяснить: {gateway_name}"
            
            print(f"         📝 Создание задачи {new_task_id}: '{task_name}'")
            
            # Найти элемент process для вставки новой задачи
            process_element = root.find('.//bpmn:process', self.namespaces)
            if not process_element:
                print(f"         ❌ Элемент process не найден")
                return False
            
            print(f"         ✅ Process элемент найден")
            
            # Создать новую задачу (serviceTask для совместимости с Camunda)
            new_task = ET.SubElement(process_element, f'{{{self.namespaces["bpmn"]}}}serviceTask')
            new_task.set('id', new_task_id)
            new_task.set('name', task_name)
            new_task.set(f'{{{self.namespaces["camunda"]}}}type', 'external')
            new_task.set(f'{{{self.namespaces["camunda"]}}}topic', 'bitrix_create_task')
            
            # Создать extensionElements с необходимыми свойствами
            extension_elements = ET.SubElement(new_task, f'{{{self.namespaces["bpmn"]}}}extensionElements')
            properties = ET.SubElement(extension_elements, f'{{{self.namespaces["camunda"]}}}properties')
            
            # Добавить свойства для определения результата
            result_expected_prop = ET.SubElement(properties, f'{{{self.namespaces["camunda"]}}}property')
            result_expected_prop.set('name', 'UF_RESULT_EXPECTED')
            result_expected_prop.set('value', 'true')
            
            result_question_prop = ET.SubElement(properties, f'{{{self.namespaces["camunda"]}}}property')
            result_question_prop.set('name', 'UF_RESULT_QUESTION')
            result_question_prop.set('value', gateway_name)
            
            # Добавить ответственного по умолчанию
            assignee_name_prop = ET.SubElement(properties, f'{{{self.namespaces["camunda"]}}}property')
            assignee_name_prop.set('name', 'assigneeName')
            assignee_name_prop.set('value', 'Рук. отдела разрешительной док-ции')
            
            assignee_id_prop = ET.SubElement(properties, f'{{{self.namespaces["camunda"]}}}property')
            assignee_id_prop.set('name', 'assigneeId')
            assignee_id_prop.set('value', '15297786')
            
            print(f"         ✅ Создан элемент serviceTask с extensionElements: {new_task_id}")
            
            # Добавить incoming для новой задачи (из исходного потока)
            task_incoming = ET.SubElement(new_task, f'{{{self.namespaces["bpmn"]}}}incoming')
            task_incoming.text = incoming_flow_id
            print(f"         ✅ Добавлен incoming: {incoming_flow_id}")
            
            # Добавить outgoing для новой задачи (новый поток к целевому Gateway)
            task_outgoing = ET.SubElement(new_task, f'{{{self.namespaces["bpmn"]}}}outgoing')
            task_outgoing.text = new_flow_id
            print(f"         ✅ Добавлен outgoing: {new_flow_id}")
            
            # Создать новый sequenceFlow от задачи к целевому Gateway
            new_sequence_flow = ET.SubElement(process_element, f'{{{self.namespaces["bpmn"]}}}sequenceFlow')
            new_sequence_flow.set('id', new_flow_id)
            new_sequence_flow.set('sourceRef', new_task_id)
            new_sequence_flow.set('targetRef', target_gateway_id)
            print(f"         ✅ Создан новый sequenceFlow: {new_flow_id} ({new_task_id} → {target_gateway_id})")
            
            # Обновить исходный incoming_flow: теперь он ведет к новой задаче
            old_target = incoming_flow.get('targetRef')
            incoming_flow.set('targetRef', new_task_id)
            print(f"         ✅ Обновлен incoming_flow {incoming_flow_id}: {old_target} → {new_task_id}")
            
            # Обновить incoming потоки целевого Gateway
            self._update_gateway_incoming_flows(target_gateway, incoming_flow_id, new_flow_id)
            print(f"         ✅ Обновлены incoming потоки Gateway {target_gateway_id}")
            
            # Создать диаграммные элементы для новых объектов
            self._create_diagram_elements_for_task(root, new_task_id, new_flow_id, target_gateway_id, incoming_flow_id)
            
            print(f"         🎉 Задача {new_task_id} успешно вставлена")
            print(f"         📎 Итоговая цепочка: ...→{new_task_id}→{target_gateway_id}")
            
            return True
            
        except Exception as e:
            print(f"         ❌ Ошибка при вставке задачи: {e}")
            import traceback
            print(f"         🔍 Детали ошибки:")
            traceback.print_exc(limit=2)
            return False

    def _update_gateway_incoming_flows(self, gateway, old_flow_id: str, new_flow_id: str):
        """Обновить incoming потоки Gateway"""
        
        # Найти и обновить соответствующий incoming элемент
        for incoming in gateway.findall('bpmn:incoming', self.namespaces):
            if incoming.text == old_flow_id:
                incoming.text = new_flow_id
                break

    def _create_diagram_elements_for_task(self, root, new_task_id: str, new_flow_id: str, 
                                        target_gateway_id: str, incoming_flow_id: str) -> None:
        """Создать диаграммные элементы для новой задачи и потока"""
        
        try:
            # Найти BPMNDiagram
            bpmn_diagram = root.find('.//bpmndi:BPMNDiagram', self.namespaces)
            if bpmn_diagram is None:
                print(f"         ⚠️ BPMNDiagram не найден, пропускаем создание диаграммных элементов")
                return
            
            bpmn_plane = bpmn_diagram.find('.//bpmndi:BPMNPlane', self.namespaces)
            if bpmn_plane is None:
                print(f"         ⚠️ BPMNPlane не найден, пропускаем создание диаграммных элементов")
                return
            
            # Получить координаты существующих элементов для позиционирования
            source_coords, target_coords = self._get_positioning_coordinates_for_task(
                root, incoming_flow_id, target_gateway_id
            )
            
            if source_coords is None or target_coords is None:
                print(f"         ⚠️ Не удалось получить координаты для позиционирования")
                return
            
            # Вычислить позицию для новой задачи
            task_width = 100
            task_height = 80
            
            # Расстояние между элементами
            distance_from_source = 120  # минимальное расстояние от источника
            distance_to_target = 120   # минимальное расстояние до цели
            
            # Вычисляем позицию с учетом минимальных расстояний
            if source_coords[0] + distance_from_source + task_width + distance_to_target <= target_coords[0]:
                # Есть достаточно места между источником и целью
                task_x = source_coords[0] + distance_from_source
                task_y = (source_coords[1] + target_coords[1]) // 2 - task_height // 2
            else:
                # Недостаточно места, размещаем в середине с минимальным расстоянием
                available_space = target_coords[0] - source_coords[0]
                if available_space > task_width + 40:  # минимальный зазор 20 пикселей с каждой стороны
                    task_x = source_coords[0] + (available_space - task_width) // 2
                else:
                    # Совсем мало места, размещаем сразу после источника
                    task_x = source_coords[0] + 20
                task_y = (source_coords[1] + target_coords[1]) // 2 - task_height // 2
            
            # Проверяем, что координаты разумные
            if task_x < 0:
                task_x = 50
            if task_y < 0:
                task_y = 50
            
            print(f"         📐 Позиционирование задачи: x={task_x}, y={task_y} (размер: {task_width}x{task_height})")
            print(f"         📏 Расстояния: от источника={task_x - source_coords[0]}, до цели={target_coords[0] - (task_x + task_width)}")
            
            # Создать BPMNShape для новой задачи
            task_shape = ET.SubElement(bpmn_plane, f'{{{self.namespaces["bpmndi"]}}}BPMNShape')
            task_shape.set('id', f'{new_task_id}_di')
            task_shape.set('bpmnElement', new_task_id)
            
            task_bounds = ET.SubElement(task_shape, f'{{{self.namespaces["dc"]}}}Bounds')
            task_bounds.set('x', str(task_x))
            task_bounds.set('y', str(task_y))
            task_bounds.set('width', str(task_width))
            task_bounds.set('height', str(task_height))
            
            print(f"         ✅ Создан BPMNShape для задачи {new_task_id}")
            
            # Создать BPMNEdge для нового sequenceFlow
            flow_edge = ET.SubElement(bpmn_plane, f'{{{self.namespaces["bpmndi"]}}}BPMNEdge')
            flow_edge.set('id', f'{new_flow_id}_di')
            flow_edge.set('bpmnElement', new_flow_id)
            
            # Waypoints для нового потока (от задачи к целевому Gateway)
            start_waypoint = ET.SubElement(flow_edge, f'{{{self.namespaces["di"]}}}waypoint')
            start_waypoint.set('x', str(task_x + task_width))
            start_waypoint.set('y', str(task_y + task_height // 2))
            
            end_waypoint = ET.SubElement(flow_edge, f'{{{self.namespaces["di"]}}}waypoint')
            end_waypoint.set('x', str(target_coords[0]))
            end_waypoint.set('y', str(target_coords[1]))
            
            print(f"         ✅ Создан BPMNEdge для потока {new_flow_id}")
            
            # Обновить waypoints существующего incoming потока
            self._update_existing_flow_waypoints(root, incoming_flow_id, task_x, task_y, task_height)
            
            print(f"         ✅ Диаграммные элементы созданы успешно")
            
        except Exception as e:
            print(f"         ⚠️ Ошибка при создании диаграммных элементов: {e}")

    def _get_positioning_coordinates_for_task(self, root, incoming_flow_id: str, 
                                           target_gateway_id: str) -> tuple:
        """Получить координаты для позиционирования новой задачи"""
        
        try:
            print(f"         🔍 Анализ координат для incoming_flow_id={incoming_flow_id}, target_gateway_id={target_gateway_id}")
            
            # Найти incoming sequenceFlow для получения координат источника
            incoming_flow = root.find(f'.//bpmn:sequenceFlow[@id="{incoming_flow_id}"]', self.namespaces)
            if incoming_flow is None:
                print(f"         ⚠️ Incoming flow {incoming_flow_id} не найден")
                return None, None
            
            source_ref = incoming_flow.get('sourceRef')
            if not source_ref:
                print(f"         ⚠️ sourceRef не найден для incoming flow {incoming_flow_id}")
                return None, None
            
            print(f"         📍 Источник: {source_ref}")
            
            # Получить координаты источника
            source_shape = root.find(f'.//bpmndi:BPMNShape[@bpmnElement="{source_ref}"]', self.namespaces)
            source_coords = None
            if source_shape is not None:
                bounds = source_shape.find('dc:Bounds', self.namespaces)
                if bounds is not None:
                    source_x = int(bounds.get('x', 0))
                    source_y = int(bounds.get('y', 0))
                    source_width = int(bounds.get('width', 100))
                    source_height = int(bounds.get('height', 80))
                    # Правая сторона источника (точка выхода)
                    source_coords = (source_x + source_width, source_y + source_height // 2)
                    print(f"         📐 Координаты источника: {source_ref} = ({source_x}, {source_y}, {source_width}x{source_height}) → exit=({source_coords[0]}, {source_coords[1]})")
                else:
                    print(f"         ⚠️ Bounds не найден для источника {source_ref}")
            else:
                print(f"         ⚠️ Shape не найден для источника {source_ref}")
            
            # Получить координаты целевого Gateway
            target_shape = root.find(f'.//bpmndi:BPMNShape[@bpmnElement="{target_gateway_id}"]', self.namespaces)
            target_coords = None
            if target_shape is not None:
                bounds = target_shape.find('dc:Bounds', self.namespaces)
                if bounds is not None:
                    target_x = int(bounds.get('x', 0))
                    target_y = int(bounds.get('y', 0))
                    target_width = int(bounds.get('width', 50))
                    target_height = int(bounds.get('height', 50))
                    # Левая сторона цели (точка входа)
                    target_coords = (target_x, target_y + target_height // 2)
                    print(f"         📐 Координаты цели: {target_gateway_id} = ({target_x}, {target_y}, {target_width}x{target_height}) → entry=({target_coords[0]}, {target_coords[1]})")
                else:
                    print(f"         ⚠️ Bounds не найден для цели {target_gateway_id}")
            else:
                print(f"         ⚠️ Shape не найден для цели {target_gateway_id}")
            
            # Проверяем разумность координат
            if source_coords and target_coords:
                # Убеждаемся, что координаты в разумных пределах
                if (abs(source_coords[0]) > 10000 or abs(source_coords[1]) > 10000 or 
                    abs(target_coords[0]) > 10000 or abs(target_coords[1]) > 10000):
                    print(f"         ⚠️ Координаты вне разумных пределов, используем значения по умолчанию")
                    # Используем разумные значения по умолчанию
                    source_coords = (1000, 500)
                    target_coords = (1200, 500)
            
            print(f"         ✅ Итоговые координаты: source={source_coords}, target={target_coords}")
            return source_coords, target_coords
            
        except Exception as e:
            print(f"         ⚠️ Ошибка при получении координат: {e}")
            return None, None

    def _update_existing_flow_waypoints(self, root, flow_id: str, 
                                       task_x: int, task_y: int, task_height: int) -> None:
        """Обновить waypoints существующего потока для подключения к новой задаче"""
        
        try:
            # Найти диаграммный элемент потока
            flow_edge = root.find(f'.//bpmndi:BPMNEdge[@bpmnElement="{flow_id}"]', self.namespaces)
            if flow_edge is None:
                print(f"         ⚠️ BPMNEdge для потока {flow_id} не найден")
                return
            
            # Обновить конечный waypoint (теперь он ведет к новой задаче)
            waypoints = flow_edge.findall('di:waypoint', self.namespaces)
            if len(waypoints) >= 2:
                last_waypoint = waypoints[-1]
                last_waypoint.set('x', str(task_x))
                last_waypoint.set('y', str(task_y + task_height // 2))
                print(f"         ✅ Обновлен waypoint для потока {flow_id}")
            
        except Exception as e:
            print(f"         ⚠️ Ошибка при обновлении waypoints: {e}")

    def _generate_unique_activity_id(self, root) -> str:
        """Генерировать уникальный ID для Activity"""
        import random
        import string
        
        existing_ids = set()
        
        # Собрать все существующие ID элементов
        for element in root.findall('.//*[@id]', self.namespaces):
            element_id = element.get('id')
            if element_id:
                existing_ids.add(element_id)
        
        # Генерировать уникальный ID
        while True:
            # Генерируем 7 случайных символов (буквы и цифры)
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            new_id = f"Activity_{random_suffix}"
            
            if new_id not in existing_ids:
                return new_id

    def _generate_unique_flow_id(self, root) -> str:
        """Генерировать уникальный ID для sequenceFlow"""
        import random
        import string
        
        existing_ids = set()
        
        # Собрать все существующие ID элементов
        for element in root.findall('.//*[@id]', self.namespaces):
            element_id = element.get('id')
            if element_id:
                existing_ids.add(element_id)
        
        # Генерировать уникальный ID
        while True:
            # Генерируем 7 случайных символов (буквы и цифры)
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            new_id = f"Flow_{random_suffix}"
            
            if new_id not in existing_ids:
                return new_id
            
    def _assign_responsible_to_unassigned_tasks(self, root):
        """
        Назначить ответственных для всех Activity без назначенных ответственных
        (перенесено из расширения Process_1d4oa6g46)
        """
        print("🔧 Назначение ответственных для задач без назначенных ответственных...")
        
        # Данные ответственного по умолчанию (руководитель проекта)
        DEFAULT_ASSIGNEE_NAME = "Рук. отдела разрешительной док-ции"
        DEFAULT_ASSIGNEE_ID = "15297786"
        
        assigned_count = 0
        
        # Найти все serviceTask элементы
        for service_task in root.findall('.//bpmn:serviceTask', self.namespaces):
            task_id = service_task.get('id')
            task_name = service_task.get('name', 'Без имени')
            
            # Проверить, есть ли уже назначенный ответственный
            has_assignee = self._has_assignee_properties(service_task)
            
            if not has_assignee:
                print(f"   🎯 Найдена задача без ответственного: {task_id} ({task_name})")
                
                # Назначить ответственного
                success = self._add_assignee_to_task(service_task, DEFAULT_ASSIGNEE_NAME, DEFAULT_ASSIGNEE_ID)
                
                if success:
                    assigned_count += 1
                    print(f"   ✅ Назначен ответственный для {task_id}: {DEFAULT_ASSIGNEE_NAME}")
                else:
                    print(f"   ❌ Ошибка при назначении ответственного для {task_id}")
            else:
                print(f"   ℹ️ Задача {task_id} уже имеет назначенного ответственного, пропускаем")
        
        if assigned_count > 0:
            print(f"✅ Назначено ответственных: {assigned_count}")
        else:
            print("✅ Все Activity уже имеют назначенных ответственных")

    def _has_assignee_properties(self, service_task) -> bool:
        """
        Проверить, есть ли у serviceTask назначенный ответственный
        
        Args:
            service_task: Элемент serviceTask
        
        Returns:
            bool: True если ответственный назначен
        """
        try:
            # Найти extensionElements
            extension_elements = service_task.find('bpmn:extensionElements', self.namespaces)
            if extension_elements is None:
                return False
            
            # Найти camunda:properties
            properties = extension_elements.find('camunda:properties', self.namespaces)
            if properties is None:
                return False
            
            # Проверить наличие свойства assigneeId
            for prop in properties.findall('camunda:property', self.namespaces):
                if prop.get('name') == 'assigneeId':
                    return True
            
            return False
            
        except Exception as e:
            print(f"      ⚠️ Ошибка при проверке ответственного: {e}")
            return False

    def _add_assignee_to_task(self, service_task, assignee_name: str, assignee_id: str) -> bool:
        """
        Добавить ответственного к serviceTask
        
        Args:
            service_task: Элемент serviceTask
            assignee_name: Имя ответственного
            assignee_id: ID ответственного
        
        Returns:
            bool: True если ответственный успешно добавлен
        """
        try:
            # Найти или создать extensionElements
            extension_elements = service_task.find('bpmn:extensionElements', self.namespaces)
            if extension_elements is None:
                extension_elements = ET.SubElement(
                    service_task, 
                    f'{{{self.namespaces["bpmn"]}}}extensionElements'
                )
            
            # Найти или создать camunda:properties
            properties = extension_elements.find('camunda:properties', self.namespaces)
            if properties is None:
                properties = ET.SubElement(
                    extension_elements,
                    f'{{{self.namespaces["camunda"]}}}properties'
                )
            
            # Добавить свойство assigneeName
            assignee_name_prop = ET.SubElement(
                properties,
                f'{{{self.namespaces["camunda"]}}}property'
            )
            assignee_name_prop.set('name', 'assigneeName')
            assignee_name_prop.set('value', assignee_name)
            
            # Добавить свойство assigneeId
            assignee_id_prop = ET.SubElement(
                properties,
                f'{{{self.namespaces["camunda"]}}}property'
            )
            assignee_id_prop.set('name', 'assigneeId')
            assignee_id_prop.set('value', assignee_id)
            
            return True
            
        except Exception as e:
            print(f"      ❌ Ошибка при добавлении ответственного: {e}")
            return False


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