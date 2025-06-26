"""
Playwright installer for PyInstaller packaged applications
This module handles browser installation for packaged applications
"""
import os
import sys
import subprocess
from pathlib import Path

def install_playwright_browsers():
    """
    Install Playwright browsers for PyInstaller packaged applications
    """
    try:
        # Check if running as PyInstaller bundle
        if getattr(sys, 'frozen', False):
            print("Running as PyInstaller bundle - installing Playwright browsers...")
            
            # Get the directory where the executable is located
            app_dir = Path(sys.executable).parent
            browsers_dir = app_dir / "playwright_browsers"
            
            # Set environment variable for browser installation
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browsers_dir)
            
            # Install browsers if not already installed
            if not browsers_dir.exists() or not any(browsers_dir.iterdir()):
                print("Installing Playwright browsers...")
                subprocess.run([
                    sys.executable, "-m", "playwright", "install", "msedge"
                ], check=True)
                print("Playwright browsers installed successfully!")
            else:
                print("Playwright browsers already installed")
                
        else:
            print("Running as script - browsers should already be installed")
            
    except Exception as e:
        print(f"Error installing Playwright browsers: {e}")
        return False
    
    return True

def get_browser_executable_path():
    """
    Get the correct browser executable path for PyInstaller
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        app_dir = Path(sys.executable).parent
        browsers_dir = app_dir / "playwright_browsers"
        return str(browsers_dir)
    else:
        # Running as script - use default path
        return None
