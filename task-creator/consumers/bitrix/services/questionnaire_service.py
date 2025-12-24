"""
Сервис для работы с анкетами задач Bitrix24

Модуль содержит класс QuestionnaireService для управления анкетами:
извлечение из шаблонов, форматирование ответов, добавление к задачам.
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from loguru import logger

from ..clients import BitrixAPIClient


class QuestionnaireService:
    """
    Сервис для работы с анкетами задач Bitrix24

    Предоставляет методы для извлечения анкет из шаблонов,
    форматирования ответов и добавления анкет к задачам.
    """

    def __init__(self, bitrix_client: BitrixAPIClient, config: Any, stats: Dict[str, int]):
        """
        Инициализация сервиса анкет

        Args:
            bitrix_client: Клиент API Bitrix24
            config: Конфигурация (webhook_url, request_timeout)
            stats: Словарь статистики для обновления счётчиков
        """
        self.bitrix_client = bitrix_client
        self.config = config
        self.stats = stats

    def extract_from_template(self, template_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлечение анкет из шаблона задачи (questionnaires.items)

        Args:
            template_data: Данные шаблона от API

        Returns:
            Список анкет
        """
        if not template_data:
            return []

        questionnaires_section = template_data.get('questionnaires') or {}
        if not isinstance(questionnaires_section, dict):
            logger.debug("Секция questionnaires имеет некорректный формат (ожидался dict)")
            return []

        # Логируем вспомогательные поля v2.3 (total, has_codes), если они присутствуют
        total = questionnaires_section.get('total')
        has_codes = questionnaires_section.get('has_codes')
        if isinstance(total, int):
            logger.debug(f"questionnaires.total из шаблона: {total}")
        if isinstance(has_codes, bool):
            logger.debug(f"questionnaires.has_codes: {has_codes}")

        items = questionnaires_section.get('items')
        if not items:
            logger.debug("Секция questionnaires отсутствует или items пустой")
            return []

        if not isinstance(items, list):
            logger.debug("questionnaires.items имеет некорректный формат (ожидался list)")
            return []

        # Лёгкая валидация: CODE у анкеты и вопросов — обязательный в v2.3, но не модифицируем данные
        missing_questionnaire_codes = sum(1 for q in items if isinstance(q, dict) and not q.get('CODE'))
        missing_question_codes = 0
        for q in items:
            if not isinstance(q, dict):
                continue
            questions = q.get('questions') or []
            if isinstance(questions, list):
                missing_question_codes += sum(1 for question in questions if isinstance(question, dict) and not question.get('CODE'))
        if missing_questionnaire_codes or missing_question_codes:
            logger.warning(
                f"Анкеты из шаблона содержат пустые CODE: анкеты={missing_questionnaire_codes}, вопросы={missing_question_codes}"
            )

        self.stats["questionnaires_found"] += len(items)
        logger.debug(f"Извлечено {len(items)} анкет из шаблона")
        return items

    def extract_for_description(self, template_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлечение анкет для вставки в описание задачи (questionnairesInDescription.items)

        Args:
            template_data: Данные шаблона от API imena.camunda.tasktemplate.get

        Returns:
            Список анкет с вопросами для вставки в описание
        """
        if not template_data:
            return []

        qid_section = template_data.get('questionnairesInDescription') or {}
        if not isinstance(qid_section, dict):
            logger.debug("Секция questionnairesInDescription имеет некорректный формат (ожидался dict)")
            return []

        total = qid_section.get('total', 0)
        if not total:
            logger.debug("questionnairesInDescription.total = 0, анкеты для описания отсутствуют")
            return []

        items = qid_section.get('items')
        if not items:
            logger.debug("questionnairesInDescription.items пустой или отсутствует")
            return []

        if not isinstance(items, list):
            logger.debug("questionnairesInDescription.items имеет некорректный формат (ожидался list)")
            return []

        logger.debug(f"Извлечено {len(items)} анкет для вставки в описание задачи")
        return items

    def add_to_task(self, task_id: int, questionnaires: List[Dict[str, Any]]) -> bool:
        """
        Добавление анкет к созданной задаче через кастомный REST API Bitrix24

        Args:
            task_id: ID задачи в Bitrix24
            questionnaires: Список анкет для добавления

        Returns:
            True если анкеты добавлены успешно
        """
        if not questionnaires:
            logger.debug("Нет анкет для добавления в задачу")
            return True

        api_url = f"{self.config.webhook_url.rstrip('/')}/imena.camunda.task.questionnaire.add"

        # Краткий лог: сколько анкет и их коды (если есть)
        sample_codes = []
        for q in questionnaires:
            if isinstance(q, dict) and 'CODE' in q:
                sample_codes.append(q.get('CODE'))
                if len(sample_codes) >= 5:
                    break
        logger.debug(
            f"Подготовка к добавлению анкет в задачу {task_id}: всего={len(questionnaires)}, пример CODE={sample_codes}"
        )

        payload = {
            "taskId": task_id,
            "questionnaires": questionnaires
        }

        try:
            response = requests.post(
                api_url,
                json=payload,
                timeout=self.config.request_timeout,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            result = response.json()

            api_result = result.get('result', {})
            if api_result.get('success'):
                created_ids = api_result.get('data', {}).get('createdIds', [])
                created_count = api_result.get('data', {}).get('totalCreated')
                if created_count is None:
                    created_count = len(created_ids) if created_ids else len(questionnaires)
                self.stats["questionnaires_sent"] += int(created_count)
                logger.debug(f"Анкеты добавлены в задачу {task_id}: created_count={created_count}")
                return True

            error_msg = api_result.get('error', 'Unknown error')
            self.stats["questionnaires_failed"] += 1
            logger.warning(f"Bitrix24 вернул ошибку при добавлении анкет в задачу {task_id}: {error_msg}")
            logger.debug(f"Полный ответ API анкет: {json.dumps(api_result, ensure_ascii=False)}")
            return False

        except requests.exceptions.Timeout:
            self.stats["questionnaires_failed"] += 1
            logger.error(f"Таймаут при добавлении анкет к задаче {task_id} (timeout={self.config.request_timeout}s)")
            return False
        except requests.exceptions.RequestException as e:
            self.stats["questionnaires_failed"] += 1
            logger.error(f"Ошибка запроса при добавлении анкет к задаче {task_id}: {e}")
            try:
                if getattr(e, "response", None) is not None and e.response is not None:
                    logger.error(f"Тело ответа Bitrix24 при ошибке анкет: {e.response.text}")
            except Exception:
                pass
            return False
        except json.JSONDecodeError as e:
            self.stats["questionnaires_failed"] += 1
            logger.error(f"Ошибка декодирования ответа при добавлении анкет к задаче {task_id}: {e}")
            return False
        except Exception as e:
            self.stats["questionnaires_failed"] += 1
            logger.error(f"Неожиданная ошибка при добавлении анкет к задаче {task_id}: {e}")
            return False

    def get_user_name_by_id(self, user_id: int) -> Optional[str]:
        """
        Получение имени пользователя Bitrix24 по ID через REST API user.get

        Args:
            user_id: ID пользователя Bitrix24

        Returns:
            Имя пользователя (Фамилия Имя) или None при ошибке
        """
        if not user_id or user_id <= 0:
            return None

        try:
            api_url = f"{self.config.webhook_url.rstrip('/')}/user.get"
            params = {'ID': user_id}

            response = requests.get(api_url, params=params, timeout=self.config.request_timeout)
            response.raise_for_status()
            data = response.json()

            result = data.get('result')
            if result and isinstance(result, list) and len(result) > 0:
                user = result[0]
                last_name = user.get('LAST_NAME', '')
                first_name = user.get('NAME', '')
                full_name = f"{last_name} {first_name}".strip()
                if full_name:
                    return full_name
                # Fallback на email или логин
                return user.get('EMAIL') or user.get('LOGIN') or str(user_id)

            logger.debug(f"Пользователь с ID={user_id} не найден в Bitrix24")
            return None

        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка запроса user.get для user_id={user_id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Неожиданная ошибка при получении имени пользователя {user_id}: {e}")
            return None

    def format_answer(self, question: Dict[str, Any], raw_value: Any) -> str:
        """
        Форматирование ответа на вопрос анкеты в человекочитаемый вид

        Args:
            question: Данные вопроса (CODE, NAME, TYPE, ENUM_OPTIONS и т.д.)
            raw_value: Сырое значение из переменных процесса

        Returns:
            Отформатированное значение для отображения
        """
        if raw_value is None:
            return "-"

        # Извлекаем value из Camunda формата {"value": ..., "type": ...}
        value = raw_value
        if isinstance(raw_value, dict):
            value = raw_value.get('value', raw_value.get('VALUE', raw_value))

        if value is None or value == '':
            return "-"

        question_type = (question.get('TYPE') or '').lower()

        # Boolean: true → Да, false → Нет
        if question_type == 'boolean':
            if isinstance(value, bool):
                return "Да" if value else "Нет"
            if isinstance(value, str):
                return "Да" if value.lower() in ('true', '1', 'yes', 'да') else "Нет"
            if isinstance(value, (int, float)):
                return "Да" if value != 0 else "Нет"
            return "-"

        # Date: ISO → DD.MM.YYYY
        if question_type == 'date':
            if isinstance(value, str):
                try:
                    # Попытка распарсить ISO формат
                    normalized = value.strip().replace('Z', '+00:00')
                    if 'T' in normalized:
                        dt = datetime.fromisoformat(normalized.split('T')[0])
                    else:
                        dt = datetime.fromisoformat(normalized)
                    return dt.strftime("%d.%m.%Y")
                except ValueError:
                    try:
                        dt = datetime.strptime(value.strip()[:10], "%Y-%m-%d")
                        return dt.strftime("%d.%m.%Y")
                    except ValueError:
                        return str(value)
            return str(value)

        # User: ID → Имя пользователя
        if question_type == 'user':
            try:
                user_id = int(value)
                user_name = self.get_user_name_by_id(user_id)
                return user_name if user_name else str(user_id)
            except (TypeError, ValueError):
                return str(value)

        # Universal list: ID → Название элемента
        if question_type == 'universal_list':
            try:
                element_id = int(value)
                # Получаем iblock_id из ENUM_OPTIONS или _iblockId
                iblock_id = None
                enum_options = question.get('ENUM_OPTIONS')
                if isinstance(enum_options, dict):
                    iblock_id = enum_options.get('iblock_id')
                if not iblock_id:
                    iblock_id = question.get('_iblockId')

                if iblock_id:
                    element_name = self.bitrix_client.get_list_element_name(int(iblock_id), element_id)
                    return element_name if element_name else str(element_id)
                return str(element_id)
            except (TypeError, ValueError):
                return str(value)

        # Integer
        if question_type == 'integer':
            try:
                return str(int(value))
            except (TypeError, ValueError):
                return str(value)

        # String, enum и остальные типы
        return str(value)

    def build_description_block(
        self,
        questionnaires: List[Dict[str, Any]],
        process_variables: Dict[str, Any],
        element_id: str
    ) -> Optional[str]:
        """
        Формирование BB-code блока с данными анкет для вставки в описание задачи

        Args:
            questionnaires: Список анкет из questionnairesInDescription.items
            process_variables: Переменные процесса Camunda
            element_id: ID текущего элемента диаграммы (Activity)

        Returns:
            BB-code строка с данными анкет или None если анкет нет
        """
        if not questionnaires:
            return None

        blocks: List[str] = []

        for questionnaire in questionnaires:
            questionnaire_code = questionnaire.get('CODE') or ''
            questionnaire_title = questionnaire.get('TITLE') or questionnaire_code or 'Анкета'
            questions = questionnaire.get('questions') or []

            if not questions:
                continue

            lines: List[str] = []
            # Заголовок анкеты в BB-code (жирный)
            lines.append(f"[B]{questionnaire_title}[/B]")

            for question in questions:
                question_code = question.get('CODE') or ''
                question_name = question.get('NAME') or question_code or 'Вопрос'

                # Ищем переменную по суффиксу _{QUESTIONNAIRE_CODE}_{QUESTION_CODE}
                # Анкеты могут быть заполнены на разных шагах процесса,
                # поэтому element_id в ключе переменной может отличаться от текущего
                var_suffix = f"_{questionnaire_code}_{question_code}"
                raw_value = None
                for var_key, var_val in process_variables.items():
                    if var_key.endswith(var_suffix):
                        raw_value = var_val
                        logger.debug(f"Найдена переменная {var_key} для суффикса {var_suffix}")
                        break

                # Форматируем значение в зависимости от типа
                formatted_value = self.format_answer(question, raw_value)

                # Добавляем строку с вопросом и ответом
                lines.append(f"• {question_name}: {formatted_value}")

            if len(lines) > 1:  # Если есть хотя бы один вопрос кроме заголовка
                blocks.append("\n".join(lines))

        if not blocks:
            return None

        return "\n\n".join(blocks)
