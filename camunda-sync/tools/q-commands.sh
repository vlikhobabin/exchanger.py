#!/bin/bash
PROCESS_ID="Process_06mpj1p"
# Остановить процесс
python camunda-worker/tools/process_manager.py stop $PROCESS_ID --force
# Очистка очереди
python camunda-worker/tools/queue_reader.py bitrix24.sent.queue --clear --force
# Запустить процесс
python camunda-worker/tools/process_manager.py start $PROCESS_ID