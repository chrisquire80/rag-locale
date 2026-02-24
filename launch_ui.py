#!/usr/bin/env python
"""
RAG LOCALE - Streamlit Launcher with Error Handling
Questo script avvia Streamlit con configurazione timeout ottimale
"""

import sys
import subprocess
import os
from pathlib import Path

def main():
    print("\n" + "="*70)
    print("          RAG LOCALE - STREAMLIT UI LAUNCHER")
    print("="*70)
    print()

    # Verifica Python version
    print(f"[1/4] Python Version: {sys.version.split()[0]}")
    if sys.version_info < (3, 8):
        print("❌ ERRORE: Python 3.8+ richiesto!")
        return 1
    print("✅ Python OK\n")

    # Verifica dipendenze
    print("[2/4] Verificando dipendenze...")
    required_packages = ['streamlit', 'google', 'numpy', 'pandas']
    missing = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"    ✅ {package}")
        except ImportError:
            print(f"    ⚠️  {package} non trovato")
            missing.append(package)

    if missing:
        print(f"\n📦 Installazione pacchetti mancanti: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + missing)
        print("✅ Dipendenze installate\n")
    else:
        print("✅ Tutte le dipendenze OK\n")

    # Verifica vector store
    print("[3/4] Verificando vector store...")
    project_root = Path(__file__).parent
    vector_store = project_root / "data" / "vector_db" / "vector_store.pkl"

    if vector_store.exists():
        size_mb = vector_store.stat().st_size / (1024 * 1024)
        print(f"    ✅ Vector store trovato ({size_mb:.1f}MB)")
    else:
        print("    ℹ️  Vector store non ancora presente (sarà creato al primo avvio)")

    print()

    # Verifica configurazione
    print("[4/4] Verificando configurazione...")
    config_file = project_root / ".env"

    if config_file.exists():
        print("    ✅ .env file trovato")
        # Leggi e mostra se GEMINI_API_KEY è configurato
        with open(config_file) as f:
            env_content = f.read()
            if "GEMINI_API_KEY" in env_content:
                print("    ✅ GEMINI_API_KEY configurato")
            else:
                print("    ⚠️  GEMINI_API_KEY non trovato in .env")
    else:
        print("    ⚠️  .env file non trovato - verifica configurazione manualmente")

    print()
    print("="*70)
    print("✅ SYSTEM CHECK PASSED - Avvio Streamlit...")
    print("="*70)
    print()
    print("📋 ISTRUZIONI:")
    print("   • Browser si aprirà a http://localhost:8501")
    print("   • Se non si apre, vai manualmente a http://localhost:8501")
    print("   • Per fermare: Premi Ctrl+C")
    print()
    print("-"*70)
    print()

    # Cambia directory al project root
    os.chdir(project_root)

    # Avvia Streamlit
    try:
        subprocess.run(
            [
                sys.executable, "-m", "streamlit", "run",
                "src/app_ui.py",
                "--logger.level=info",
                "--client.showErrorDetails=true",
                "--client.toolbarMode=viewer"
            ],
            check=False
        )
    except KeyboardInterrupt:
        print("\n\n⏹️  Streamlit terminato dall'utente")
    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
