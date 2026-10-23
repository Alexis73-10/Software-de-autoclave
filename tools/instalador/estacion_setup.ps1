<#
.SYNOPSIS
  Puente del Setup (autoclave.iss, E9 tanda 9 / D9-11) hacia los scripts de
  tools\estacion: aplica o revierte UN paso, sin interaccion, y devuelve 0 si
  termino bien y 1 si fallo (el detalle queda en
  %ProgramData%\Especifika\Autoclave\estacion\estacion.log).
.DESCRIPTION
  El Setup lo instala junto a los scripts, en {app}\estacion\ (Archivos de
  programa: solo administradores pueden cambiarlos), porque el desinstalador
  necesita los inversos. Corre elevado (el Setup y el desinstalador piden
  administrador).
  - $ErrorActionPreference = 'Stop': un error no terminante de un paso (que
    por si solo dejaria la salida en 0) cuenta como falla.
  - Paso 01: la cuenta es la que instala (decision de Cristian, 23-oct); la
    contrasena llega por la variable de entorno AUTOCLAVE_CLAVE_AUTOLOGON del
    proceso, nunca por la linea de comandos; con -NoCrearCuenta no se crea
    ninguna cuenta.
  - Los inversos no se ejecutan con -EliminarCuenta (01 nunca crea cuenta
    desde el Setup).
#>
param(
    [Parameter(Mandatory)][ValidateSet('01', '02', '04', '05', '06')][string]$Paso,
    [Parameter(Mandatory)][ValidateSet('Aplicar', 'Revertir')][string]$Accion,
    [string]$Usuario,
    [string]$Dominio
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\_comun.ps1"

$scripts = @{
    '01' = @('01_cuenta_autologon.ps1', '01_revertir_cuenta_autologon.ps1')
    '02' = @('02_arranque_silencioso.ps1', '02_revertir_arranque_silencioso.ps1')
    '04' = @('04_notificaciones_actualizaciones_gestos.ps1', '04_revertir_notificaciones_actualizaciones_gestos.ps1')
    '05' = @('05_plan_energia.ps1', '05_revertir_plan_energia.ps1')
    '06' = @('06_asociar_tactiles.ps1', '06_revertir_asociar_tactiles.ps1')
}
$indice = if ($Accion -eq 'Aplicar') { 0 } else { 1 }
$ruta = Join-Path $PSScriptRoot $scripts[$Paso][$indice]

try {
    Assert-Administrador
    Write-Log "Setup: $Accion paso $Paso ($ruta)."
    if ($Paso -eq '01' -and $Accion -eq 'Aplicar') {
        if (-not $Usuario) { throw 'Paso 01 sin -Usuario.' }
        if (-not $Dominio) { $Dominio = $env:COMPUTERNAME }
        & $ruta -Usuario $Usuario -Dominio $Dominio -NoCrearCuenta -ContrasenaDesdeEntorno
    } else {
        & $ruta
    }
    Write-Log "Setup: paso $Paso ($Accion) terminado."
    exit 0
} catch {
    # la contrasena nunca queda en el entorno, aunque el paso falle antes de leerla
    Remove-Item Env:AUTOCLAVE_CLAVE_AUTOLOGON -ErrorAction SilentlyContinue
    try { Write-Log "Setup: paso $Paso ($Accion) FALLO: $($_.Exception.Message)" 'ERROR' } catch { }
    exit 1
}
