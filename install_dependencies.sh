#!/bin/bash
echo "Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install tkinterdnd2

echo "Creating fonts directory..."
mkdir -p ~/.fonts

echo "Downloading SF Pro Display fonts..."
curl -L -o sf-pro.zip "https://devimages-cdn.apple.com/design/resources/download/SF-Pro.dmg"
unzip -j sf-pro.zip "*.otf" -d ~/.fonts/
rm sf-pro.zip

echo "Refreshing font cache..."
fc-cache -f -v

echo ""
echo "Installation complete!"
echo "If you encountered any errors, please make sure Python is installed"