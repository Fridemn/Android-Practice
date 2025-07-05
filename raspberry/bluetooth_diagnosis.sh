#!/bin/bash

# 蓝牙系统诊断脚本

echo "========================================"
echo "蓝牙系统完整诊断"
echo "========================================"

echo "1. 检查蓝牙硬件..."
lsusb | grep -i bluetooth
echo ""
echo "蓝牙适配器详细状态:"
hciconfig -a

echo ""
echo "2. 检查蓝牙服务状态..."
systemctl status bluetooth --no-pager

echo ""
echo "3. 检查Python蓝牙库..."
python3 -c "import bluetooth; print('pybluez库OK')" 2>&1 || echo "pybluez库缺失"

echo ""
echo "4. 检查蓝牙可发现状态..."
bluetoothctl show | grep -E "(Powered|Discoverable|Pairable)"

echo ""
echo "5. 检查蓝牙进程..."
ps aux | grep -i bluetooth | grep -v grep

echo ""
echo "6. 检查蓝牙设备权限..."
ls -la /dev/rfcomm* 2>/dev/null || echo "无RFCOMM设备"
groups | grep bluetooth && echo "用户在bluetooth组中" || echo "用户不在bluetooth组中"

echo ""
echo "4. 检查蓝牙开发库..."
dpkg -l | grep -i bluetooth
dpkg -l | grep libbluetooth

echo ""
echo "5. 检查Python开发库..."
dpkg -l | grep python3-dev

echo ""
echo "6. 检查编译工具..."
which gcc
which make

echo "========================================"
echo "诊断完成"
echo "========================================"
