#!/bin/bash
set -e
echo "Restarting Exchanger.py services..."
sudo systemctl restart exchanger-worker
sudo systemctl restart exchanger-creator
echo "Services restarted."
sudo systemctl status exchanger-worker exchanger-creator --no-pager 