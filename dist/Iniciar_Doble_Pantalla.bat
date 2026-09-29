@echo off
REM Levanta las dos ventanas del PC de doble pantalla (una por puerta).
REM No hace falta esperar entre una y otra: la ventana de la puerta 2
REM espera sola a que el backend de la puerta 1 quede disponible.
cd /d "%~dp0"
start "" "AutoclaveUI.exe" --door 1
start "" "AutoclaveUI.exe" --door 2
