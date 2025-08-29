#!/bin/bash
echo "Checking status of Exchanger.py services..."
sudo systemctl status exchanger-camunda-worker exchanger-task-creator --no-pager 