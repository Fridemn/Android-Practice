package com.example.remotecontrol

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.app.ActivityCompat
import com.example.remotecontrol.ui.theme.RemoteControlTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.io.IOException
import java.util.*

class MainActivity : ComponentActivity() {
    private var bluetoothSocket: BluetoothSocket? = null
    private var wifiSocket: java.net.Socket? = null
    private val bluetoothAdapter: BluetoothAdapter? = BluetoothAdapter.getDefaultAdapter()
    
    // 树莓派配置
    private val raspberryPiName = "RaspberryPi-BT" // 树莓派蓝牙设备名
    private val raspberryPiIP = "192.168.1.XXX" // 替换为树莓派IP地址  
    private val wifiPort = 8888
    private val uuid: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    
    // 连接状态 - 使用 mutableStateOf 以便 Compose 可以观察
    private var _isBluetoothConnected = mutableStateOf(false)
    private var _isWifiConnected = mutableStateOf(false)
    
    private val isBluetoothConnected: Boolean get() = _isBluetoothConnected.value
    private val isWifiConnected: Boolean get() = _isWifiConnected.value
    
    private val requestPermissions = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        // 处理权限结果
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        
        // 请求蓝牙权限
        requestBluetoothPermissions()
        
        setContent {
            RemoteControlTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    RaspberryPiControlApp(
                        modifier = Modifier.padding(innerPadding),
                        onSendCommand = { command -> sendBluetoothCommand(command) },
                        isBluetoothConnected = _isBluetoothConnected.value,
                        isWifiConnected = _isWifiConnected.value,
                        onConnect = {
                            CoroutineScope(Dispatchers.IO).launch {
                                connectToBluetooth()
                            }
                        },
                        onDisconnect = {
                            CoroutineScope(Dispatchers.IO).launch {
                                try {
                                    bluetoothSocket?.close()
                                    wifiSocket?.close()
                                    _isBluetoothConnected.value = false
                                    _isWifiConnected.value = false
                                    
                                    runOnUiThread {
                                        Toast.makeText(this@MainActivity, "连接已断开", Toast.LENGTH_SHORT).show()
                                    }
                                } catch (e: Exception) {
                                    e.printStackTrace()
                                }
                            }
                        }
                    )
                }
            }
        }
    }
    
    private fun requestBluetoothPermissions() {
        requestPermissions.launch(
            arrayOf(
                Manifest.permission.BLUETOOTH,
                Manifest.permission.BLUETOOTH_ADMIN,
                Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.BLUETOOTH_SCAN
            )
        )
    }
    
    private fun connectToBluetooth(): Boolean {
        try {
            if (ActivityCompat.checkSelfPermission(
                    this,
                    Manifest.permission.BLUETOOTH_CONNECT
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                runOnUiThread {
                    Toast.makeText(this, "蓝牙权限未授予", Toast.LENGTH_SHORT).show()
                }
                return false
            }
            
            // 检查蓝牙是否可用
            if (bluetoothAdapter == null) {
                runOnUiThread {
                    Toast.makeText(this, "设备不支持蓝牙", Toast.LENGTH_SHORT).show()
                }
                return false
            }
            
            if (!bluetoothAdapter.isEnabled) {
                runOnUiThread {
                    Toast.makeText(this, "请先开启蓝牙", Toast.LENGTH_SHORT).show()
                }
                return false
            }
            
            // 查找已配对的树莓派设备
            val pairedDevices = bluetoothAdapter.bondedDevices
            var targetDevice: BluetoothDevice? = null
            
            println("🔍 搜索已配对设备...")
            for (device in pairedDevices) {
                println("📱 发现设备: ${device.name} (${device.address})")
                if (device.name == raspberryPiName) {
                    targetDevice = device
                    println("✅ 找到目标设备: ${device.name}")
                    break
                }
            }
            
            if (targetDevice == null) {
                println("❌ 未找到已配对的 $raspberryPiName 设备")
                runOnUiThread {
                    Toast.makeText(this, "未找到已配对的 $raspberryPiName 设备，请先在蓝牙设置中配对", Toast.LENGTH_LONG).show()
                }
                return false
            }
            
            println("🔗 准备连接到设备: ${targetDevice.name} (${targetDevice.address})")
            runOnUiThread {
                Toast.makeText(this, "正在连接 ${targetDevice.name}...", Toast.LENGTH_SHORT).show()
            }
            
            // 如果已有连接，先关闭
            try {
                bluetoothSocket?.close()
                println("🔒 已关闭旧连接")
            } catch (e: Exception) {
                println("⚠️ 关闭旧连接时出现异常: ${e.message}")
            }
            
            // 尝试多种连接方法
            var connected = false
            
            // 方法1: 标准RFCOMM连接
            try {
                println("🔄 尝试方法1: 标准RFCOMM连接")
                bluetoothSocket = targetDevice.createRfcommSocketToServiceRecord(uuid)
                bluetoothSocket?.connect()
                
                if (bluetoothSocket?.isConnected == true) {
                    connected = true
                    println("✅ 标准RFCOMM连接成功")
                }
            } catch (e: Exception) {
                println("❌ 标准RFCOMM连接失败: ${e.message}")
                try {
                    bluetoothSocket?.close()
                } catch (closeException: Exception) {
                    // 忽略关闭异常
                }
            }
            
            // 方法2: 反射连接（如果方法1失败）
            if (!connected) {
                try {
                    println("🔄 尝试方法2: 反射连接")
                    val method = targetDevice.javaClass.getMethod("createRfcommSocket", Int::class.javaPrimitiveType)
                    bluetoothSocket = method.invoke(targetDevice, 1) as BluetoothSocket
                    bluetoothSocket?.connect()
                    
                    if (bluetoothSocket?.isConnected == true) {
                        connected = true
                        println("✅ 反射连接成功")
                    }
                } catch (e: Exception) {
                    println("❌ 反射连接失败: ${e.message}")
                    try {
                        bluetoothSocket?.close()
                    } catch (closeException: Exception) {
                        // 忽略关闭异常
                    }
                }
            }
            
            // 方法3: 不安全连接（如果方法2失败）
            if (!connected) {
                try {
                    println("🔄 尝试方法3: 不安全连接")
                    bluetoothSocket = targetDevice.createInsecureRfcommSocketToServiceRecord(uuid)
                    bluetoothSocket?.connect()
                    
                    if (bluetoothSocket?.isConnected == true) {
                        connected = true
                        println("✅ 不安全连接成功")
                    }
                } catch (e: Exception) {
                    println("❌ 不安全连接失败: ${e.message}")
                    try {
                        bluetoothSocket?.close()
                    } catch (closeException: Exception) {
                        // 忽略关闭异常
                    }
                }
            }
            
            if (connected) {
                _isBluetoothConnected.value = true
                println("🎉 蓝牙连接最终成功！")
                
                runOnUiThread {
                    Toast.makeText(this, "蓝牙连接成功！", Toast.LENGTH_SHORT).show()
                }
                
                // 发送测试命令确认连接
                try {
                    bluetoothSocket?.let { socket ->
                        // 等待服务端欢迎消息
                        socket.inputStream?.let { inputStream ->
                            val welcomeBuffer = ByteArray(1024)
                            
                            try {
                                // 使用一个线程来处理超时读取
                                var welcomeMsg: String? = null
                                val readThread = Thread {
                                    try {
                                        val bytesRead = inputStream.read(welcomeBuffer)
                                        if (bytesRead > 0) {
                                            welcomeMsg = String(welcomeBuffer, 0, bytesRead).trim()
                                        }
                                    } catch (e: Exception) {
                                        println("读取欢迎消息异常: ${e.message}")
                                    }
                                }
                                
                                readThread.start()
                                readThread.join(5000) // 等待最多5秒
                                
                                if (welcomeMsg != null) {
                                    println("📥 收到服务端欢迎消息: '$welcomeMsg'")
                                    
                                    if (welcomeMsg == "WELCOME_RPi") {
                                        // 发送握手响应
                                        socket.outputStream?.let { outputStream ->
                                            val handshakeMsg = "PING"
                                            outputStream.write(handshakeMsg.toByteArray())
                                            outputStream.flush()
                                            println("📤 发送握手响应: $handshakeMsg")
                                            
                                            // 等待握手确认
                                            var confirmMsg: String? = null
                                            val confirmThread = Thread {
                                                try {
                                                    val confirmBuffer = ByteArray(1024)
                                                    val confirmBytes = inputStream.read(confirmBuffer)
                                                    if (confirmBytes > 0) {
                                                        confirmMsg = String(confirmBuffer, 0, confirmBytes).trim()
                                                    }
                                                } catch (e: Exception) {
                                                    println("读取握手确认异常: ${e.message}")
                                                }
                                            }
                                            
                                            confirmThread.start()
                                            confirmThread.join(3000) // 等待最多3秒
                                            
                                            if (confirmMsg != null) {
                                                println("📥 收到握手确认: '$confirmMsg'")
                                                
                                                if (confirmMsg == "HANDSHAKE_OK") {
                                                    println("🤝 握手成功完成")
                                                } else {
                                                    println("⚠️ 握手确认不匹配，但继续连接")
                                                }
                                            } else {
                                                println("⚠️ 握手确认超时")
                                            }
                                        }
                                    }
                                } else {
                                    println("⚠️ 未收到欢迎消息，直接发送测试PING")
                                    socket.outputStream?.let { outputStream ->
                                        val testCommand = "PING"
                                        outputStream.write(testCommand.toByteArray())
                                        outputStream.flush()
                                        println("📤 发送连接测试命令: $testCommand")
                                    }
                                }
                                
                            } catch (e: Exception) {
                                println("⚠️ 握手超时，发送简单测试命令")
                                socket.outputStream?.let { outputStream ->
                                    val testCommand = "PING"
                                    outputStream.write(testCommand.toByteArray())
                                    outputStream.flush()
                                    println("📤 发送连接测试命令: $testCommand")
                                }
                            }
                        }
                    }
                } catch (e: Exception) {
                    println("⚠️ 握手过程出现异常: ${e.message}")
                }
                
                return true
            } else {
                println("❌ 所有连接方法都失败了")
                _isBluetoothConnected.value = false
                
                runOnUiThread {
                    Toast.makeText(this, "蓝牙连接失败，所有方法都无效", Toast.LENGTH_LONG).show()
                }
                
                // 蓝牙连接失败，尝试WiFi连接
                connectToWiFi()
                return false
            }
            
        } catch (e: Exception) {
            e.printStackTrace()
            _isBluetoothConnected.value = false
            
            println("❌ 连接过程中出现严重错误: ${e.message}")
            runOnUiThread {
                Toast.makeText(this, "连接错误: ${e.message}", Toast.LENGTH_SHORT).show()
            }
            return false
        }
    }
    
    private fun connectToWiFi() {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                wifiSocket = java.net.Socket(raspberryPiIP, wifiPort)
                _isWifiConnected.value = true
                
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "已通过WiFi连接", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                e.printStackTrace()
                _isWifiConnected.value = false
                
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "WiFi连接失败: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
    
    private fun sendBluetoothCommand(command: String) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                var success = false
                
                // 优先尝试蓝牙连接
                if (isBluetoothConnected && bluetoothSocket?.isConnected == true) {
                    try {
                        bluetoothSocket?.outputStream?.let { outputStream ->
                            println("🔄 准备发送命令: '$command'")
                            println("📏 命令长度: ${command.length} 字符")
                            println("📝 命令字节: ${command.toByteArray().contentToString()}")
                            
                            outputStream.write(command.toByteArray())
                            outputStream.flush()
                            println("📤 命令已发送")
                            
                            // 尝试读取响应
                            bluetoothSocket?.inputStream?.let { inputStream ->
                                try {
                                    val response = ByteArray(1024)
                                    val bytesRead = inputStream.read(response)
                                    if (bytesRead > 0) {
                                        val responseStr = String(response, 0, bytesRead)
                                        println("📥 服务端响应: '$responseStr' (${bytesRead} 字节)")
                                        
                                        runOnUiThread {
                                            Toast.makeText(this@MainActivity, "收到响应: $responseStr", Toast.LENGTH_SHORT).show()
                                        }
                                    } else {
                                        println("⚠️  未收到响应数据")
                                    }
                                } catch (e: Exception) {
                                    println("❌ 读取响应失败: ${e.message}")
                                }
                            }
                            
                            success = true
                            runOnUiThread {
                                Toast.makeText(this@MainActivity, "蓝牙命令发送成功", Toast.LENGTH_SHORT).show()
                            }
                        }
                    } catch (e: IOException) {
                        e.printStackTrace()
                        _isBluetoothConnected.value = false
                        runOnUiThread {
                            Toast.makeText(this@MainActivity, "蓝牙发送失败: ${e.message}", Toast.LENGTH_SHORT).show()
                        }
                    }
                }
                
                // 如果蓝牙发送失败，尝试WiFi连接
                if (!success && isWifiConnected && wifiSocket?.isConnected == true) {
                    try {
                        wifiSocket?.outputStream?.let { outputStream ->
                            outputStream.write(command.toByteArray())
                            outputStream.flush()
                            success = true
                            runOnUiThread {
                                Toast.makeText(this@MainActivity, "WiFi命令发送成功", Toast.LENGTH_SHORT).show()
                            }
                        }
                    } catch (e: IOException) {
                        e.printStackTrace()
                        _isWifiConnected.value = false
                        runOnUiThread {
                            Toast.makeText(this@MainActivity, "WiFi发送失败: ${e.message}", Toast.LENGTH_SHORT).show()
                        }
                    }
                }
                
                // 如果都没有连接，尝试建立连接
                if (!success) {
                    runOnUiThread {
                        Toast.makeText(this@MainActivity, "无可用连接，正在尝试重新连接...", Toast.LENGTH_SHORT).show()
                    }
                    
                    if (connectToBluetooth()) {
                        // 连接成功后重新发送命令
                        try {
                            bluetoothSocket?.outputStream?.let { outputStream ->
                                outputStream.write(command.toByteArray())
                                outputStream.flush()
                                success = true
                                runOnUiThread {
                                    Toast.makeText(this@MainActivity, "重连后命令发送成功", Toast.LENGTH_SHORT).show()
                                }
                            }
                        } catch (e: IOException) {
                            e.printStackTrace()
                            runOnUiThread {
                                Toast.makeText(this@MainActivity, "重连后发送失败: ${e.message}", Toast.LENGTH_SHORT).show()
                            }
                        }
                    }
                }
                
                if (!success) {
                    runOnUiThread {
                        Toast.makeText(this@MainActivity, "命令发送失败，请检查连接", Toast.LENGTH_LONG).show()
                    }
                }
                
            } catch (e: Exception) {
                e.printStackTrace()
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "发送错误: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        try {
            bluetoothSocket?.close()
            wifiSocket?.close()
        } catch (e: IOException) {
            e.printStackTrace()
        }
    }
}

