<#
.SYNOPSIS
  Inverso del paso 2: vuelve a mostrar el logo y la pantalla de bloqueo.
.DESCRIPTION
  Quita bootux del BCD (vuelve al valor por defecto), restaura los valores de
  registro y deja CONSOLELOCK=1 (valor por defecto de Windows).
  La copia del BCD queda en %ProgramData%\Especifika\Autoclave\estacion\bcd_respaldo.bcd
  por si hiciera falta 'bcdedit /import' manual.
#>
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '02_arranque_silencioso'
Write-Log "== Inicio revertir $Paso (WhatIf=$WhatIfPreference) =="

$actual = (& bcdedit.exe /enum '{current}') -join "`n"
if ($actual -notmatch '(?im)^bootux\s') {
    Write-Log 'Sin cambio: bootux no esta fijado.'
} elseif ($PSCmdlet.ShouldProcess('{current} bootux', 'bcdedit /deletevalue bootux')) {
    & bcdedit.exe /deletevalue '{current}' bootux | Out-Null
    Write-Log "bcdedit /deletevalue bootux (codigo $LASTEXITCODE)."
}

Restore-RegValores -Paso $Paso

if ($PSCmdlet.ShouldProcess('SCHEME_CURRENT CONSOLELOCK', 'Fijar a 1')) {
    & powercfg.exe /setacvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 1 | Out-Null
    & powercfg.exe /setdcvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 1 | Out-Null
    & powercfg.exe /setactive SCHEME_CURRENT | Out-Null
    Write-Log 'CONSOLELOCK=1 en el plan activo.'
}
Write-Log "== Fin revertir $Paso =="
