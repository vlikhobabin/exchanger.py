# start_process.py - Запуск новых экземпляров процессов в Camunda через REST API.
	python start_process.py ProcessKey --info
		Просмотр информации о процессе
	
# camunda_processes.py - Получение детальной информации о процессах, экземплярах и задачах в Camunda.
	python camunda_processes.py
		Полная информация о системе
	python camunda_processes.py --stats
		Только статистика
	python camunda_processes.py --external-tasks
		Только внешние задачи
	python camunda_processes.py --export camunda_data.json
		Экспорт в JSON файл
		
# check_queues.py - Мониторинг состояния очередей RabbitMQ с поддержкой Alternate Exchange
	python check_queues.py
		Проверка всех очередей и AE
		
# queue_reader.py - Работа с сообщениями в очередях RabbitMQ
	python queue_reader.py
		Список всех очередей с количеством сообщений
	python queue_reader.py errors.camunda_tasks.queue
		Просмотр первых 5 сообщений из очереди
	python queue_reader.py errors.camunda_tasks.queue --count 10
		Просмотр первых 10 сообщений
	python queue_reader.py errors.camunda_tasks.queue --output backup.json
		Экспорт всех сообщений в JSON файл
	python queue_reader.py errors.camunda_tasks.queue --clear
		Очистка очереди с подтверждением
		
# unlock_task.py - Разблокировка заблокированных задач в Camunda
	python unlock_task.py --task-id abc123-def456-ghi789
		Разблокировка конкретной задачи
	python unlock_task.py --task-id id1,id2,id3
		Разблокировка нескольких задач
	python unlock_task.py --topic bitrix_create_task
		Разблокировка всех задач топика
	python unlock_task.py --worker-id universal-worker
		Разблокировка задач конкретного worker
	python unlock_task.py --list
		Просмотр заблокированных задач без разблокировки

# worker_diagnostics.py - Комплексная диагностика системы
	python worker_diagnostics.py --quick
		Быстрая проверка подключений
	python worker_diagnostics.py --camunda-only
		Проверка только Camunda
	python worker_diagnostics.py --rabbitmq-only
		Проверка только RabbitMQ
	python worker_diagnostics.py --detailed
		Детальный отчет
	python worker_diagnostics.py --export diagnostics_report.json
		Экспорт результатов в файл
		
# status_check.py - Быстрая проверка состояния всех компонентов системы
	python status_check.py
		Статус всех компонентов
		
# test_alternate_exchange.py - Тестирование корректности работы Alternate Exchange
	python test_alternate_exchange.py
		Полное тестирование маршрутизации без дублирования