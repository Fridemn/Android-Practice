#!/usr/bin/env python3
"""
树莓派蓝牙遥控器服务端
控制两个舵机和一个OLED显示屏
"""

import bluetooth
import time
import threading
import subprocess
import signal
import os
from gpiozero import Servo, Device
from gpiozero.pins.pigpio import PiGPIOFactory
import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont
import json

# 使用 pigpio 作为引脚工厂以获得更精确的 PWM 控制
Device.pin_factory = PiGPIOFactory()

class RaspberryPiController:
    def __init__(self):
        # 舵机初始化 (GPIO 引脚)
        self.servo1 = Servo(18)  # GPIO 18
        self.servo2 = Servo(19)  # GPIO 19
        
        # OLED 显示屏初始化 (I2C)
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.oled = adafruit_ssd1306.SSD1306_I2C(128, 64, self.i2c)
        
        # 蓝牙服务器设置
        self.server_socket = None
        self.client_socket = None
        self.is_running = True
        
        # 配对助手设置
        self.pairing_process = None
        self.pairing_active = False
        self.pin_code = "0000"
        
        # 初始化显示
        self.clear_oled()
        self.display_text("Waiting...")
        
    def setup_bluetooth_server(self):
        """设置蓝牙服务器"""
        try:
            # 首先启动配对代理
            self.start_pairing_agent()
            
            # 检查蓝牙适配器状态
            self.check_bluetooth_adapter()
            
            print("Creating bluetooth socket...")
            # 创建蓝牙服务器套接字
            self.server_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.server_socket.bind(("", bluetooth.PORT_ANY))
            self.server_socket.listen(1)
            
            port = self.server_socket.getsockname()[1]
            print(f"Socket bound to port {port}")
            
            # 尝试注册服务，如果失败则跳过
            uuid = "00001101-0000-1000-8000-00805F9B34FB"
            
            print("Trying to advertise service...")
            try:
                bluetooth.advertise_service(
                    self.server_socket,
                    "RaspberryPi-BT",
                    service_id=uuid,
                    service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
                    profiles=[bluetooth.SERIAL_PORT_PROFILE]
                )
                print("Service advertisement successful")
            except Exception as adv_error:
                print(f"Service advertisement failed: {adv_error}")
                print("Continuing without service advertisement...")
                # 手动设置设备可发现
                self.ensure_discoverable()
            
            print(f"🎉 蓝牙服务端启动成功！")
            print(f"📱 等待安卓设备连接...")
            print(f"🔑 配对代理已就绪，可自动处理PIN码")
            print(f"📋 设备名: RaspberryPi-BT")
            print(f"📋 端口: {port}")
            print(f"📋 PIN码: {self.pin_code}")
            self.display_text(f"BT Ready\nPort: {port}")
            
        except Exception as e:
            print(f"Bluetooth setup error: {e}")
            print("Trying alternative setup...")
            
            # 尝试简化的设置
            if self.setup_simple_bluetooth_server():
                print("Simple bluetooth setup successful")
            else:
                print(f"All bluetooth setup methods failed")
                self.display_text(f"BT Error:\n{str(e)[:20]}")
    
    def setup_simple_bluetooth_server(self):
        """简化的蓝牙服务器设置（不使用advertise_service）"""
        try:
            print("Trying simple bluetooth setup...")
            
            # 启动配对代理（如果还没启动）
            if not self.pairing_active:
                self.start_pairing_agent()
            
            # 确保蓝牙适配器配置正确
            self.ensure_discoverable()
            
            # 创建简单的蓝牙socket
            if self.server_socket:
                self.server_socket.close()
                
            self.server_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.server_socket.bind(("", bluetooth.PORT_ANY))
            self.server_socket.listen(1)
            
            port = self.server_socket.getsockname()[1]
            print(f"Simple bluetooth server ready on port {port}")
            print("🔑 配对代理已就绪，可自动处理PIN码确认")
            print("📱 设备现在可以接受连接和配对")
            print("📱 请在安卓设备上搜索 'RaspberryPi-BT' 并配对")
            
            self.display_text(f"BT Simple\nPort: {port}")
            return True
            
        except Exception as e:
            print(f"Simple bluetooth setup failed: {e}")
            return False
    
    def ensure_discoverable(self):
        """确保设备可发现"""
        try:
            import subprocess
            
            print("Ensuring device is discoverable...")
            
            commands = [
                "sudo bluetoothctl power on",
                "sudo bluetoothctl discoverable on", 
                "sudo bluetoothctl pairable on",
                "sudo hciconfig hci0 piscan"
            ]
            
            for cmd in commands:
                try:
                    subprocess.run(cmd.split(), 
                                 stderr=subprocess.DEVNULL, 
                                 timeout=5)
                except:
                    pass
                    
            print("Device discoverability ensured")
            
        except Exception as e:
            print(f"Failed to ensure discoverability: {e}")
    
    def start_pairing_agent(self):
        """启动配对代理，自动处理PIN码确认"""
        if self.pairing_active:
            return
            
        try:
            print("🔑 启动配对代理...")
            self.pairing_active = True
            
            # 启动后台线程处理配对
            pairing_thread = threading.Thread(target=self._pairing_agent_worker, daemon=True)
            pairing_thread.start()
            
            print("✅ 配对代理已启动，可以自动处理PIN码确认")
            
        except Exception as e:
            print(f"❌ 配对代理启动失败: {e}")
            self.pairing_active = False
    
    def _pairing_agent_worker(self):
        """配对代理工作线程"""
        try:
            # 启动bluetoothctl进程
            self.pairing_process = subprocess.Popen(
                ["sudo", "bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 发送初始配置命令
            commands = [
                "agent on",
                "default-agent",
                "pairable on",
                "discoverable on"
            ]
            
            for cmd in commands:
                self.pairing_process.stdin.write(cmd + "\n")
                self.pairing_process.stdin.flush()
                time.sleep(0.5)
            
            print("🔵 配对代理监听配对请求...")
            self.display_text("Pairing Ready\nWaiting...")
            
            # 监听配对请求
            while self.pairing_active and self.pairing_process.poll() is None:
                try:
                    line = self.pairing_process.stdout.readline()
                    if not line:
                        break
                        
                    line = line.strip()
                    if line:
                        print(f"📟 {line}")
                        
                        # 处理各种配对请求
                        if "Request PIN code" in line:
                            print(f"🔑 收到PIN码请求，发送: {self.pin_code}")
                            self.pairing_process.stdin.write(f"{self.pin_code}\n")
                            self.pairing_process.stdin.flush()
                            self.display_text(f"PIN: {self.pin_code}\nSent")
                            
                        elif "Confirm passkey" in line:
                            # 提取密钥
                            import re
                            passkey_match = re.search(r'Confirm passkey (\d+)', line)
                            if passkey_match:
                                passkey = passkey_match.group(1)
                                print(f"🔑 收到密钥确认请求: {passkey}")
                                print("📱 请在手机上确认相同的密钥!")
                                self.display_text(f"Confirm:\n{passkey}")
                                
                            print("✅ 自动确认配对密钥")
                            self.pairing_process.stdin.write("yes\n")
                            self.pairing_process.stdin.flush()
                            
                        elif "Request confirmation" in line:
                            print("🔑 收到配对确认请求")
                            print("✅ 自动确认配对")
                            self.pairing_process.stdin.write("yes\n")
                            self.pairing_process.stdin.flush()
                            self.display_text("Confirming\nPairing...")
                            
                        elif "[agent] Confirm passkey" in line:
                            # 处理代理确认请求
                            import re
                            passkey_match = re.search(r'Confirm passkey (\d+)', line)
                            if passkey_match:
                                passkey = passkey_match.group(1)
                                print(f"🔑 代理密钥确认: {passkey}")
                                print("📱 请在手机上确认相同的密钥!")
                                self.display_text(f"Key: {passkey}\nConfirm on phone")
                            self.pairing_process.stdin.write("yes\n")
                            self.pairing_process.stdin.flush()
                            
                        elif "Authorize service" in line:
                            print("✅ 授权服务")
                            self.pairing_process.stdin.write("yes\n")
                            self.pairing_process.stdin.flush()
                            self.display_text("Service\nAuthorized")
                            
                        elif "Pairing successful" in line:
                            print("🎉 配对成功！")
                            self.display_text("Pairing\nSuccess!")
                            time.sleep(2)  # 显示成功信息2秒
                            
                        elif "Failed to pair" in line:
                            print("❌ 配对失败")
                            self.display_text("Pairing\nFailed")
                            
                        elif "Request canceled" in line:
                            print("⚠️  配对请求被取消")
                            self.display_text("Pairing\nCanceled")
                            
                        elif "NEW" in line and "Device" in line:
                            print("📱 发现新设备尝试配对")
                            self.display_text("Device Found\nPairing...")
                            
                except Exception as e:
                    if self.pairing_active:
                        print(f"配对代理读取错误: {e}")
                    break
                    
        except Exception as e:
            print(f"❌ 配对代理错误: {e}")
        finally:
            self.stop_pairing_agent()
    
    def stop_pairing_agent(self):
        """停止配对代理"""
        self.pairing_active = False
        if self.pairing_process:
            try:
                self.pairing_process.terminate()
                self.pairing_process.wait(timeout=5)
            except:
                try:
                    self.pairing_process.kill()
                except:
                    pass
            self.pairing_process = None
        print("🔑 配对代理已停止")
    
    def check_bluetooth_adapter(self):
        """检查蓝牙适配器状态"""
        try:
            import subprocess
            import os
            
            # 查找hciconfig命令的完整路径
            hciconfig_path = None
            for path in ['/usr/bin/hciconfig', '/bin/hciconfig', '/usr/sbin/hciconfig']:
                if os.path.exists(path):
                    hciconfig_path = path
                    break
            
            if not hciconfig_path:
                # 尝试使用which命令查找
                try:
                    result = subprocess.run(['which', 'hciconfig'], capture_output=True, text=True)
                    if result.returncode == 0:
                        hciconfig_path = result.stdout.strip()
                except:
                    pass
            
            if not hciconfig_path:
                print("hciconfig command not found, assuming adapter is ready")
                return True
            
            result = subprocess.run([hciconfig_path, 'hci0'], capture_output=True, text=True)
            if 'UP RUNNING' not in result.stdout:
                print("Bluetooth adapter not running, trying to fix...")
                return self.fix_bluetooth_adapter()
            if 'ISCAN' not in result.stdout:
                print("Bluetooth not discoverable, trying to fix...")
                return self.fix_bluetooth_adapter()
            print("Bluetooth adapter status: OK")
            return True
        except Exception as e:
            print(f"Bluetooth adapter check failed: {e}")
            print("Continuing with bluetooth setup anyway...")
            return True  # 继续尝试，不因为检查失败而中止
    
    def fix_bluetooth_adapter(self):
        """修复蓝牙适配器配置"""
        try:
            import subprocess
            import os
            print("Fixing bluetooth adapter...")
            
            # 查找命令路径
            def find_command(cmd):
                for path in [f'/usr/bin/{cmd}', f'/bin/{cmd}', f'/usr/sbin/{cmd}', f'/sbin/{cmd}']:
                    if os.path.exists(path):
                        return path
                try:
                    result = subprocess.run(['which', cmd], capture_output=True, text=True)
                    if result.returncode == 0:
                        return result.stdout.strip()
                except:
                    pass
                return cmd  # 最后尝试使用命令名
            
            hciconfig = find_command('hciconfig')
            bluetoothctl = find_command('bluetoothctl')
            
            # 重新启动适配器
            try:
                subprocess.run(['sudo', hciconfig, 'hci0', 'down'], 
                             stderr=subprocess.DEVNULL, timeout=5)
                time.sleep(1)
                subprocess.run(['sudo', hciconfig, 'hci0', 'up'], 
                             stderr=subprocess.DEVNULL, timeout=5)
                time.sleep(1)
                
                # 设置可发现
                subprocess.run(['sudo', hciconfig, 'hci0', 'piscan'], 
                             stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(['sudo', hciconfig, 'hci0', 'sspmode', '1'], 
                             stderr=subprocess.DEVNULL, timeout=5)
            except Exception as e:
                print(f"hciconfig commands failed: {e}")
            
            # 使用bluetoothctl
            try:
                subprocess.run(['sudo', bluetoothctl, 'power', 'on'], 
                             stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(['sudo', bluetoothctl, 'discoverable', 'on'], 
                             stderr=subprocess.DEVNULL, timeout=5)
                subprocess.run(['sudo', bluetoothctl, 'pairable', 'on'], 
                             stderr=subprocess.DEVNULL, timeout=5)
            except Exception as e:
                print(f"bluetoothctl commands failed: {e}")
            
            time.sleep(2)
            
            # 验证修复（可选）
            try:
                result = subprocess.run([hciconfig, 'hci0'], 
                                      capture_output=True, text=True, timeout=5)
                if 'ISCAN' in result.stdout and 'UP RUNNING' in result.stdout:
                    print("Bluetooth adapter fixed successfully")
                    return True
                else:
                    print("Bluetooth adapter status unclear, continuing anyway")
                    return True
            except:
                print("Cannot verify bluetooth status, continuing anyway")
                return True
                
        except Exception as e:
            print(f"Bluetooth adapter fix error: {e}")
            print("Continuing with bluetooth setup anyway...")
            return True  # 即使修复失败也继续尝试
    
    def wait_for_connection(self):
        """等待蓝牙连接"""
        try:
            print("🔍 等待蓝牙连接...")
            print("📱 请从安卓设备连接")
            
            # 设置超时，避免无限等待
            self.server_socket.settimeout(None)  # 无超时，持续等待
            
            self.client_socket, client_info = self.server_socket.accept()
            print(f"✅ 接受来自 {client_info} 的连接")
            print(f"📱 连接设备: {client_info[0]}")
            
            # 验证连接是否稳定
            try:
                print("🔗 验证连接稳定性...")
                self.client_socket.settimeout(5.0)  # 5秒超时
                
                # 发送连接确认并等待握手
                welcome_msg = "WELCOME_RPi"
                self.client_socket.send(welcome_msg.encode('utf-8'))
                print(f"📤 发送欢迎消息: {welcome_msg}")
                
                # 等待客户端握手响应
                try:
                    handshake_data = self.client_socket.recv(1024)
                    if handshake_data:
                        handshake_msg = handshake_data.decode('utf-8').strip()
                        print(f"📥 收到握手消息: '{handshake_msg}'")
                        
                        if handshake_msg in ["PING", "HELLO", "CONNECT"]:
                            # 发送握手确认
                            confirm_msg = "HANDSHAKE_OK"
                            self.client_socket.send(confirm_msg.encode('utf-8'))
                            print(f"📤 发送握手确认: {confirm_msg}")
                        else:
                            print(f"⚠️ 收到未知握手消息，但继续连接")
                    else:
                        print("⚠️ 握手数据为空，但继续连接")
                except Exception as handshake_error:
                    print(f"⚠️ 握手失败: {handshake_error}")
                    print("🔄 尽管握手失败，仍然继续连接")
                
                # 恢复为无超时模式
                self.client_socket.settimeout(None)
                
            except Exception as verify_error:
                print(f"⚠️ 连接验证失败: {verify_error}")
                print("🔄 仍然尝试继续连接")
                
            self.display_text(f"Connected:\n{client_info[0][:12]}")
            print("🎉 连接建立完成！")
            return True
            
        except bluetooth.BluetoothError as e:
            print(f"❌ 蓝牙连接错误: {e}")
            return False
        except Exception as e:
            print(f"❌ 连接错误: {e}")
            return False
    
    def control_servo1(self, angle):
        """控制舵机1"""
        try:
            # 将角度 (0-180) 转换为 servo 值 (-1 到 1)
            servo_value = (angle - 90) / 90.0
            self.servo1.value = max(-1, min(1, servo_value))
            print(f"舵机1 设置到 {angle}°")
            return True
        except Exception as e:
            print(f"舵机1 控制错误: {e}")
            return False
    
    def control_servo2(self, angle):
        """控制舵机2"""
        try:
            # 将角度 (0-180) 转换为 servo 值 (-1 到 1)
            servo_value = (angle - 90) / 90.0
            self.servo2.value = max(-1, min(1, servo_value))
            print(f"舵机2 设置到 {angle}°")
            return True
        except Exception as e:
            print(f"舵机2 控制错误: {e}")
            return False
    
    def display_text(self, text):
        """在OLED上显示文本"""
        try:
            # 清除显示
            self.oled.fill(0)
            
            # 创建图像
            image = Image.new("1", (self.oled.width, self.oled.height))
            draw = ImageDraw.Draw(image)
            
            # 使用默认字体，避免中文编码问题
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            # 将中文转换为拼音或英文显示，避免编码问题
            display_text = self.convert_to_ascii(text)
            
            # 分行显示文本
            lines = display_text.split('\n')
            y_offset = 0
            line_height = 12
            
            for line in lines:
                if y_offset < self.oled.height - line_height:
                    # 确保文本是ASCII编码
                    safe_line = line.encode('ascii', 'ignore').decode('ascii')
                    draw.text((0, y_offset), safe_line, font=font, fill=1)
                    y_offset += line_height
            
            # 显示图像
            self.oled.image(image)
            self.oled.show()
            
        except Exception as e:
            print(f"OLED 显示错误: {e}")
    
    def convert_to_ascii(self, text):
        """将中文文本转换为ASCII可显示的文本"""
        # 中文到英文的简单映射
        chinese_to_english = {
            "等待连接": "Waiting...",
            "蓝牙等待连接": "BT Waiting",
            "已连接": "Connected",
            "蓝牙已连接": "BT Connected", 
            "蓝牙已断开": "BT Disconnected",
            "连接已断开": "Disconnected",
            "舵机": "Servo",
            "服务器已关闭": "Server Closed",
            "温度": "Temp",
            "时间": "Time",
            "状态": "Status",
            "正常": "Normal"
        }
        
        # 替换中文文本
        for chinese, english in chinese_to_english.items():
            text = text.replace(chinese, english)
        
        # 移除其他非ASCII字符
        return ''.join(char for char in text if ord(char) < 128)
    
    def clear_oled(self):
        """清除OLED显示"""
        try:
            self.oled.fill(0)
            self.oled.show()
        except Exception as e:
            print(f"OLED 清除错误: {e}")
    
    def process_command(self, command):
        """处理接收到的命令"""
        try:
            command = command.strip()
            print(f"收到命令: '{command}' (长度: {len(command)} 字节)")
            print(f"命令原始字节: {command.encode('utf-8')}")
            
            if command == "CONNECT":
                print("处理连接命令")
                self.display_text("蓝牙已连接")
                return "OK:CONNECTED"
                
            elif command == "DISCONNECT":
                print("处理断开命令")
                self.display_text("蓝牙已断开")
                return "OK:DISCONNECTED"
                
            elif command.startswith("SERVO1:"):
                print("处理舵机1命令")
                try:
                    angle_str = command.split(":")[1]
                    angle = int(angle_str)
                    print(f"解析角度: {angle}")
                    if 0 <= angle <= 180:
                        if self.control_servo1(angle):
                            self.display_text(f"舵机1: {angle}°")
                            response = f"OK:SERVO1:{angle}"
                            print(f"舵机1控制成功，响应: {response}")
                            return response
                        else:
                            print("舵机1控制失败")
                            return "ERROR:SERVO1_CONTROL_FAILED"
                    else:
                        print(f"无效角度: {angle}")
                        return "ERROR:INVALID_ANGLE"
                except (ValueError, IndexError) as e:
                    print(f"舵机1命令解析错误: {e}")
                    return "ERROR:SERVO1_PARSE_ERROR"
                    
            elif command.startswith("SERVO2:"):
                print("处理舵机2命令")
                try:
                    angle_str = command.split(":")[1]
                    angle = int(angle_str)
                    print(f"解析角度: {angle}")
                    if 0 <= angle <= 180:
                        if self.control_servo2(angle):
                            self.display_text(f"舵机2: {angle}°")
                            response = f"OK:SERVO2:{angle}"
                            print(f"舵机2控制成功，响应: {response}")
                            return response
                        else:
                            print("舵机2控制失败")
                            return "ERROR:SERVO2_CONTROL_FAILED"
                    else:
                        print(f"无效角度: {angle}")
                        return "ERROR:INVALID_ANGLE"
                except (ValueError, IndexError) as e:
                    print(f"舵机2命令解析错误: {e}")
                    return "ERROR:SERVO2_PARSE_ERROR"
                    
            elif command.startswith("OLED:"):
                print("处理OLED显示命令")
                text = command[5:]  # 移除 "OLED:" 前缀
                print(f"OLED文本: '{text}'")
                self.display_text(text)
                response = f"OK:OLED_DISPLAY"
                print(f"OLED显示成功，响应: {response}")
                return response
                
            elif command == "OLED_CLEAR":
                print("处理OLED清除命令")
                self.clear_oled()
                response = "OK:OLED_CLEARED"
                print(f"OLED清除成功，响应: {response}")
                return response
                
            else:
                print(f"未知命令: '{command}'")
                return "ERROR:UNKNOWN_COMMAND"
                
        except Exception as e:
            print(f"命令处理异常: {e}")
            import traceback
            traceback.print_exc()
            return f"ERROR:COMMAND_PROCESSING:{str(e)}"
    
    def run_server(self):
        """运行服务器主循环"""
        print("=" * 60)
        print("🚀 启动树莓派蓝牙遥控器服务端")
        print("=" * 60)
        
        # 尝试设置蓝牙服务器
        self.setup_bluetooth_server()
        
        if not self.server_socket:
            print("❌ 蓝牙服务器设置失败")
            self.display_text("BT Setup Failed")
            return
        
        print("✅ 蓝牙服务器设置成功")
        print("")
        print("📱 连接步骤:")
        print("1. 在安卓设备上打开蓝牙设置")
        print("2. 搜索新设备，找到 'RaspberryPi-BT'")
        print("3. 点击配对 (PIN码: 0000 或自动确认)")
        print("4. 配对成功后，在App中点击'连接蓝牙'")
        print("5. 选择已配对的树莓派设备")
        print("")
        print("🔑 配对代理已启动，会自动处理PIN码确认")
        print("📱 如果出现密钥确认，请在手机上确认相同数字")
        print("")
        print("🔄 等待配对和连接中...")
        
        while self.is_running:
            try:
                if self.wait_for_connection():
                    print("🎉 蓝牙连接建立成功！")
                    print("🎮 可以开始使用遥控器功能")
                    
                    # 显示连接成功
                    self.display_text("Connected!\nReady")
                    
                    # 连接建立后的主循环
                    while self.is_running:
                        try:
                            # 设置接收超时，避免长时间阻塞
                            self.client_socket.settimeout(30.0)
                            
                            print("📡 等待接收命令...")
                            
                            # 接收数据
                            data = self.client_socket.recv(1024)
                            
                            if not data:
                                print("📱 客户端主动断开连接 (接收到空数据)")
                                break
                            
                            print(f"📥 接收到原始数据: {data}")
                            print(f"📏 数据长度: {len(data)} 字节")
                            
                            try:
                                decoded_data = data.decode('utf-8')
                                print(f"📝 解码后命令: '{decoded_data}'")
                            except UnicodeDecodeError as e:
                                print(f"❌ 数据解码失败: {e}")
                                print(f"原始字节: {data.hex()}")
                                response = "ERROR:DECODE_ERROR"
                                self.client_socket.send(response.encode('utf-8'))
                                continue
                                
                            # 处理命令
                            print("🔄 开始处理命令...")
                            response = self.process_command(decoded_data)
                            print(f"📤 准备发送响应: '{response}'")
                            
                            # 发送响应
                            response_bytes = response.encode('utf-8')
                            self.client_socket.send(response_bytes)
                            print(f"✅ 响应已发送: {len(response_bytes)} 字节")
                            print("-" * 50)
                            
                        except bluetooth.BluetoothError as e:
                            print(f"❌ 蓝牙通信错误: {e}")
                            break
                        except Exception as e:
                            print(f"⚠️  通信错误: {e}")
                            break
                    
                    # 关闭客户端连接
                    if self.client_socket:
                        try:
                            self.client_socket.close()
                        except:
                            pass
                        self.client_socket = None
                        
                    print("🔌 连接已断开")
                    self.display_text("Disconnected\nWaiting...")
                    
                else:
                    print("⚠️  等待连接失败，重试中...")
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                print("\n🛑 收到中断信号，服务器关闭中...")
                break
            except Exception as e:
                print(f"❌ 服务器运行错误: {e}")
                print("🔄 5秒后重试...")
                time.sleep(5)
    
    def cleanup(self):
        """清理资源"""
        self.is_running = False
        
        # 停止配对代理
        self.stop_pairing_agent()
        
        # 关闭蓝牙连接
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()
        
        # 重置舵机到中位
        try:
            self.servo1.value = 0
            self.servo2.value = 0
        except:
            pass
        
        # 清除显示
        self.clear_oled()
        self.display_text("Server Closed")
        
        print("🧹 清理完成")

def main():
    """主函数"""
    controller = RaspberryPiController()
    
    try:
        controller.run_server()
    except KeyboardInterrupt:
        print("\n接收到中断信号")
    finally:
        controller.cleanup()

if __name__ == "__main__":
    main()
