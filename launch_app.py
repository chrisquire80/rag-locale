#!/usr/bin/env python3
"""
Launch RAG LOCALE Streamlit App
This script starts the Streamlit server and opens it in the browser
"""

import subprocess
import time
import webbrowser
import os
from pathlib import Path

def main():
    print("\n" + "="*80)
    print(" RAG LOCALE - STREAMLIT APP LAUNCHER".center(80))
    print("="*80)

    # Change to RAG LOCALE directory
    rag_locale_dir = Path(__file__).parent
    os.chdir(rag_locale_dir)

    print(f"\nDirectory: {rag_locale_dir}")
    print(f"App file: app_streamlit_real_docs.py")

    print("\n" + "-"*80)
    print("Starting Streamlit server...")
    print("-"*80 + "\n")

    # Start Streamlit
    try:
        # Use subprocess to launch streamlit
        process = subprocess.Popen(
            ["streamlit", "run", "app_streamlit_real_docs.py"],
            cwd=str(rag_locale_dir)
        )

        # Wait a moment for the server to start
        print("Waiting for server to start...", end="", flush=True)
        time.sleep(3)
        print(" READY!")

        # Try to open browser
        print("\nOpening http://localhost:8501 in browser...")
        webbrowser.open("http://localhost:8501")

        print("\n" + "="*80)
        print("STREAMLIT SERVER IS RUNNING")
        print("="*80)
        print("\nAccess the app at: http://localhost:8501")
        print("\nPress Ctrl+C to stop the server")
        print("="*80 + "\n")

        # Wait for process
        process.wait()

    except KeyboardInterrupt:
        print("\n\nShutting down...")
        process.terminate()
        print("Server stopped.")
    except Exception as e:
        print(f"\nError: {e}")
        print("\nAlternative: Run manually with:")
        print("  streamlit run app_streamlit_real_docs.py")
        return 1

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