@Composable
fun RaspberryPiControlApp(
    modifier: Modifier = Modifier,
    onSendCommand: (String) -> Unit,
    isBluetoothConnected: Boolean,
    isWifiConnected: Boolean,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit
) {
    val context = LocalContext.current
    var servo1Angle by remember { mutableStateOf(90) }
    var servo2Angle by remember { mutableStateOf(90) }
    var oledText by remember { mutableStateOf("Hello RPi!") }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // 标题
        Text(
            text = "树莓派遥控器",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(bottom = 16.dp)
        )

        // 蓝牙连接状态
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 16.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (isBluetoothConnected || isWifiConnected) 
                    MaterialTheme.colorScheme.primaryContainer 
                else 
                    MaterialTheme.colorScheme.errorContainer
            )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = if (isBluetoothConnected || isWifiConnected) Icons.Default.CheckCircle else Icons.Default.Close,
                    contentDescription = null,
                    modifier = Modifier.padding(end = 8.dp)
                )
                Text(
                    text = when {
                        isBluetoothConnected -> "蓝牙已连接"
                        isWifiConnected -> "WiFi已连接"
                        else -> "未连接"
                    },
                    fontWeight = FontWeight.Medium
                )
                Spacer(modifier = Modifier.weight(1f))
                Button(
                    onClick = { 
                        if (isBluetoothConnected || isWifiConnected) {
                            onDisconnect()
                        } else {
                            onConnect()
                        }
                    }
                ) {
                    Text(if (isBluetoothConnected || isWifiConnected) "断开" else "连接")
                }
            }
        }

        // 舵机1控制
        ServoControlCard(
            title = "舵机1控制",
            angle = servo1Angle,
            onAngleChange = { newAngle ->
                servo1Angle = newAngle
                onSendCommand("SERVO1:$newAngle")
            }
        )

        Spacer(modifier = Modifier.height(16.dp))

        // 舵机2控制
        ServoControlCard(
            title = "舵机2控制",
            angle = servo2Angle,
            onAngleChange = { newAngle ->
                servo2Angle = newAngle
                onSendCommand("SERVO2:$newAngle")
            }
        )

        Spacer(modifier = Modifier.height(16.dp))

        // OLED显示控制
        Card(
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(
                modifier = Modifier.padding(16.dp)
            ) {
                Text(
                    text = "OLED显示控制",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.padding(bottom = 16.dp)
                )
                
                OutlinedTextField(
                    value = oledText,
                    onValueChange = { oledText = it },
                    label = { Text("显示文本") },
                    modifier = Modifier.fillMaxWidth()
                )
                
                Spacer(modifier = Modifier.height(16.dp))
                
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    Button(
                        onClick = {
                            onSendCommand("OLED:$oledText")
                            Toast.makeText(context, "发送文本到OLED", Toast.LENGTH_SHORT).show()
                        }
                    ) {
                        Text("发送文本")
                    }
                    
                    Button(
                        onClick = {
                            onSendCommand("OLED_CLEAR")
                            Toast.makeText(context, "清除OLED显示", Toast.LENGTH_SHORT).show()
                        }
                    ) {
                        Text("清除显示")
                    }
                }
                
                Spacer(modifier = Modifier.height(16.dp))
                
                // 预设文本按钮
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    Button(
                        onClick = {
                            val text = "温度: 25°C"
                            oledText = text
                            onSendCommand("OLED:$text")
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("温度")
                    }
                    
                    Spacer(modifier = Modifier.width(8.dp))
                    
                    Button(
                        onClick = {
                            val text = "时间: ${java.text.SimpleDateFormat("HH:mm").format(java.util.Date())}"
                            oledText = text
                            onSendCommand("OLED:$text")
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("时间")
                    }
                    
                    Spacer(modifier = Modifier.width(8.dp))
                    
                    Button(
                        onClick = {
                            val text = "状态: 正常"
                            oledText = text
                            onSendCommand("OLED:$text")
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("状态")
                    }
                }
            }
        }
    }
}

