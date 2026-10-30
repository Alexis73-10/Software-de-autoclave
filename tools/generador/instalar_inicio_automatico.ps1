# tools/generador/instalar_inicio_automatico.ps1
#
# Inicio automático del generador de códigos con Windows (G1, tanda 2).
# Crea una tarea programada "Especifika Generador de Codigos" que arranca
# GeneradorCodigos.exe --sin-navegador AL INICIAR EL EQUIPO (sin esperar a que
# alguien inicie sesión), como SYSTEM, sin ventana, y lo reinicia si se cae.
# El navegador lo abre cada usuario con la URL (o con un doble clic al .exe,
# que si el servidor ya corre solo abre el navegador).
#
# Ejecutar en PowerShell COMO ADMINISTRADOR:
#   powershell -ExecutionPolicy Bypass -File .\instalar_inicio_automatico.ps1 -Exe "C:\Especifika\GeneradorCodigos.exe"
#
# Nota: SYSTEM usa C:\ProgramData\Especifika\Generador\ como carpeta de datos
# (la misma que un usuario normal), así que la base es una sola.

param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [string]$Nombre = "Especifika Generador de Codigos"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $Exe)) { throw "No existe el ejecutable: $Exe" }

$accion = New-ScheduledTaskAction -Execute $Exe -Argument "--sin-navegador" `
    -WorkingDirectory (Split-Path $Exe)
$disparador = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Limited
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $Nombre -Action $accion -Trigger $disparador `
    -Principal $principal -Settings $ajustes -Force | Out-Null
Write-Host "Tarea '$Nombre' creada. Se iniciará en el próximo arranque de Windows."
Write-Host "Para arrancarla ahora: Start-ScheduledTask -TaskName '$Nombre'"
