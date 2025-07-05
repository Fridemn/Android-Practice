#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
蓝牙配对助手
自动处理PIN码和配对请求
"""

import subprocess
import time
import threading
import signal
import sys

class BluetoothPairingHelper:
    def __init__(self):
        self.running = True
        self.pin_code = "0000"  # 默认PIN码
        
    def run_command(self, cmd):
        """执行系统命令"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def setup_bluetooth(self):
        """设置蓝牙为配对模式"""
        print("🔧 设置蓝牙配对模式...")
        
        commands = [
            "sudo bluetoothctl power on",
            "sudo bluetoothctl pairable on", 
            "sudo bluetoothctl discoverable on",
            "sudo hciconfig hci0 piscan",
            "sudo hciconfig hci0 sspmode 1"  # 启用SSP模式
        ]
        
        for cmd in commands:
            success, stdout, stderr = self.run_command(cmd)
            if not success:
                print(f"⚠️  命令失败: {cmd}")
                print(f"错误: {stderr}")
        
        print("✅ 蓝牙已设置为配对模式")
    
    def monitor_pairing_requests(self):
        """监控配对请求"""
        print("👂 开始监控配对请求...")
        print("📱 请在安卓设备上搜索并尝试配对 'RaspberryPi-BT'")
        print("🔑 如果需要PIN码，将自动使用: 0000")
        print("")
        
        # 启动bluetoothctl监控
        try:
            process = subprocess.Popen(
                ["sudo", "bluetoothctl"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 发送初始命令
            process.stdin.write("agent on\n")
            process.stdin.write("default-agent\n")
            process.stdin.flush()
            
            while self.running:
                try:
                    # 读取输出
                    output = process.stdout.readline()
                    if output:
                        output = output.strip()
                        print(f"📟 {output}")
                        
                        # 检查各种配对请求
                        if "Request PIN code" in output:
                            print(f"🔑 收到PIN码请求，发送: {self.pin_code}")
                            process.stdin.write(f"{self.pin_code}\n")
                            process.stdin.flush()
                            
                        elif "Confirm passkey" in output:
                            # 提取密钥
                            import re
                            passkey_match = re.search(r'Confirm passkey (\d+)', output)
                            if passkey_match:
                                passkey = passkey_match.group(1)
                                print(f"🔑 收到密钥确认请求: {passkey}")
                                print("📱 请在安卓设备上确认相同的密钥!")
                                
                            print("✅ 自动确认配对密钥")
                            process.stdin.write("yes\n")
                            process.stdin.flush()
                            
                        elif "Request confirmation" in output:
                            print("🔑 收到配对确认请求")
                            print("✅ 自动确认配对")
                            process.stdin.write("yes\n")
                            process.stdin.flush()
                            
                        elif "[agent] Confirm passkey" in output:
                            # 处理代理确认请求
                            import re
                            passkey_match = re.search(r'Confirm passkey (\d+)', output)
                            if passkey_match:
                                passkey = passkey_match.group(1)
                                print(f"🔑 代理密钥确认: {passkey}")
                                print("📱 请在安卓设备上确认相同的密钥!")
                            process.stdin.write("yes\n")
                            process.stdin.flush()
                            
                        elif "Authorize service" in output:
                            print("✅ 授权服务")
                            process.stdin.write("yes\n")
                            process.stdin.flush()
                            
                        elif "Pairing successful" in output:
                            print("🎉 配对成功！")
                            
                        elif "Failed to pair" in output:
                            print("❌ 配对失败，请重试")
                            
                        elif "Request canceled" in output:
                            print("⚠️  配对请求被取消，可能是超时或用户取消")
                            
                except Exception as e:
                    if self.running:
                        print(f"读取输出错误: {e}")
                    break
                    
        except KeyboardInterrupt:
            print("\n🛑 停止监控")
        except Exception as e:
            print(f"❌ 监控错误: {e}")
        finally:
            try:
                process.terminate()
            except:
                pass
    
    def auto_accept_pairing(self):
        """自动接受配对的另一种方法"""
        print("🤖 启动自动配对脚本...")
        
        script = '''
        bluetoothctl << EOF
        agent on
        default-agent
        pairable on
        discoverable on
        
        # 等待配对请求
        EOF
        '''
        
        # 使用expect脚本自动处理配对
        expect_script = f'''
        #!/usr/bin/expect -f
        spawn sudo bluetoothctl
        expect "Agent registered"
        send "agent on\\n"
        send "default-agent\\n"
        send "pairable on\\n"
        send "discoverable on\\n"
        
        # 处理PIN码请求
        expect {{
            "Request PIN code*" {{
                send "{self.pin_code}\\n"
                exp_continue
            }}
            "Confirm passkey*" {{
                send "yes\\n"
                exp_continue
            }}
            "Authorize service*" {{
                send "yes\\n"
                exp_continue
            }}
            timeout {{
                exp_continue
            }}
        }}
        '''
        
        # 写入expect脚本
        with open("/tmp/bluetooth_pair.exp", "w") as f:
            f.write(expect_script)
        
        subprocess.run(["chmod", "+x", "/tmp/bluetooth_pair.exp"])
        
        # 检查是否安装了expect
        success, _, _ = self.run_command("which expect")
        if success:
            print("使用expect脚本自动处理配对...")
            subprocess.run(["/tmp/bluetooth_pair.exp"])
        else:
            print("expect未安装，使用手动监控模式")
            self.monitor_pairing_requests()
    
    def signal_handler(self, signum, frame):
        """处理中断信号"""
        print("\n🛑 收到停止信号，正在退出...")
        self.running = False
        sys.exit(0)

def main():
    print("=" * 60)
    print("🔵 蓝牙配对助手")
    print("=" * 60)
    print("")
    
    helper = BluetoothPairingHelper()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, helper.signal_handler)
    signal.signal(signal.SIGTERM, helper.signal_handler)
    
    try:
        # 设置蓝牙
        helper.setup_bluetooth()
        
        print("选择配对模式:")
        print("1. 自动监控配对请求（推荐）")
        print("2. 手动处理")
        print("3. 仅设置配对模式后退出")
        
        choice = input("请选择 (1/2/3): ").strip()
        
        if choice == "1":
            helper.monitor_pairing_requests()
        elif choice == "2":
            print("🔧 蓝牙已设置为配对模式")
            print("📱 请手动在安卓设备上配对")
            print("🔑 PIN码: 0000")
            input("按Enter键退出...")
        elif choice == "3":
            print("✅ 蓝牙配对模式已设置，可以手动配对")
            print("🔑 如果需要PIN码，请使用: 0000")
        else:
            print("❌ 无效选择")
            
    except KeyboardInterrupt:
        print("\n🛑 用户中断")
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    main()
