#!/usr/bin/env python3
"""
Кастомный ExternalTaskClient с поддержкой Camunda Multi-Tenancy.

Расширяет стандартную библиотеку camunda-external-task-client-python3
для добавления поддержки фильтрации задач по tenant ID.

Camunda 7 Multi-Tenancy позволяет разделять процессы и задачи
между различными "тенантами" (арендаторами), что используется
для разделения prod и dev сред на одном сервере Camunda.

Использование:
    client = TenantAwareExternalTaskClient(
        worker_id="my-worker",
        engine_base_url="https://camunda.example.com/engine-rest",
        config={...},
        tenant_id="imenaProd"  # Фильтрация по tenant
    )
"""
import logging
from typing import Optional, List, Dict, Any
from camunda.client.external_task_client import ExternalTaskClient
from camunda.utils.utils import str_to_list

logger = logging.getLogger(__name__)


class TenantAwareExternalTaskClient(ExternalTaskClient):
    """
    ExternalTaskClient с поддержкой tenant ID для multi-tenancy в Camunda.
    
    При указании tenant_id, клиент будет получать только задачи, 
    принадлежащие указанному tenant.
    
    Это реализуется через параметр tenantIdIn в Camunda REST API fetchAndLock:
    https://docs.camunda.org/manual/7.21/reference/rest/external-task/fetch/
    
    Attributes:
        tenant_id: ID тенанта для фильтрации задач (None = все тенанты)
    """
    
    def __init__(
        self, 
        worker_id: str, 
        engine_base_url: str, 
        config: Optional[Dict[str, Any]] = None, 
        tenant_id: Optional[str] = None
    ):
        """
        Инициализация клиента с поддержкой tenant ID.
        
        Args:
            worker_id: Уникальный идентификатор воркера в Camunda
            engine_base_url: URL Camunda REST API (например, https://camunda.example.com/engine-rest)
            config: Конфигурация клиента (maxTasks, lockDuration, etc.)
            tenant_id: ID тенанта для фильтрации задач.
                      Если None - будут получаться задачи всех тенантов.
                      Если указан - только задачи с этим tenant ID.
        """
        super().__init__(worker_id, engine_base_url, config)
        self.tenant_id = tenant_id
        
        if self.tenant_id:
            self._log_with_context(
                f"Tenant-aware client initialized. "
                f"Filtering tasks by tenant_id: {self.tenant_id}"
            )
        else:
            self._log_with_context(
                "Tenant-aware client initialized WITHOUT tenant filter. "
                "Will fetch tasks from ALL tenants."
            )
    
    def _get_topics(
        self, 
        topic_names: str, 
        process_variables: Optional[Dict] = None, 
        variables: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Переопределение метода для добавления tenantIdIn в каждый topic.
        
        Camunda REST API fetchAndLock поддерживает следующие параметры на уровне topic:
        - topicName: имя топика
        - tenantIdIn: массив tenant IDs для фильтрации задач
        - withoutTenantId: boolean для получения задач без tenant
        - lockDuration, variables, processVariables, etc.
        
        Args:
            topic_names: Имя топика или список топиков через запятую
            process_variables: Переменные процесса для фильтрации
            variables: Список переменных для получения
            
        Returns:
            Список конфигураций топиков для fetchAndLock
        """
        topics = []
        
        for topic in str_to_list(topic_names):
            topic_config = {
                "topicName": topic,
                "lockDuration": self.config["lockDuration"],
                "processVariables": process_variables if process_variables else {},
                "includeExtensionProperties": self.config.get("includeExtensionProperties") or False,
                "deserializeValues": self.config["deserializeValues"],
                "variables": variables
            }
            
            # Добавляем фильтрацию по tenant, если указан
            if self.tenant_id:
                topic_config["tenantIdIn"] = [self.tenant_id]
            
            topics.append(topic_config)
        
        return topics
    
    def get_tenant_id(self) -> Optional[str]:
        """Получить текущий tenant ID."""
        return self.tenant_id
    
    def is_tenant_aware(self) -> bool:
        """Проверить, включена ли фильтрация по tenant."""
        return self.tenant_id is not None

