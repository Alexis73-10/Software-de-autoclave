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
  EST-07 (tanda 17, DECISION SIN CONFIRMAR): disparo sin retraso (PT0S, antes
  PT10S). EST-08 (tanda 18): se retiro la cubierta de arranque; entre el
  inicio de sesion y la intro se ve el escritorio de la estacion (paso 07).
  -Ejecutable por defecto: RutaPrograma de HKLM\SOFTWARE\Especifika\Autoclave
  (vista de 64 bits, la escribe el Setup desde la tanda 17) + Autoclave.exe;
  sin esa clave, %ProgramFiles%\Especifika\Autoclave\Autoclave.exe como antes.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Usuario = 'operador',
    [string]$Ejecutable,
    [string]$NombreTarea = 'Especifika Autoclave - Arranque'
)
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '03_tarea_autoclave'

function Get-EjecutablePorDefecto {
    <# RutaPrograma de HKLM\SOFTWARE\Especifika\Autoclave (vista de 64 bits) +
       Autoclave.exe; sin la clave o el valor, la ruta de antes en Archivos de programa. #>
    $porDefecto = Join-Path $env:ProgramFiles 'Especifika\Autoclave\Autoclave.exe'
    try {
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry64')
        try {
            $clave = $base.OpenSubKey('SOFTWARE\Especifika\Autoclave', $false)
            if ($null -ne $clave) {
                try { $ruta = $clave.GetValue('RutaPrograma', $null) } finally { $clave.Close() }
                if ($ruta) { return (Join-Path ([string]$ruta) 'Autoclave.exe') }
            }
        } finally { $base.Close() }
    } catch {
        Write-Log "No se pudo leer RutaPrograma del registro: $($_.Exception.Message)" 'WARN'
    }
    return $porDefecto
}
if (-not $Ejecutable) { $Ejecutable = Get-EjecutablePorDefecto }
Write-Log "== Inicio $Paso (usuario=$Usuario, exe=$Ejecutable, WhatIf=$WhatIfPreference) =="

if (-not (Test-Path -LiteralPath $Ejecutable)) {
    Write-Log "ATENCION: no existe $Ejecutable. La tarea se crea igual; instalar el exe antes de reiniciar." 'WARN'
}
$principalUsuario = "$env:COMPUTERNAME\$Usuario"

$existente = Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
if ($existente) {
    $acc = $existente.Actions | Select-Object -First 1
    # V17-s2-03: una tarea anterior con retraso (PT10S) se reemplaza aunque la
    # accion y el usuario coincidan. Sin retraso = PT0S o vacio (Task Scheduler
    # puede guardar PT0S como "sin retraso").
    $trigExistente = $existente.Triggers | Select-Object -First 1
    $delayExistente = if ($null -ne $trigExistente) { "$($trigExistente.Delay)" } else { '' }
    $sinRetraso = ($delayExistente -eq '' -or $delayExistente -eq 'PT0S')
    if ($acc.Execute -eq $Ejecutable -and $existente.Principal.UserId -like "*$Usuario" -and $sinRetraso) {
        Write-Log "Sin cambio: la tarea '$NombreTarea' ya existe con la misma accion, usuario y sin retraso."
        Write-Log "== Fin $Paso =="
        return
    }
    Write-Log "La tarea '$NombreTarea' existe con otra configuracion (retraso '$delayExistente'): se reemplaza."
}

$accion   = New-ScheduledTaskAction -Execute $Ejecutable -WorkingDirectory (Split-Path -Parent $Ejecutable)
$disparo  = New-ScheduledTaskTrigger -AtLogOn -User $principalUsuario
$disparo.Delay = 'PT0S'    # EST-07: sin retraso
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
