@echo off
echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install tkinterdnd2

echo Creating fonts directory...
mkdir "%LOCALAPPDATA%\Microsoft\Windows\Fonts" 2>nul

echo Downloading SF Pro Display fonts...
powershell -Command "& {Invoke-WebRequest -Uri 'https://devimages-cdn.apple.com/design/resources/download/SF-Pro.dmg' -OutFile 'sf-pro.zip'}"
powershell -Command "& {Expand-Archive sf-pro.zip -DestinationPath .\fonts -Force}"
xcopy /y "fonts\*.otf" "%LOCALAPPDATA%\Microsoft\Windows\Fonts"
reg add "HKCU\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" /v "SF Pro Display Regular (TrueType)" /t REG_SZ /d "%LOCALAPPDATA%\Microsoft\Windows\Fonts\SF-Pro-Display-Regular.otf" /f

del sf-pro.zip
rmdir /s /q fonts

echo.
echo Installation complete!
echo If you encountered any errors, please make sure Python is installed and added to your PATH
pause