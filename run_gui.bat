@echo off
echo Starting HDR Video Processor...
python hdr_gui.py
if errorlevel 1 (
    echo Error running the application
    echo Please make sure Python is installed and dependencies are set up
    echo Run install_dependencies.bat if you haven't already
    pause
)