#!/bin/bash
set -e
echo "Starting Exchanger.py services..."
sudo systemctl start exchanger-camunda-worker
sudo systemctl start exchanger-task-creator
echo "Services started."
sudo systemctl status exchanger-camunda-worker exchanger-task-creator --no-pager 