"""
Валидатор полей для Bitrix24

Проверка существования обязательных пользовательских полей
и извлечение UF_ полей из метаданных.
"""
import requests
from typing import Dict, Any, List
from urllib.parse import urlparse
from loguru import logger


class FieldValidator:
    """
    Валидатор обязательных полей Bitrix24

    Проверяет существование и типы пользовательских полей (UF_),
    а также извлекает их из метаданных сообщений.
    """

    # Список обязательных полей с их ожидаемыми типами
    REQUIRED_FIELDS = {
        "UF_CAMUNDA_ID_EXTERNAL_TASK": {
            "type": "string",
            "description": "Уникальный идентификатор External Task из Camunda"
        },
        "UF_RESULT_ANSWER": {
            "type": "enumeration",
            "description": "Ответ пользователя на вопрос задачи"
        },
        "UF_RESULT_QUESTION": {
            "type": "string",
            "description": "Вопрос для задачи, требующей ответа"
        },
        "UF_RESULT_EXPECTED": {
            "type": "boolean",
            "description": "Флаг, требуется ли ответ от пользователя"
        },
        "UF_ELEMENT_ID": {
            "type": "string",
            "description": "ID элемента BPMN диаграммы (activityId)"
        },
        "UF_PROCESS_INSTANCE_ID": {
            "type": "string",
            "description": "ID экземпляра процесса Camunda (для связи задач одного экземпляра)"
        }
    }

    # Маппинг типов для проверки
    TYPE_MAPPING = {
        'string': ['string', 'text'],
        'enumeration': ['enumeration', 'enum'],
        'boolean': ['boolean', 'bool']
    }

    # Поддерживаемые пользовательские поля для извлечения
    SUPPORTED_USER_FIELDS = [
        "UF_RESULT_EXPECTED",
        "UF_RESULT_QUESTION"
    ]

    def __init__(self, config: Any):
        """
        Инициализация валидатора

        Args:
            config: Конфигурация с webhook_url и request_timeout
        """
        self.config = config

    def extract_user_fields(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлечение пользовательских полей UF_ из метаданных

        Args:
            metadata: Метаданные сообщения из RabbitMQ

        Returns:
            Словарь с пользовательскими полями для Bitrix24
        """
        user_fields = {}

        # Получаем extensionProperties из метаданных
        extension_properties = metadata.get("extensionProperties", {})

        # Извлекаем поддерживаемые пользовательские поля
        for field_name in self.SUPPORTED_USER_FIELDS:
            if field_name in extension_properties:
                field_value = extension_properties[field_name]

                # Обработка различных типов значений
                if field_value is not None:
                    # Для поля UF_RESULT_EXPECTED преобразуем строку в булево значение
                    if field_name == "UF_RESULT_EXPECTED":
                        if isinstance(field_value, str):
                            # Битрикс ожидает 'Y' или 'N' для булевых полей
                            user_fields[field_name] = 'Y' if field_value.lower() in ['true', '1', 'да', 'yes'] else 'N'
                        elif isinstance(field_value, bool):
                            user_fields[field_name] = 'Y' if field_value else 'N'
                        else:
                            user_fields[field_name] = 'N'  # По умолчанию

                    # Для текстовых полей передаем как есть
                    elif field_name == "UF_RESULT_QUESTION":
                        if isinstance(field_value, str) and field_value.strip():
                            user_fields[field_name] = field_value.strip()

                    # Для других полей передаем строковое представление
                    else:
                        user_fields[field_name] = str(field_value)

                    logger.debug(f"Извлечено пользовательское поле: {field_name}={user_fields.get(field_name)}")

        if user_fields:
            logger.info(f"Извлечено {len(user_fields)} пользовательских полей: {list(user_fields.keys())}")
        else:
            logger.debug("Пользовательские поля UF_ в метаданных не найдены")

        return user_fields

    def check_required_fields(self) -> None:
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: Проверяет существование всех обязательных пользовательских полей
        для объекта TASKS_TASK в Bitrix24.

        Обязательные поля:
        - UF_CAMUNDA_ID_EXTERNAL_TASK (string) - уникальный идентификатор External Task из Camunda
        - UF_RESULT_ANSWER (enumeration) - ответ пользователя на вопрос задачи
        - UF_RESULT_QUESTION (string) - вопрос для задачи, требующей ответа
        - UF_RESULT_EXPECTED (boolean) - флаг, требуется ли ответ от пользователя
        - UF_ELEMENT_ID (string) - ID элемента BPMN диаграммы
        - UF_PROCESS_INSTANCE_ID (string) - ID экземпляра процесса Camunda

        Если хотя бы одно поле отсутствует - останавливает сервис с фатальной ошибкой.
        Все поля должны быть созданы администратором вручную перед запуском сервиса.

        Raises:
            SystemExit: Если хотя бы одно поле не найдено - останавливает сервис
        """
        try:
            logger.info("Проверка существования обязательных пользовательских полей в Bitrix24...")
            logger.info(f"Ожидаемые поля: {', '.join(self.REQUIRED_FIELDS.keys())}")

            # Получаем список полей из Bitrix24
            user_fields = self._fetch_user_fields()

            if user_fields is None or len(user_fields) == 0:
                self._log_fatal_error_no_fields()
                raise SystemExit(1)

            # Создаем словарь найденных полей для быстрого поиска
            found_fields = self._build_found_fields_dict(user_fields)

            # Проверяем каждое обязательное поле
            missing_fields, incorrect_type_fields = self._validate_fields(found_fields)

            # Если есть отсутствующие поля или поля с неверным типом - останавливаем сервис
            if missing_fields or incorrect_type_fields:
                self._log_fatal_error_missing_fields(missing_fields, incorrect_type_fields)
                raise SystemExit(1)

            logger.info("✅ Все обязательные пользовательские поля найдены и имеют корректные типы")

        except requests.exceptions.RequestException as e:
            self._log_fatal_error_connection(e)
            raise SystemExit(1)
        except SystemExit:
            # Пробрасываем SystemExit дальше
            raise
        except Exception as e:
            self._log_fatal_error_unexpected(e)
            raise SystemExit(1)

    def _fetch_user_fields(self) -> List[Dict[str, Any]]:
        """
        Получение списка пользовательских полей из Bitrix24

        Returns:
            Список словарей с информацией о полях
        """
        user_fields = None

        # Пробуем использовать API через webhook
        try:
            api_url = f"{self.config.webhook_url}/imena.camunda.userfield.list"
            logger.debug(f"Попытка проверки через webhook API: {api_url}")

            response = requests.get(api_url, timeout=self.config.request_timeout)
            response.raise_for_status()
            result = response.json()

            # Проверяем наличие ошибок
            if 'error' in result:
                logger.warning(f"Webhook API вернул ошибку: {result.get('error', {}).get('error_description', 'Unknown error')}")
                raise requests.exceptions.RequestException("Webhook API error")

            # Извлекаем список полей
            api_data = result.get('result', {})
            user_fields = api_data.get('userFields', [])
            logger.debug(f"Получено {len(user_fields)} полей через webhook API")

        except (requests.exceptions.RequestException, KeyError) as e:
            logger.warning(f"Не удалось получить поля через webhook API: {e}")
            logger.info("Попытка использовать прямой API файл...")

            # Fallback: используем прямой API файл
            user_fields = self._fetch_user_fields_direct_api()

        return user_fields

    def _fetch_user_fields_direct_api(self) -> List[Dict[str, Any]]:
        """
        Получение списка полей через прямой API файл (fallback)

        Returns:
            Список словарей с информацией о полях
        """
        try:
            webhook_parsed = urlparse(self.config.webhook_url)
            base_domain = f"{webhook_parsed.scheme}://{webhook_parsed.netloc}"
            direct_api_url = f"{base_domain}/local/modules/imena.camunda/lib/UserFields/userfields_api.php?api=1&method=list"

            logger.debug(f"Попытка проверки через прямой API файл: {direct_api_url}")

            response = requests.get(direct_api_url, timeout=self.config.request_timeout, verify=False)
            response.raise_for_status()
            result = response.json()

            if result.get('status') == 'success':
                api_data = result.get('data', {})
                user_fields = api_data.get('userFields', [])
                logger.debug(f"Получено {len(user_fields)} полей через прямой API файл")
                return user_fields
            else:
                raise requests.exceptions.RequestException("Direct API returned error")

        except Exception as e:
            logger.error(f"Не удалось получить поля через прямой API файл: {e}")
            raise

    def _build_found_fields_dict(self, user_fields: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Построение словаря найденных полей

        Args:
            user_fields: Список полей из API

        Returns:
            Словарь {field_name: field_info}
        """
        found_fields = {}
        for field in user_fields:
            field_name = field.get('FIELD_NAME')
            if field_name:
                found_fields[field_name] = {
                    'ID': field.get('ID', 'unknown'),
                    'USER_TYPE_ID': field.get('USER_TYPE_ID', 'unknown'),
                    'field_data': field
                }
        return found_fields

    def _validate_fields(self, found_fields: Dict[str, Dict[str, Any]]) -> tuple:
        """
        Валидация обязательных полей

        Args:
            found_fields: Словарь найденных полей

        Returns:
            Кортеж (missing_fields, incorrect_type_fields)
        """
        missing_fields = []
        incorrect_type_fields = []

        for field_name, field_info in self.REQUIRED_FIELDS.items():
            expected_type = field_info['type']
            description = field_info['description']

            if field_name not in found_fields:
                missing_fields.append({
                    'name': field_name,
                    'type': expected_type,
                    'description': description
                })
            else:
                actual_type = found_fields[field_name]['USER_TYPE_ID']
                field_id = found_fields[field_name]['ID']

                # Проверяем соответствие типа
                expected_types = self.TYPE_MAPPING.get(expected_type, [expected_type])
                if actual_type.lower() not in [t.lower() for t in expected_types]:
                    incorrect_type_fields.append({
                        'name': field_name,
                        'expected': expected_type,
                        'actual': actual_type,
                        'id': field_id
                    })
                    logger.warning(f"⚠️  Поле {field_name} найдено, но имеет неверный тип: ожидается '{expected_type}', фактически '{actual_type}' (ID: {field_id})")
                else:
                    logger.info(f"✅ Поле {field_name} найдено (ID: {field_id}, тип: {actual_type}) - {description}")

        return missing_fields, incorrect_type_fields

    def _log_fatal_error_no_fields(self) -> None:
        """Логирование фатальной ошибки: не удалось получить список полей"""
        logger.error("=" * 80)
        logger.error("ФАТАЛЬНАЯ ОШИБКА: Не удалось получить список полей из Bitrix24!")
        logger.error("=" * 80)
        logger.error("")
        logger.error("ДЕЙСТВИЯ:")
        logger.error("1. Проверьте доступность Bitrix24 API")
        logger.error("2. Проверьте правильность BITRIX_WEBHOOK_URL в конфигурации")
        logger.error("3. Убедитесь, что модуль imena.camunda установлен и активен")
        logger.error("4. Перезапустите сервис после исправления")
        logger.error("")

    def _log_fatal_error_missing_fields(
        self,
        missing_fields: List[Dict[str, str]],
        incorrect_type_fields: List[Dict[str, str]]
    ) -> None:
        """Логирование фатальной ошибки: отсутствующие или неверные поля"""
        logger.error("=" * 80)
        logger.error("ФАТАЛЬНАЯ ОШИБКА: Обязательные поля отсутствуют или имеют неверный тип!")
        logger.error("=" * 80)
        logger.error("")

        if missing_fields:
            logger.error("ОТСУТСТВУЮЩИЕ ПОЛЯ:")
            for field in missing_fields:
                logger.error(f"  ❌ {field['name']} (тип: {field['type']})")
                logger.error(f"     Описание: {field['description']}")
            logger.error("")

        if incorrect_type_fields:
            logger.error("ПОЛЯ С НЕВЕРНЫМ ТИПОМ:")
            for field in incorrect_type_fields:
                logger.error(f"  ⚠️  {field['name']} (ID: {field['id']})")
                logger.error(f"     Ожидается: {field['expected']}, фактически: {field['actual']}")
            logger.error("")

        logger.error("ДЕЙСТВИЯ:")
        logger.error("1. Создайте отсутствующие пользовательские поля в Bitrix24:")
        logger.error("   Объект: Задачи (TASKS_TASK)")
        logger.error("")

        for field in missing_fields:
            logger.error(f"   - {field['name']}:")
            logger.error(f"     * Тип: {field['type']}")
            logger.error(f"     * Описание: {field['description']}")
            if field['name'] == 'UF_CAMUNDA_ID_EXTERNAL_TASK':
                logger.error("     * Обязательное: Нет (но должно быть уникальным)")
            logger.error("")

        if incorrect_type_fields:
            logger.error("2. Исправьте типы полей с неверным типом:")
            for field in incorrect_type_fields:
                logger.error(f"   - {field['name']}: измените тип с '{field['actual']}' на '{field['expected']}'")
            logger.error("")

        logger.error("3. Перезапустите сервис после создания/исправления полей")
        logger.error("4. Только после этого сервис сможет корректно работать")
        logger.error("")
        logger.error("БЕЗ ВСЕХ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ СЕРВИС НЕ МОЖЕТ РАБОТАТЬ КОРРЕКТНО!")
        logger.error("=" * 80)

    def _log_fatal_error_connection(self, error: Exception) -> None:
        """Логирование фатальной ошибки: ошибка подключения"""
        logger.error("=" * 80)
        logger.error("ФАТАЛЬНАЯ ОШИБКА: Не удалось подключиться к Bitrix24 API!")
        logger.error("=" * 80)
        logger.error("")
        logger.error(f"Ошибка подключения: {error}")
        logger.error("")
        logger.error("ДЕЙСТВИЯ:")
        logger.error("1. Проверьте доступность Bitrix24")
        logger.error("2. Проверьте правильность BITRIX_WEBHOOK_URL в конфигурации")
        logger.error("3. Убедитесь, что API метод imena.camunda.userfield.list доступен")
        logger.error("4. Перезапустите сервис после исправления")
        logger.error("")

    def _log_fatal_error_unexpected(self, error: Exception) -> None:
        """Логирование фатальной ошибки: неожиданная ошибка"""
        logger.error("=" * 80)
        logger.error("ФАТАЛЬНАЯ ОШИБКА: Неожиданная ошибка при проверке обязательных полей!")
        logger.error("=" * 80)
        logger.error("")
        logger.error(f"Ошибка: {error}")
        logger.error("")
        logger.error("ДЕЙСТВИЯ:")
        logger.error("1. Проверьте логи для деталей")
        logger.error("2. Убедитесь, что все обязательные поля созданы в Bitrix24:")
        logger.error("   - UF_CAMUNDA_ID_EXTERNAL_TASK (string)")
        logger.error("   - UF_RESULT_ANSWER (enumeration)")
        logger.error("   - UF_RESULT_QUESTION (string)")
        logger.error("   - UF_RESULT_EXPECTED (boolean)")
        logger.error("   - UF_ELEMENT_ID (string)")
        logger.error("   - UF_PROCESS_INSTANCE_ID (string)")
        logger.error("3. Перезапустите сервис после исправления")
        logger.error("")
