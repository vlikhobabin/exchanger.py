#!/bin/bash
set -e
echo "Stopping Exchanger.py services..."
sudo systemctl stop exchanger-worker
sudo systemctl stop exchanger-creator
echo "Services stopped." 