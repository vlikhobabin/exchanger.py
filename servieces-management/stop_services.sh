#!/bin/bash
set -e
echo "Stopping Exchanger.py services..."
sudo systemctl stop exchanger-camunda-worker
sudo systemctl stop exchanger-task-creator
echo "Services stopped." 