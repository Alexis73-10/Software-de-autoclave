<#
.SYNOPSIS
  Inverso del paso 4: restaura notificaciones, Windows Update y gestos de borde.
#>
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '04_notificaciones_actualizaciones_gestos'
Write-Log "== Inicio revertir $Paso (WhatIf=$WhatIfPreference) =="
Restore-RegValores -Paso $Paso
Write-Log 'Para que se aplique ya: gpupdate /force o reiniciar.'
Write-Log "== Fin revertir $Paso =="
