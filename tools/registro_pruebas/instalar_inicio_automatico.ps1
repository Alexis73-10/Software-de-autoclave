# tools/registro_pruebas/instalar_inicio_automatico.ps1
#
# Inicio automático de la app de registro de pruebas con Windows (F1, tanda 3).
# Crea una tarea programada "Especifika Registro de Pruebas" que arranca
# `python lanzador_registro.py --sin-navegador` AL INICIAR EL EQUIPO, sin ventana, y la
# reinicia si se cae. (Sin ejecutable: se indica el Python y la carpeta de la app.)
#
# Ejecutar en PowerShell COMO ADMINISTRADOR:
#   powershell -ExecutionPolicy Bypass -File .\instalar_inicio_automatico.ps1 -Python "C:\Python314\pythonw.exe"
# Nota: SYSTEM usa C:\ProgramData\Especifika\RegistroPruebas\ como carpeta de
# datos (la misma que un usuario normal), así que la base es una sola.

param(
    [Parameter(Mandatory = $true)][string]$Python,
    [string]$Nombre = "Especifika Registro de Pruebas"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Python)) { throw "No existe el intérprete: $Python" }
$carpeta = Split-Path -Parent $MyInvocation.MyCommand.Path
$lanzador = Join-Path $carpeta "lanzador_registro.py"
$accion = New-ScheduledTaskAction -Execute $Python -Argument "`"$lanzador`" --sin-navegador" `
    -WorkingDirectory $carpeta
$disparador = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Limited
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparador `
    -Principal $principal -Settings $ajustes -Force | Out-Null
Write-Host "Tarea '$Nombre' creada. Se iniciará en el próximo arranque de Windows."
Write-Host "Para arrancarla ahora: Start-ScheduledTask -TaskName '$Nombre'"
