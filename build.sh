#!/usr/bin/env bash
# Gera o executável para o SISTEMA ATUAL (Linux/macOS).
# Para Windows, use build.bat em uma máquina Windows (ou o GitHub Actions).
set -euo pipefail

python -m pip install -r requirements-build.txt
pyinstaller --noconfirm --clean monitor.spec

echo ""
echo "Executável gerado em: dist/monitor-diarios"
echo "Teste: ./dist/monitor-diarios healthcheck"
