#!/bin/bash
echo "Checking status of Exchanger.py services..."
sudo systemctl status exchanger-worker exchanger-creator --no-pager 