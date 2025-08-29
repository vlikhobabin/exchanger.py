#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расширение для процесса: Process_1d4oa6g46
Название: Разработка и получение разрешительной документации

Этот модуль содержит кастомную логику обработки BPMN схемы
для конкретного процесса, выполняемую до и после стандартных преобразований.
"""

import xml.etree.ElementTree as ET
from typing import Optional, Any


def pre_process(root: ET.Element, converter) -> None:
    """
    Предобработка схемы процесса (выполняется ДО стандартных преобразований)
    
    Args:
        root: Корневой элемент BPMN XML
        converter: Экземпляр BPMNConverter для доступа к методам и namespaces
    
    Автоматическая вставка промежуточных задач между шлюзами для разрыва цепочек Gateway → Gateway
    """
    print("🔧 [EXTENSION] Предобработка процесса Process_1d4oa6g46...")
    
    # Поиск всех sequenceFlow с name="да" и вставка промежуточных задач
    inserted_tasks = _insert_intermediate_tasks_for_yes_flows(root, converter)
    
    if inserted_tasks > 0:
        print(f"   ✅ Предобработка завершена (вставлено промежуточных задач: {inserted_tasks})")
    else:
        print("   ✅ Предобработка завершена (изменения не требуются)")


def _insert_intermediate_tasks_for_yes_flows(root: ET.Element, converter) -> int:
    """
    Найти все sequenceFlow с name="да" и вставить промежуточные задачи между шлюзами
    
    Returns:
        int: Количество вставленных задач
    """
    print("   🔍 Поиск sequenceFlow с name='да' для вставки промежуточных задач...")
    
    inserted_count = 0
    
    # Найти все sequenceFlow с name="да"
    yes_flows = []
    for flow in root.findall('.//bpmn:sequenceFlow', converter.namespaces):
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
        source_gateway = _find_gateway_by_id(root, source_ref, converter.namespaces)
        if not source_gateway:
            print(f"      ⚠️ Gateway {source_ref} не найден")
            continue
        
        print(f"      ✅ Gateway {source_ref} найден: {source_gateway.tag}")
        
        # Получить incoming flows этого Gateway
        incoming_flows = source_gateway.findall('bpmn:incoming', converter.namespaces)
        print(f"      📊 Найдено incoming потоков для {source_ref}: {len(incoming_flows)}")
        
        for i, incoming_element in enumerate(incoming_flows):
            incoming_flow_id = incoming_element.text
            print(f"      🔗 Анализируем incoming поток #{i+1}: {incoming_flow_id}")
            
            # Найти incoming sequenceFlow
            incoming_flow = root.find(f'.//bpmn:sequenceFlow[@id="{incoming_flow_id}"]', converter.namespaces)
            
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
                task_inserted = _insert_task_between_gateways(
                    root, converter, incoming_flow, source_gateway, source_ref
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


def _find_gateway_by_id(root: ET.Element, gateway_id: str, namespaces: dict) -> Optional[ET.Element]:
    """Найти Gateway по ID"""
    for gateway_type in ['exclusiveGateway', 'inclusiveGateway', 'parallelGateway']:
        gateway = root.find(f'.//bpmn:{gateway_type}[@id="{gateway_id}"]', namespaces)
        if gateway is not None:
            return gateway
    return None


def _insert_task_between_gateways(root: ET.Element, converter, incoming_flow: ET.Element, 
                                 target_gateway: ET.Element, target_gateway_id: str) -> bool:
    """
    Вставить промежуточную задачу между двумя Gateway
    
    Args:
        root: Корневой элемент BPMN XML
        converter: Экземпляр BPMNConverter 
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
        new_task_id = _generate_unique_activity_id(root, converter.namespaces)
        new_flow_id = _generate_unique_flow_id(root, converter.namespaces)
        print(f"         🆔 Сгенерированы ID: task={new_task_id}, flow={new_flow_id}")
        
        # Получить name целевого Gateway для формирования имени задачи
        gateway_name = target_gateway.get('name', 'условие')
        task_name = f"Выяснить: {gateway_name}"
        
        print(f"         📝 Создание задачи {new_task_id}: '{task_name}'")
        
        # Найти элемент process для вставки новой задачи
        process_element = root.find('.//bpmn:process', converter.namespaces)
        if not process_element:
            print(f"         ❌ Элемент process не найден")
            return False
        
        print(f"         ✅ Process элемент найден")
        
        # Создать новую задачу
        new_task = ET.SubElement(process_element, f'{{{converter.namespaces["bpmn"]}}}task')
        new_task.set('id', new_task_id)
        new_task.set('name', task_name)
        print(f"         ✅ Создан элемент task: {new_task_id}")
        
        # Добавить incoming для новой задачи (из исходного потока)
        task_incoming = ET.SubElement(new_task, f'{{{converter.namespaces["bpmn"]}}}incoming')
        task_incoming.text = incoming_flow_id
        print(f"         ✅ Добавлен incoming: {incoming_flow_id}")
        
        # Добавить outgoing для новой задачи (новый поток к целевому Gateway)
        task_outgoing = ET.SubElement(new_task, f'{{{converter.namespaces["bpmn"]}}}outgoing')
        task_outgoing.text = new_flow_id
        print(f"         ✅ Добавлен outgoing: {new_flow_id}")
        
        # Создать новый sequenceFlow от задачи к целевому Gateway
        new_sequence_flow = ET.SubElement(process_element, f'{{{converter.namespaces["bpmn"]}}}sequenceFlow')
        new_sequence_flow.set('id', new_flow_id)
        new_sequence_flow.set('sourceRef', new_task_id)
        new_sequence_flow.set('targetRef', target_gateway_id)
        print(f"         ✅ Создан новый sequenceFlow: {new_flow_id} ({new_task_id} → {target_gateway_id})")
        
        # Обновить исходный incoming_flow: теперь он ведет к новой задаче
        old_target = incoming_flow.get('targetRef')
        incoming_flow.set('targetRef', new_task_id)
        print(f"         ✅ Обновлен incoming_flow {incoming_flow_id}: {old_target} → {new_task_id}")
        
        # Обновить incoming потоки целевого Gateway
        _update_gateway_incoming_flows(target_gateway, incoming_flow_id, new_flow_id, converter.namespaces)
        print(f"         ✅ Обновлены incoming потоки Gateway {target_gateway_id}")
        
        # Создать диаграммные элементы для новых объектов
        _create_diagram_elements(root, converter, new_task_id, new_flow_id, target_gateway_id, incoming_flow_id)
        
        print(f"         🎉 Задача {new_task_id} успешно вставлена")
        print(f"         📎 Итоговая цепочка: ...→{new_task_id}→{target_gateway_id}")
        
        return True
        
    except Exception as e:
        print(f"         ❌ Ошибка при вставке задачи: {e}")
        import traceback
        print(f"         🔍 Детали ошибки:")
        traceback.print_exc(limit=2)
        return False


