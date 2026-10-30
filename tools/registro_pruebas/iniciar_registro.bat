@echo off
rem Doble clic: arranca la app de registro de pruebas y abre el navegador.
rem Muestra la URL para el telefono (mismo Wi-Fi). Cerrar esta ventana detiene la app.
cd /d "%~dp0"
python lanzador_registro.py
pause
