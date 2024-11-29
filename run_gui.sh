#!/bin/bash
echo "Starting HDR Video Processor..."
python3 hdr_gui.py
if [ $? -ne 0 ]; then
    echo "Error running the application"
    echo "Please make sure Python is installed and dependencies are set up"
    echo "Run ./install_dependencies.sh if you haven't already"
    read -p "Press Enter to continue..."
fi