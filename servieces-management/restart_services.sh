#!/bin/bash
set -e

# ============================================================================
# Скрипт для перезапуска сервисов Exchanger.py
# Использование: ./restart_services.sh [prod|dev|all]
# ============================================================================

ENV=${1:-prod}

case $ENV in
    prod)
        echo "Restarting Exchanger.py PRODUCTION services..."
        sudo systemctl restart exchanger-camunda-worker-prod
        sudo systemctl restart exchanger-task-creator-prod
        echo ""
        echo "✓ PROD services restarted successfully"
        echo ""
        sudo systemctl status exchanger-camunda-worker-prod exchanger-task-creator-prod --no-pager -l | head -20
        ;;
    dev)
        echo "Restarting Exchanger.py DEVELOPMENT services..."
        sudo systemctl restart exchanger-camunda-worker-dev
        sudo systemctl restart exchanger-task-creator-dev
        echo ""
        echo "✓ DEV services restarted successfully"
        echo ""
        sudo systemctl status exchanger-camunda-worker-dev exchanger-task-creator-dev --no-pager -l | head -20
        ;;
    all)
        echo "Restarting ALL Exchanger.py services..."
        sudo systemctl restart exchanger-camunda-worker-prod exchanger-task-creator-prod
        sudo systemctl restart exchanger-camunda-worker-dev exchanger-task-creator-dev
        echo ""
        echo "✓ All services restarted successfully"
        echo ""
        echo "=== PROD ==="
        sudo systemctl status exchanger-camunda-worker-prod exchanger-task-creator-prod --no-pager -l | head -10
        echo ""
        echo "=== DEV ==="
        sudo systemctl status exchanger-camunda-worker-dev exchanger-task-creator-dev --no-pager -l | head -10
        ;;
    *)
        echo "Exchanger.py - Restart Services"
        echo ""
        echo "Usage: $0 [prod|dev|all]"
        echo ""
        echo "Options:"
        echo "  prod  - Restart production services (default)"
        echo "  dev   - Restart development services"
        echo "  all   - Restart both prod and dev services"
        exit 1
        ;;
esac
