#!/bin/bash
set -e
echo "Restarting Exchanger.py services..."
sudo systemctl restart exchanger-camunda-worker
sudo systemctl restart exchanger-task-creator
echo "Services restarted."
sudo systemctl status exchanger-camunda-worker exchanger-task-creator --no-pager 