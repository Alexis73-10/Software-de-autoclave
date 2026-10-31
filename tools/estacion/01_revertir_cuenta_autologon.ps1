<#
.SYNOPSIS
  Inverso del paso 1: restaura Winlogon y, si se pide, elimina la cuenta creada.
.DESCRIPTION
  Restaura los valores de registro guardados por 01_cuenta_autologon.ps1.
  La cuenta solo se elimina con -EliminarCuenta y solo si la creo el paso 1
  (su perfil y archivos no se borran: hacerlo a mano si corresponde).
#>
[CmdletBinding(SupportsShouldProcess)]
param([switch]$EliminarCuenta)
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '01_cuenta_autologon'
Write-Log "== Inicio revertir $Paso (WhatIf=$WhatIfPreference) =="

$resp = Read-Respaldo $Paso
$creada = if ($resp.ContainsKey('CuentaCreada')) { $resp['CuentaCreada'] } else { $null }
if ($creada) { $resp.Remove('CuentaCreada'); if (-not $WhatIfPreference) { Save-Respaldo $Paso $resp } }

Restore-RegValores -Paso $Paso

if ($EliminarCuenta) {
    if (-not $creada) { Write-Log 'La cuenta no fue creada por el paso 1: no se elimina.' 'WARN' }
    elseif (-not (Get-LocalUser -Name $creada -ErrorAction SilentlyContinue)) { Write-Log "La cuenta '$creada' ya no existe." }
    elseif ($PSCmdlet.ShouldProcess($creada, 'Eliminar cuenta local')) {
        Remove-LocalUser -Name $creada
        Write-Log "Cuenta '$creada' eliminada (el perfil en C:\Users queda; borrar a mano si aplica)."
    }
} elseif ($creada -and -not $WhatIfPreference) {
    # Conservar el dato para un posible -EliminarCuenta posterior.
    $r = Read-Respaldo $Paso; $r['CuentaCreada'] = $creada; Save-Respaldo $Paso $r
}
Write-Log "== Fin revertir $Paso =="