@Composable
fun ServoControlCard(
    title: String,
    angle: Int,
    onAngleChange: (Int) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Text(
                text = title,
                fontSize = 18.sp,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(
                    onClick = {
                        if (angle > 0) {
                            onAngleChange(angle - 10)
                        }
                    }
                ) {
                    Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "减少角度")
                }
                
                Slider(
                    value = angle.toFloat(),
                    onValueChange = { onAngleChange(it.toInt()) },
                    valueRange = 0f..180f,
                    modifier = Modifier.weight(1f)
                )
                
                IconButton(
                    onClick = {
                        if (angle < 180) {
                            onAngleChange(angle + 10)
                        }
                    }
                ) {
                    Icon(Icons.Default.KeyboardArrowRight, contentDescription = "增加角度")
                }
            }
            
            Text(
                text = "当前角度: ${angle}°",
                modifier = Modifier.align(Alignment.CenterHorizontally)
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            // 快速角度设置按钮
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                Button(
                    onClick = { onAngleChange(0) },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("0°")
                }
                
                Spacer(modifier = Modifier.width(4.dp))
                
                Button(
                    onClick = { onAngleChange(90) },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("90°")
                }
                
                Spacer(modifier = Modifier.width(4.dp))
                
                Button(
                    onClick = { onAngleChange(180) },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("180°")
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun RaspberryPiControlPreview() {
    RemoteControlTheme {
        RaspberryPiControlApp(
            onSendCommand = {},
            isBluetoothConnected = false,
            isWifiConnected = false,
            onConnect = {},
            onDisconnect = {}
        )
    }
}