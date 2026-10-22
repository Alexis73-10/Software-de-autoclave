<#
.SYNOPSIS
  Inverso del paso 3: elimina la tarea programada de arranque del autoclave.
#>
[CmdletBinding(SupportsShouldProcess)]
param([string]$NombreTarea = 'Especifika Autoclave - Arranque')
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
Write-Log "== Inicio revertir 03_tarea_autoclave (WhatIf=$WhatIfPreference) =="
if (-not (Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue)) {
    Write-Log "Sin cambio: la tarea '$NombreTarea' no existe."
} elseif ($PSCmdlet.ShouldProcess($NombreTarea, 'Eliminar tarea programada')) {
    Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false
    Write-Log "Tarea '$NombreTarea' eliminada."
}
Write-Log '== Fin revertir 03_tarea_autoclave =='
