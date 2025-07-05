#!/bin/bash

# 树莓派蓝牙遥控器安装脚本

echo "========================================"
echo "树莓派蓝牙遥控器系统安装脚本"
echo "========================================"

# 更新系统
echo "更新系统包..."
sudo apt update && sudo apt upgrade -y

# 安装必要的包
echo "安装必要的软件包..."
sudo apt install -y python3-pip python3-dev python3-venv
sudo apt install -y bluetooth bluez bluez-tools
sudo apt install -y i2c-tools
sudo apt install -y pigpio

# 安装 Python 库
echo "安装 Python 依赖库..."
pip3 install pybluez
pip3 install gpiozero
pip3 install pigpio
pip3 install adafruit-circuitpython-ssd1306
pip3 install adafruit-blinka
pip3 install Pillow

# 启用必要的服务
echo "配置系统服务..."
sudo systemctl enable bluetooth
sudo systemctl start bluetooth
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# 启用 I2C
echo "启用 I2C 接口..."
sudo raspi-config nonint do_i2c 0

# 修复蓝牙配置
echo "修复蓝牙配置..."
sudo tee /etc/bluetooth/main.conf > /dev/null <<EOF
[General]
Name = RaspberryPi-Controller
Class = 0x1F00
DiscoverableTimeout = 0
PairableTimeout = 0
Discoverable = yes
Pairable = yes

[Policy]
AutoEnable=true
EOF

# 重启蓝牙服务
sudo systemctl restart bluetooth
sleep 3

# 配置蓝牙为可发现
echo "配置蓝牙设置..."
sudo hciconfig hci0 up
sudo hciconfig hci0 piscan
sudo hciconfig hci0 sspmode 1

# 创建服务文件
echo "创建系统服务..."
sudo tee /etc/systemd/system/rpi-controller.service > /dev/null <<EOF
[Unit]
Description=Raspberry Pi Bluetooth Controller
After=bluetooth.service pigpiod.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/raspberry_pi_controller.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 复制控制脚本到用户目录
echo "复制控制脚本..."
cp raspberry_pi_controller.py /home/pi/

# 设置权限
sudo chown pi:pi /home/pi/raspberry_pi_controller.py
sudo chmod +x /home/pi/raspberry_pi_controller.py

echo "========================================"
echo "安装完成！"
echo "========================================"
echo ""
echo "硬件连接说明："
echo "舵机1 -> GPIO 18 (Pin 12)"
echo "舵机2 -> GPIO 19 (Pin 35)"
echo "OLED SDA -> GPIO 2 (Pin 3)"
echo "OLED SCL -> GPIO 3 (Pin 5)"
echo "所有设备共地线 -> GND"
echo ""
echo "使用说明："
echo "1. 手动运行: python3 /home/pi/raspberry_pi_controller.py"
echo "2. 启用服务: sudo systemctl enable rpi-controller"
echo "3. 启动服务: sudo systemctl start rpi-controller"
echo "4. 查看状态: sudo systemctl status rpi-controller"
echo "5. 查看日志: sudo journalctl -u rpi-controller -f"
echo ""
echo "重启系统以确保所有设置生效:"
echo "sudo reboot"
