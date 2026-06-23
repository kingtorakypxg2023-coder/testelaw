@echo off
REM Gera o executavel para Windows (.exe).
python -m pip install -r requirements-build.txt || exit /b 1
pyinstaller --noconfirm --clean monitor.spec || exit /b 1

echo.
echo Executavel gerado em: dist\monitor-diarios.exe
echo Teste: dist\monitor-diarios.exe healthcheck
