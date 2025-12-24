"""
Сервис для работы с файлами задач Bitrix24

Модуль содержит класс FileService для управления файлами:
прикрепление файлов шаблона, прикрепление файлов предшественников,
формирование текстовых блоков для описания.
"""
import json
from typing import Any, Dict, List, Optional

import requests
from loguru import logger


class FileService:
    """
    Сервис для работы с файлами задач Bitrix24

    Предоставляет методы для прикрепления файлов из шаблонов,
    прикрепления файлов от задач-предшественников и формирования
    текстовых блоков с информацией о файлах.
    """

    def __init__(self, config: Any, stats: Dict[str, int]):
        """
        Инициализация сервиса файлов

        Args:
            config: Конфигурация (webhook_url, request_timeout)
            stats: Словарь статистики для обновления счётчиков
        """
        self.config = config
        self.stats = stats

    def attach_template_files(self, task_id: int, files: List[Dict[str, Any]]) -> None:
        """
        Прикрепление файлов из шаблона к созданной задаче Bitrix24

        Использует метод tasks.task.files.attach для прикрепления файлов диска к задаче.

        Args:
            task_id: ID задачи в Bitrix24
            files: Список файлов из шаблона (с полями OBJECT_ID, NAME, ID)
        """
        if not files:
            logger.debug(f"Нет файлов для прикрепления к задаче {task_id}")
            return

        api_url = f"{self.config.webhook_url.rstrip('/')}/tasks.task.files.attach.json"

        for file_entry in files:
            object_id = file_entry.get('OBJECT_ID')
            attached_id = file_entry.get('ID')
            file_name = file_entry.get('NAME') or f"object_{object_id}"

            if not object_id:
                logger.warning(f"Пропуск файла без OBJECT_ID в шаблоне (task_id={task_id}, file={file_entry})")
                self.stats["template_files_failed"] += 1
                continue

            payload = {
                "taskId": task_id,
                "fileId": object_id
            }

            try:
                logger.info(f"Прикрепление файла '{file_name}' (OBJECT_ID={object_id}, attachedId={attached_id}) к задаче {task_id}")
                response = requests.post(api_url, data=payload, timeout=self.config.request_timeout)

                try:
                    data = response.json()
                except json.JSONDecodeError:
                    self.stats["template_files_failed"] += 1
                    logger.error(f"Некорректный JSON ответ при прикреплении файла '{file_name}' к задаче {task_id}: {response.text}")
                    continue

                if response.status_code != 200 or data.get('error'):
                    error_desc = data.get('error_description', data.get('error', 'Неизвестная ошибка'))
                    logger.warning(f"Bitrix24 вернул ошибку при прикреплении файла '{file_name}' к задаче {task_id}: {error_desc}")
                    self.stats["template_files_failed"] += 1
                    continue

                self.stats["template_files_attached"] += 1
                logger.info(f"Файл '{file_name}' успешно прикреплён к задаче {task_id}")

            except requests.exceptions.RequestException as e:
                self.stats["template_files_failed"] += 1
                logger.error(f"Ошибка запроса при прикреплении файла '{file_name}' к задаче {task_id}: {e}")
            except Exception as e:
                self.stats["template_files_failed"] += 1
                logger.error(f"Неожиданная ошибка при прикреплении файла '{file_name}' к задаче {task_id}: {e}")

    def attach_predecessor_files(
        self,
        task_id: int,
        predecessor_results: Dict[int, List[Dict[str, Any]]]
    ) -> None:
        """
        Прикрепление файлов из результатов предшествующих задач к созданной задаче

        Использует скачивание файлов через DOWNLOAD_URL и загрузку через disk API,
        затем прикрепление к задаче.

        Args:
            task_id: ID созданной задачи
            predecessor_results: Словарь с результатами предшественников
                                 {pred_task_id: [{"files": [...], ...}, ...]}
        """
        if not predecessor_results:
            return

        # Собираем все файлы из результатов
        all_files: List[Dict[str, Any]] = []
        for pred_task_id, results in predecessor_results.items():
            for result in results:
                for file_info in result.get('files', []):
                    file_info['source_task_id'] = pred_task_id
                    all_files.append(file_info)

        if not all_files:
            logger.debug(f"Нет файлов для прикрепления от предшественников к задаче {task_id}")
            return

        logger.info(f"Прикрепление {len(all_files)} файлов от предшественников к задаче {task_id}")

        # Прикрепляем файлы через FILE_ID (disk file id)
        api_url = f"{self.config.webhook_url.rstrip('/')}/tasks.task.files.attach.json"

        for file_info in all_files:
            file_id = file_info.get('fileId')
            file_name = file_info.get('name', 'unknown')
            source_task = file_info.get('source_task_id')

            if not file_id:
                logger.warning(f"Пропуск файла '{file_name}' без fileId (source_task={source_task})")
                self.stats["predecessor_files_failed"] += 1
                continue

            payload = {
                "taskId": task_id,
                "fileId": file_id
            }

            try:
                logger.debug(f"Прикрепление файла '{file_name}' (fileId={file_id}) от задачи {source_task}")
                response = requests.post(api_url, data=payload, timeout=self.config.request_timeout)

                try:
                    data = response.json()
                except json.JSONDecodeError:
                    self.stats["predecessor_files_failed"] += 1
                    logger.error(f"Некорректный JSON при прикреплении файла '{file_name}': {response.text}")
                    continue

                if response.status_code != 200 or data.get('error'):
                    error_desc = data.get('error_description', data.get('error', 'Неизвестная ошибка'))
                    logger.warning(f"Ошибка прикрепления файла '{file_name}' к задаче {task_id}: {error_desc}")
                    self.stats["predecessor_files_failed"] += 1
                    continue

                self.stats["predecessor_files_attached"] += 1
                logger.info(f"Файл '{file_name}' от задачи {source_task} прикреплён к задаче {task_id}")

            except requests.exceptions.RequestException as e:
                self.stats["predecessor_files_failed"] += 1
                logger.error(f"Ошибка запроса при прикреплении файла '{file_name}': {e}")
            except Exception as e:
                self.stats["predecessor_files_failed"] += 1
                logger.error(f"Неожиданная ошибка при прикреплении файла '{file_name}': {e}")

    def build_template_files_block(self, files: List[Dict[str, Any]]) -> Optional[str]:
        """
        Формирование текстового блока с ссылками на файлы шаблона

        Args:
            files: Список файлов из шаблона (с полями NAME, URL)

        Returns:
            Текстовый блок со списком файлов или None если файлов нет
        """
        if not files:
            return None

        base_url = self.config.webhook_url.split('/rest/')[0].rstrip('/')
        lines: List[str] = ["Файлы из шаблона:"]

        for index, file_entry in enumerate(files, start=1):
            name = file_entry.get('NAME') or f"Файл {index}"
            relative_url = file_entry.get('URL')
            if not relative_url:
                lines.append(f"{index}. {name}")
                continue
            full_url = f"{base_url}{relative_url}"
            lines.append(f"{index}. {name}: {full_url}")

        return "\n".join(lines)
