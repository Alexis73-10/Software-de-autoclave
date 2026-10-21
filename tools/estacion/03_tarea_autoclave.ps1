<#
.SYNOPSIS
  Paso 3: tarea programada que lanza Autoclave.exe al iniciar sesion el operador.
.DESCRIPTION
  Planeacion seccion 3.2 y 8: tarea "al iniciar sesion" con reintento (3 veces,
  1 minuto). Se eligio la tarea y no Shell Launcher porque esta funciona en
  cualquier edicion (Shell Launcher exige Pro/Enterprise/Education y la edicion
  del PC industrial no esta confirmada - plan seccion 10.1).
  La tarea corre con la cuenta del operador en modo interactivo (las pantallas
  QML necesitan el escritorio de esa sesion), con nivel limitado.
  Idempotente: si la tarea existe con la misma accion, no se toca; si difiere, se
  reemplaza. Inverso: 03_revertir_tarea_autoclave.ps1.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Usuario = 'operador',
    [string]$Ejecutable = (Join-Path $env:ProgramFiles 'Especifika\Autoclave\Autoclave.exe'),
    [string]$NombreTarea = 'Especifika Autoclave - Arranque'
)
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '03_tarea_autoclave'
Write-Log "== Inicio $Paso (usuario=$Usuario, exe=$Ejecutable, WhatIf=$WhatIfPreference) =="

if (-not (Test-Path -LiteralPath $Ejecutable)) {
    Write-Log "ATENCION: no existe $Ejecutable. La tarea se crea igual; instalar el exe antes de reiniciar." 'WARN'
}
$principalUsuario = "$env:COMPUTERNAME\$Usuario"

$existente = Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
if ($existente) {
    $acc = $existente.Actions | Select-Object -First 1
    if ($acc.Execute -eq $Ejecutable -and $existente.Principal.UserId -like "*$Usuario") {
        Write-Log "Sin cambio: la tarea '$NombreTarea' ya existe con la misma accion y usuario."
        Write-Log "== Fin $Paso =="
        return
    }
    Write-Log "La tarea '$NombreTarea' existe con otra configuracion: se reemplaza."
}

$accion   = New-ScheduledTaskAction -Execute $Ejecutable -WorkingDirectory (Split-Path -Parent $Ejecutable)
$disparo  = New-ScheduledTaskTrigger -AtLogOn -User $principalUsuario
$disparo.Delay = 'PT10S'
$ajustes  = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
              -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $principalUsuario -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($NombreTarea, 'Registrar tarea programada al iniciar sesion')) {
    Register-ScheduledTask -TaskName $NombreTarea -Action $accion -Trigger $disparo -Settings $ajustes `
        -Principal $principal -Description 'Lanza Autoclave.exe al iniciar sesion el operador (W1, tanda 6).' -Force | Out-Null
    Write-Log "Tarea '$NombreTarea' registrada."
}
Write-Log "== Fin $Paso =="
