#!/bin/bash

# ============================================================================
# Скрипт для проверки статуса сервисов Exchanger.py
# Использование: ./status_services.sh [prod|dev|all]
# ============================================================================

ENV=${1:-all}

print_separator() {
    echo "============================================================"
}

case $ENV in
    prod)
        print_separator
        echo "Exchanger.py PRODUCTION Services Status"
        print_separator
        echo ""
        echo ">>> Camunda Worker [PROD]"
        sudo systemctl status exchanger-camunda-worker-prod --no-pager -l 2>/dev/null || echo "   Service not found or not running"
        echo ""
        echo ">>> Task Creator [PROD]"
        sudo systemctl status exchanger-task-creator-prod --no-pager -l 2>/dev/null || echo "   Service not found or not running"
        ;;
    dev)
        print_separator
        echo "Exchanger.py DEVELOPMENT Services Status"
        print_separator
        echo ""
        echo ">>> Camunda Worker [DEV]"
        sudo systemctl status exchanger-camunda-worker-dev --no-pager -l 2>/dev/null || echo "   Service not found or not running"
        echo ""
        echo ">>> Task Creator [DEV]"
        sudo systemctl status exchanger-task-creator-dev --no-pager -l 2>/dev/null || echo "   Service not found or not running"
        ;;
    all)
        print_separator
        echo "Exchanger.py ALL Services Status"
        print_separator
        echo ""
        echo "=== PRODUCTION SERVICES ==="
        echo ""
        echo ">>> Camunda Worker [PROD]"
        systemctl is-active exchanger-camunda-worker-prod 2>/dev/null && \
            sudo systemctl status exchanger-camunda-worker-prod --no-pager -l | head -15 || \
            echo "   Status: inactive or not found"
        echo ""
        echo ">>> Task Creator [PROD]"
        systemctl is-active exchanger-task-creator-prod 2>/dev/null && \
            sudo systemctl status exchanger-task-creator-prod --no-pager -l | head -15 || \
            echo "   Status: inactive or not found"
        echo ""
        print_separator
        echo ""
        echo "=== DEVELOPMENT SERVICES ==="
        echo ""
        echo ">>> Camunda Worker [DEV]"
        systemctl is-active exchanger-camunda-worker-dev 2>/dev/null && \
            sudo systemctl status exchanger-camunda-worker-dev --no-pager -l | head -15 || \
            echo "   Status: inactive or not found"
        echo ""
        echo ">>> Task Creator [DEV]"
        systemctl is-active exchanger-task-creator-dev 2>/dev/null && \
            sudo systemctl status exchanger-task-creator-dev --no-pager -l | head -15 || \
            echo "   Status: inactive or not found"
        ;;
    summary)
        print_separator
        echo "Exchanger.py Services Summary"
        print_separator
        echo ""
        echo "Service                             Status          Enabled"
        echo "-----------------------------------------------------------"
        
        for svc in exchanger-camunda-worker-prod exchanger-task-creator-prod exchanger-camunda-worker-dev exchanger-task-creator-dev; do
            status=$(systemctl is-active $svc 2>/dev/null | tr -d '\n' || echo "inactive")
            enabled=$(systemctl is-enabled $svc 2>/dev/null | tr -d '\n' || echo "disabled")
            printf "%-35s %-15s %s\n" "$svc" "$status" "$enabled"
        done
        ;;
    *)
        echo "Exchanger.py - Services Status"
        echo ""
        echo "Usage: $0 [prod|dev|all|summary]"
        echo ""
        echo "Options:"
        echo "  prod    - Show production services status"
        echo "  dev     - Show development services status"
        echo "  all     - Show all services status (default)"
        echo "  summary - Show compact summary table"
        exit 1
        ;;
esac

echo ""
print_separator
echo "Log files location:"
echo "  PROD: /opt/exchanger.py/logs/prod/"
echo "  DEV:  /opt/exchanger.py/logs/dev/"
print_separator
