<#
.SYNOPSIS
  Inverso del paso 5: reimporta el plan de energia original y la hibernacion.
.DESCRIPTION
  Importa el .pow respaldado como plan nuevo y lo activa (powercfg /import
  crea un GUID nuevo; el plan modificado queda en la lista y se puede borrar
  a mano con powercfg /delete). Restaura la hibernacion y el inicio rapido.
#>
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '05_plan_energia'
Write-Log "== Inicio revertir $Paso (WhatIf=$WhatIfPreference) =="

$resp = Read-Respaldo $Paso
if (-not $resp.ContainsKey('ArchivoPow')) {
    Write-Log 'Sin respaldo del plan de energia: nada que reimportar.' 'WARN'
} else {
    $pow = $resp['ArchivoPow']
    # E9 (tanda 9): solo el .pow que guardo el paso 5 en la carpeta protegida
    if ([IO.Path]::GetFullPath($pow) -ne [IO.Path]::GetFullPath((Join-Path $script:DirEstacion 'plan_energia_respaldo.pow'))) {
        throw "Ruta de respaldo del plan inesperada ($pow): no se importa."
    }
    if (-not (Test-Path -LiteralPath $pow)) { throw "No se encuentra $pow." }
    if ($PSCmdlet.ShouldProcess($pow, 'Importar y activar plan original')) {
        $salida = (& powercfg.exe /import $pow) -join ' '
        $nuevo = [regex]::Match($salida, '[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}').Value
        if (-not $nuevo) { throw "powercfg /import no devolvio GUID: $salida" }
        & powercfg.exe /setactive $nuevo | Out-Null
        Write-Log "Plan original reimportado como $nuevo y activado."
        if ($resp['HibernateEnabled'] -eq 1) {
            & powercfg.exe /hibernate on | Out-Null
            Write-Log 'Hibernacion reactivada.'
        }
        foreach ($k in 'PlanActivo','HibernateEnabled','ArchivoPow') { $resp.Remove($k) }
        Save-Respaldo $Paso $resp
    }
}
Restore-RegValores -Paso $Paso
Write-Log "== Fin revertir $Paso =="
