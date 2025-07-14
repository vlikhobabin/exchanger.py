#!/bin/bash
set -e
echo "Starting Exchanger.py services..."
sudo systemctl start exchanger-worker
sudo systemctl start exchanger-creator
echo "Services started."
sudo systemctl status exchanger-worker exchanger-creator --no-pager 