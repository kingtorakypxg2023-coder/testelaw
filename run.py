"""Ponto de entrada do executável (PyInstaller).

Mantém a lógica em `src/cli.py`; este arquivo existe porque o PyInstaller
empacota a partir de um script, não de um módulo.
"""
from src.cli import main

if __name__ == "__main__":
    main()
