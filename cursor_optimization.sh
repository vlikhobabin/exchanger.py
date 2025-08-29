#!/bin/bash

# Скрипт для оптимизации системы под работу Cursor IDE

echo "=== Оптимизация системы для Cursor IDE ==="

# 1. Увеличение лимитов для процессов
echo "Настройка лимитов процессов..."
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf
echo "* soft nproc 32768" >> /etc/security/limits.conf
echo "* hard nproc 32768" >> /etc/security/limits.conf

# 2. Настройка swap (если не настроен)
if [ $(swapon --show | wc -l) -eq 0 ]; then
    echo "Создание swap файла..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "Swap файл создан и активирован"
fi

# 3. Оптимизация памяти
echo "Настройка параметров памяти..."
echo 'vm.swappiness=10' >> /etc/sysctl.conf
echo 'vm.vfs_cache_pressure=50' >> /etc/sysctl.conf
sysctl -p

# 4. Очистка системы
echo "Очистка системы..."
apt-get autoremove -y
apt-get autoclean
journalctl --vacuum-time=7d

# 5. Проверка и удаление libfuse2 если установлен
if dpkg -l | grep -q libfuse2; then
    echo "Обнаружен libfuse2, удаляем..."
    apt-get remove --purge libfuse2 -y
    apt-get autoremove -y
    echo "libfuse2 удален"
else
    echo "libfuse2 не установлен - хорошо!"
fi

echo "=== Оптимизация завершена ==="
echo "Рекомендуется перезагрузить систему: sudo reboot"
