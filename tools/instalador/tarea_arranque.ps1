<#
.SYNOPSIS
  Tarea "al iniciar sesion" del Setup (autoclave.iss, tarea opcional autoarranque).
.DESCRIPTION
  Mismo mecanismo y MISMO NOMBRE de tarea que tools\estacion\03_tarea_autoclave.ps1:
  accion, disparo (al iniciar sesion, sin retraso), ajustes (3 reintentos,
  1 minuto, IgnoreNew) y principal (interactivo, nivel limitado). Si despues se
  ejecuta el script 03, reemplaza esta tarea (mismo nombre): nunca quedan dos
  arranques.
  Diferencia unica, decidida el 22-oct: la cuenta no es 'operador' fija sino la
  que tiene la sesion abierta en la consola al instalar (el Setup corre elevado
  y $env:USERNAME podria ser el administrador que autorizo el UAC).
  El Setup lo copia a {tmp} y lo borra al terminar; no queda en la instalacion.
  EST-07 (tanda 17, DECISION SIN CONFIRMAR): el disparo pasa de 10 s de
  retraso (PT10S) a ninguno (PT0S), para acortar el tiempo con el escritorio
  de Windows expuesto; Autoclave.exe tapa enseguida las pantallas con la
  cubierta de arranque hasta que aparece la interfaz.
#>
param(
    [Parameter(Mandatory)][string]$Ejecutable,
    [string]$NombreTarea = 'Especifika Autoclave - Arranque',
    # E9 (tanda 9): con "Configurar este PC como estacion", la cuenta del inicio
    # automatico (DOMINIO\usuario), para que la tarea sea de esa misma cuenta
    [string]$Usuario
)
$ErrorActionPreference = 'Stop'

$principalUsuario = if ($Usuario) { $Usuario } else { (Get-CimInstance Win32_ComputerSystem).UserName }
if (-not $principalUsuario) {
    Write-Error 'No hay sesion de consola abierta: no se sabe para que cuenta crear la tarea.'
    exit 2
}

$accion   = New-ScheduledTaskAction -Execute $Ejecutable -WorkingDirectory (Split-Path -Parent $Ejecutable)
$disparo  = New-ScheduledTaskTrigger -AtLogOn -User $principalUsuario
$disparo.Delay = 'PT0S'    # EST-07: sin retraso
$ajustes  = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
              -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $principalUsuario -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $NombreTarea -Action $accion -Trigger $disparo -Settings $ajustes `
    -Principal $principal -Description 'Lanza Autoclave.exe al iniciar sesion (Setup de Autoclave).' -Force | Out-Null
exit 0
