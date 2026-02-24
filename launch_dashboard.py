#!/usr/bin/env python3
"""
RAG LOCALE Dashboard Launcher
Cross-platform script to launch the Streamlit dashboard with automatic setup
"""

import subprocess
import sys
import os
from pathlib import Path

def check_streamlit():
    """Check if Streamlit is installed"""
    try:
        import streamlit
        print(f"✓ Streamlit {streamlit.__version__} is installed")
        return True
    except ImportError:
        print("✗ Streamlit is not installed")
        return False


def install_streamlit():
    """Install Streamlit"""
    print("\nInstalling Streamlit...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit"])
        print("✓ Streamlit installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("✗ Failed to install Streamlit")
        return False


def launch_dashboard():
    """Launch the Streamlit dashboard"""
    dashboard_path = Path(__file__).parent / "app_dashboard.py"

    if not dashboard_path.exists():
        print(f"✗ Dashboard file not found: {dashboard_path}")
        return False

    print(f"\nLaunching dashboard from: {dashboard_path}")
    print("\nThe dashboard will open in your browser at http://localhost:8501")
    print("Press Ctrl+C to stop the server\n")
    print("="*80)

    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_path)])
        return True
    except KeyboardInterrupt:
        print("\n\n✓ Dashboard stopped by user")
        return True
    except Exception as e:
        print(f"✗ Error launching dashboard: {e}")
        return False


def main():
    """Main entry point"""
    print("\n" + "="*80)
    print("RAG LOCALE Dashboard Launcher")
    print("="*80 + "\n")

    # Check Python version
    if sys.version_info < (3, 10):
        print("✗ Python 3.10+ is required")
        print(f"  Current version: {sys.version}")
        sys.exit(1)

    print(f"✓ Python {sys.version.split()[0]} detected\n")

    # Check/install Streamlit
    if not check_streamlit():
        if not install_streamlit():
            sys.exit(1)

    # Launch dashboard
    print("\n" + "="*80)
    success = launch_dashboard()
    print("="*80)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