def _update_gateway_incoming_flows(gateway: ET.Element, old_flow_id: str, 
                                  new_flow_id: str, namespaces: dict) -> None:
    """Обновить incoming потоки Gateway"""
    
    # Найти и обновить соответствующий incoming элемент
    for incoming in gateway.findall('bpmn:incoming', namespaces):
        if incoming.text == old_flow_id:
            incoming.text = new_flow_id
            break


def _generate_unique_activity_id(root: ET.Element, namespaces: dict) -> str:
    """Генерировать уникальный ID для Activity"""
    import random
    import string
    
    existing_ids = set()
    
    # Собрать все существующие ID элементов
    for element in root.findall('.//*[@id]', namespaces):
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


def _generate_unique_flow_id(root: ET.Element, namespaces: dict) -> str:
    """Генерировать уникальный ID для sequenceFlow"""
    import random
    import string
    
    existing_ids = set()
    
    # Собрать все существующие ID элементов
    for element in root.findall('.//*[@id]', namespaces):
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


def _create_diagram_elements(root: ET.Element, converter, new_task_id: str, new_flow_id: str, 
                           target_gateway_id: str, incoming_flow_id: str) -> None:
    """Создать диаграммные элементы для новой задачи и потока"""
    
    try:
        # Найти BPMNDiagram
        bpmn_diagram = root.find('.//bpmndi:BPMNDiagram', converter.namespaces)
        if bpmn_diagram is None:
            print(f"         ⚠️ BPMNDiagram не найден, пропускаем создание диаграммных элементов")
            return
        
        bpmn_plane = bpmn_diagram.find('.//bpmndi:BPMNPlane', converter.namespaces)
        if bpmn_plane is None:
            print(f"         ⚠️ BPMNPlane не найден, пропускаем создание диаграммных элементов")
            return
        
        # Получить координаты существующих элементов для позиционирования
        source_coords, target_coords = _get_positioning_coordinates(
            root, converter, incoming_flow_id, target_gateway_id
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
        task_shape = ET.SubElement(bpmn_plane, f'{{{converter.namespaces["bpmndi"]}}}BPMNShape')
        task_shape.set('id', f'{new_task_id}_di')
        task_shape.set('bpmnElement', new_task_id)
        
        task_bounds = ET.SubElement(task_shape, f'{{{converter.namespaces["dc"]}}}Bounds')
        task_bounds.set('x', str(task_x))
        task_bounds.set('y', str(task_y))
        task_bounds.set('width', str(task_width))
        task_bounds.set('height', str(task_height))
        
        print(f"         ✅ Создан BPMNShape для задачи {new_task_id}")
        
        # Создать BPMNEdge для нового sequenceFlow
        flow_edge = ET.SubElement(bpmn_plane, f'{{{converter.namespaces["bpmndi"]}}}BPMNEdge')
        flow_edge.set('id', f'{new_flow_id}_di')
        flow_edge.set('bpmnElement', new_flow_id)
        
        # Waypoints для нового потока (от задачи к целевому Gateway)
        start_waypoint = ET.SubElement(flow_edge, f'{{{converter.namespaces["di"]}}}waypoint')
        start_waypoint.set('x', str(task_x + task_width))
        start_waypoint.set('y', str(task_y + task_height // 2))
        
        end_waypoint = ET.SubElement(flow_edge, f'{{{converter.namespaces["di"]}}}waypoint')
        end_waypoint.set('x', str(target_coords[0]))
        end_waypoint.set('y', str(target_coords[1]))
        
        print(f"         ✅ Создан BPMNEdge для потока {new_flow_id}")
        
        # Обновить waypoints существующего incoming потока
        _update_existing_flow_waypoints(root, converter, incoming_flow_id, task_x, task_y, task_height)
        
        print(f"         ✅ Диаграммные элементы созданы успешно")
        
    except Exception as e:
        print(f"         ⚠️ Ошибка при создании диаграммных элементов: {e}")


def _get_positioning_coordinates(root: ET.Element, converter, incoming_flow_id: str, 
                               target_gateway_id: str) -> tuple:
    """Получить координаты для позиционирования новой задачи"""
    
    try:
        print(f"         🔍 Анализ координат для incoming_flow_id={incoming_flow_id}, target_gateway_id={target_gateway_id}")
        
        # Найти incoming sequenceFlow для получения координат источника
        incoming_flow = root.find(f'.//bpmn:sequenceFlow[@id="{incoming_flow_id}"]', converter.namespaces)
        if incoming_flow is None:
            print(f"         ⚠️ Incoming flow {incoming_flow_id} не найден")
            return None, None
        
        source_ref = incoming_flow.get('sourceRef')
        if not source_ref:
            print(f"         ⚠️ sourceRef не найден для incoming flow {incoming_flow_id}")
            return None, None
        
        print(f"         📍 Источник: {source_ref}")
        
        # Получить координаты источника
        source_shape = root.find(f'.//bpmndi:BPMNShape[@bpmnElement="{source_ref}"]', converter.namespaces)
        source_coords = None
        if source_shape is not None:
            bounds = source_shape.find('dc:Bounds', converter.namespaces)
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
        target_shape = root.find(f'.//bpmndi:BPMNShape[@bpmnElement="{target_gateway_id}"]', converter.namespaces)
        target_coords = None
        if target_shape is not None:
            bounds = target_shape.find('dc:Bounds', converter.namespaces)
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


def _update_existing_flow_waypoints(root: ET.Element, converter, flow_id: str, 
                                   task_x: int, task_y: int, task_height: int) -> None:
    """Обновить waypoints существующего потока для подключения к новой задаче"""
    
    try:
        # Найти диаграммный элемент потока
        flow_edge = root.find(f'.//bpmndi:BPMNEdge[@bpmnElement="{flow_id}"]', converter.namespaces)
        if flow_edge is None:
            print(f"         ⚠️ BPMNEdge для потока {flow_id} не найден")
            return
        
        # Обновить конечный waypoint (теперь он ведет к новой задаче)
        waypoints = flow_edge.findall('di:waypoint', converter.namespaces)
        if len(waypoints) >= 2:
            last_waypoint = waypoints[-1]
            last_waypoint.set('x', str(task_x))
            last_waypoint.set('y', str(task_y + task_height // 2))
            print(f"         ✅ Обновлен waypoint для потока {flow_id}")
        
    except Exception as e:
        print(f"         ⚠️ Ошибка при обновлении waypoints: {e}")


def post_process(root: ET.Element, converter) -> None:
    """
    Постобработка схемы процесса (выполняется ПОСЛЕ стандартных преобразований)
    
    Args:
        root: Корневой элемент BPMN XML (уже обработанный стандартными алгоритмами)
        converter: Экземпляр BPMNConverter для доступа к методам и namespaces
    
    Примеры возможных операций:
    - Финальная настройка уже сконвертированных элементов
    - Добавление процесс-специфичных конфигураций
    - Корректировка результатов стандартных преобразований
    - Добавление дополнительных условий или properties
    """
    print("🔧 [EXTENSION] Постобработка процесса Process_1d4oa6g46...")
    
    # Назначение ответственных для Activity без назначенных ответственных
    assigned_count = _assign_responsible_to_unassigned_tasks(root, converter)
    
    # Кастомная установка conditionExpression для специфичных потоков с переменной demolition
    # временно отключено, т.к. теперь у нас есть созданный Activity для выяснения, нужно ли сносить
    # updated_count = _add_custom_demolition_conditions(root, converter)
    updated_count = 0  # временно установлено в 0, т.к. кастомные условия отключены
    
    total_changes = assigned_count + updated_count
    if total_changes > 0:
        print(f"   ✅ Постобработка завершена (назначено ответственных: {assigned_count}, обновлено потоков: {updated_count})")
    else:
        print("   ✅ Постобработка завершена (изменения не требуются)")


def _add_custom_demolition_conditions(root: ET.Element, converter) -> int:
    """
    Добавить кастомные условные выражения с переменной demolition для конкретных потоков
    
    Returns:
        int: Количество обновленных потоков
    """
    
    # Список конкретных потоков для обновления
    target_flows = {
        'Flow_1i3yird': {'name': 'да (требуется снос)', 'condition': '${demolition == "yes"}'},
        'Flow_1ykzunp': {'name': 'нет (снос не требуется)', 'condition': '${demolition == "no"}'}
    }
    
    updated_count = 0
    
    for flow_id, flow_config in target_flows.items():
        # Найти поток по ID
        flow = root.find(f'.//bpmn:sequenceFlow[@id="{flow_id}"]', converter.namespaces)
        
        if flow is not None:
            # Проверить, нет ли уже conditionExpression
            existing_condition = flow.find('bpmn:conditionExpression', converter.namespaces)
            
            if existing_condition is None:
                # Создать новый элемент conditionExpression
                condition_element = ET.SubElement(
                    flow, 
                    f'{{{converter.namespaces["bpmn"]}}}conditionExpression'
                )
                condition_element.set(
                    f'{{{converter.namespaces["xsi"]}}}type',
                    'bpmn:tFormalExpression'
                )
                condition_element.text = flow_config['condition']
                
                print(f"   ✅ Добавлено условие для {flow_id} ({flow_config['name']}): {flow_config['condition']}")
                updated_count += 1
            else:
                print(f"   ⚠️ Поток {flow_id} уже имеет условное выражение, пропускаем")
        else:
            print(f"   ⚠️ Поток {flow_id} не найден в схеме")
    
    return updated_count


def _assign_responsible_to_unassigned_tasks(root: ET.Element, converter) -> int:
    """
    Назначить ответственных для всех Activity без назначенных ответственных
    
    Args:
        root: Корневой элемент BPMN XML
        converter: Экземпляр BPMNConverter для доступа к namespaces
    
    Returns:
        int: Количество Activity с назначенными ответственными
    """
    print("   🔍 Поиск Activity без назначенных ответственных...")
    
    # Данные ответственного по умолчанию (руководитель проекта)
    DEFAULT_ASSIGNEE_NAME = "Рук. отдела разрешительной док-ции"
    DEFAULT_ASSIGNEE_ID = "15297786"
    
    assigned_count = 0
    
    # Найти все serviceTask элементы
    for service_task in root.findall('.//bpmn:serviceTask', converter.namespaces):
        task_id = service_task.get('id')
        task_name = service_task.get('name', 'Без имени')
        
        # Проверить, есть ли уже назначенный ответственный
        has_assignee = _has_assignee_properties(service_task, converter.namespaces)
        
        if not has_assignee:
            print(f"      🎯 Найдена задача без ответственного: {task_id} ({task_name})")
            
            # Назначить ответственного
            success = _add_assignee_to_task(service_task, DEFAULT_ASSIGNEE_NAME, DEFAULT_ASSIGNEE_ID, converter.namespaces)
            
            if success:
                assigned_count += 1
                print(f"      ✅ Назначен ответственный для {task_id}: {DEFAULT_ASSIGNEE_NAME}")
            else:
                print(f"      ❌ Ошибка при назначении ответственного для {task_id}")
        else:
            print(f"      ℹ️ Задача {task_id} уже имеет назначенного ответственного, пропускаем")
    
    if assigned_count > 0:
        print(f"   📊 Итого назначено ответственных: {assigned_count}")
    else:
        print("   📊 Все Activity уже имеют назначенных ответственных")
    
    return assigned_count


def _has_assignee_properties(service_task: ET.Element, namespaces: dict) -> bool:
    """
    Проверить, есть ли у serviceTask назначенный ответственный
    
    Args:
        service_task: Элемент serviceTask
        namespaces: Словарь пространств имен
    
    Returns:
        bool: True если ответственный назначен
    """
    try:
        # Найти extensionElements
        extension_elements = service_task.find('bpmn:extensionElements', namespaces)
        if extension_elements is None:
            return False
        
        # Найти camunda:properties
        properties = extension_elements.find('camunda:properties', namespaces)
        if properties is None:
            return False
        
        # Проверить наличие свойства assigneeId
        for prop in properties.findall('camunda:property', namespaces):
            if prop.get('name') == 'assigneeId':
                return True
        
        return False
        
    except Exception as e:
        print(f"         ⚠️ Ошибка при проверке ответственного: {e}")
        return False


def _add_assignee_to_task(service_task: ET.Element, assignee_name: str, assignee_id: str, namespaces: dict) -> bool:
    """
    Добавить ответственного к serviceTask
    
    Args:
        service_task: Элемент serviceTask
        assignee_name: Имя ответственного
        assignee_id: ID ответственного
        namespaces: Словарь пространств имен
    
    Returns:
        bool: True если ответственный успешно добавлен
    """
    try:
        # Найти или создать extensionElements
        extension_elements = service_task.find('bpmn:extensionElements', namespaces)
        if extension_elements is None:
            extension_elements = ET.SubElement(
                service_task, 
                f'{{{namespaces["bpmn"]}}}extensionElements'
            )
        
        # Найти или создать camunda:properties
        properties = extension_elements.find('camunda:properties', namespaces)
        if properties is None:
            properties = ET.SubElement(
                extension_elements,
                f'{{{namespaces["camunda"]}}}properties'
            )
        
        # Добавить свойство assigneeName
        assignee_name_prop = ET.SubElement(
            properties,
            f'{{{namespaces["camunda"]}}}property'
        )
        assignee_name_prop.set('name', 'assigneeName')
        assignee_name_prop.set('value', assignee_name)
        
        # Добавить свойство assigneeId
        assignee_id_prop = ET.SubElement(
            properties,
            f'{{{namespaces["camunda"]}}}property'
        )
        assignee_id_prop.set('name', 'assigneeId')
        assignee_id_prop.set('value', assignee_id)
        
        return True
        
    except Exception as e:
        print(f"         ❌ Ошибка при добавлении ответственного: {e}")
        return False


# Метаданные расширения
EXTENSION_INFO = {
    'process_name': 'Разработка и получение разрешительной документации',
    'version': '1.6.0',
    'description': 'Кастомные преобразования для процесса разрешительной документации: автоматическая вставка промежуточных задач между шлюзами и настройка условных выражений.'
} 