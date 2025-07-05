@echo off
echo Simple Android Build Script
echo ===========================

echo Building Android app without SDK requirements...

REM Clean project
echo Cleaning project...
call gradlew.bat clean
if errorlevel 1 (
    echo Clean failed
    pause
    exit /b 1
)

REM Build debug version
echo Building debug version...
call gradlew.bat assembleDebug
if errorlevel 1 (
    echo Build failed
    echo.
    echo Possible issues:
    echo - Java/JDK not installed or not in PATH
    echo - Gradle wrapper not executable
    echo - Missing dependencies
    echo.
    pause
    exit /b 1
)

echo Build successful!
echo.
echo APK location: app\build\outputs\apk\debug\app-debug.apk
echo.
echo To install on device:
echo 1. Enable USB debugging on your Android device
echo 2. Connect device via USB
echo 3. Copy APK to device and install manually, or
echo 4. Use adb install command if you have Android SDK

echo.
echo Next steps:
echo 1. Install the APK on your Android device
echo 2. Ensure Bluetooth is enabled
echo 3. Pair your device with RaspberryPi-BT
echo 4. Start the Raspberry Pi bluetooth service
echo 5. Use the app to connect and control

echo.
pause
