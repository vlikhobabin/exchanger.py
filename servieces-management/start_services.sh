#!/bin/bash
set -e

# ============================================================================
# Скрипт для запуска сервисов Exchanger.py
# Использование: ./start_services.sh [prod|dev|all]
# ============================================================================

ENV=${1:-prod}

case $ENV in
    prod)
        echo "Starting Exchanger.py PRODUCTION services..."
        sudo systemctl start exchanger-camunda-worker-prod
        sudo systemctl start exchanger-task-creator-prod
        echo ""
        echo "✓ PROD services started successfully"
        echo ""
        sudo systemctl status exchanger-camunda-worker-prod exchanger-task-creator-prod --no-pager -l | head -20
        ;;
    dev)
        echo "Starting Exchanger.py DEVELOPMENT services..."
        sudo systemctl start exchanger-camunda-worker-dev
        sudo systemctl start exchanger-task-creator-dev
        echo ""
        echo "✓ DEV services started successfully"
        echo ""
        sudo systemctl status exchanger-camunda-worker-dev exchanger-task-creator-dev --no-pager -l | head -20
        ;;
    all)
        echo "Starting ALL Exchanger.py services..."
        sudo systemctl start exchanger-camunda-worker-prod exchanger-task-creator-prod
        sudo systemctl start exchanger-camunda-worker-dev exchanger-task-creator-dev
        echo ""
        echo "✓ All services started successfully"
        echo ""
        echo "=== PROD ==="
        sudo systemctl status exchanger-camunda-worker-prod exchanger-task-creator-prod --no-pager -l | head -10
        echo ""
        echo "=== DEV ==="
        sudo systemctl status exchanger-camunda-worker-dev exchanger-task-creator-dev --no-pager -l | head -10
        ;;
    *)
        echo "Exchanger.py - Start Services"
        echo ""
        echo "Usage: $0 [prod|dev|all]"
        echo ""
        echo "Options:"
        echo "  prod  - Start production services (default)"
        echo "  dev   - Start development services"
        echo "  all   - Start both prod and dev services"
        echo ""
        echo "Examples:"
        echo "  $0           # Start prod (default)"
        echo "  $0 prod      # Start prod"
        echo "  $0 dev       # Start dev"
        echo "  $0 all       # Start both"
        exit 1
        ;;
esac
