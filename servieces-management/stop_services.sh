#!/bin/bash
set -e

# ============================================================================
# Скрипт для остановки сервисов Exchanger.py
# Использование: ./stop_services.sh [prod|dev|all]
# ============================================================================

ENV=${1:-prod}

case $ENV in
    prod)
        echo "Stopping Exchanger.py PRODUCTION services..."
        sudo systemctl stop exchanger-camunda-worker-prod 2>/dev/null || true
        sudo systemctl stop exchanger-task-creator-prod 2>/dev/null || true
        echo ""
        echo "✓ PROD services stopped"
        ;;
    dev)
        echo "Stopping Exchanger.py DEVELOPMENT services..."
        sudo systemctl stop exchanger-camunda-worker-dev 2>/dev/null || true
        sudo systemctl stop exchanger-task-creator-dev 2>/dev/null || true
        echo ""
        echo "✓ DEV services stopped"
        ;;
    all)
        echo "Stopping ALL Exchanger.py services..."
        sudo systemctl stop exchanger-camunda-worker-prod 2>/dev/null || true
        sudo systemctl stop exchanger-task-creator-prod 2>/dev/null || true
        sudo systemctl stop exchanger-camunda-worker-dev 2>/dev/null || true
        sudo systemctl stop exchanger-task-creator-dev 2>/dev/null || true
        echo ""
        echo "✓ All services stopped"
        ;;
    *)
        echo "Exchanger.py - Stop Services"
        echo ""
        echo "Usage: $0 [prod|dev|all]"
        echo ""
        echo "Options:"
        echo "  prod  - Stop production services (default)"
        echo "  dev   - Stop development services"
        echo "  all   - Stop both prod and dev services"
        exit 1
        ;;
esac
