<#
.SYNOPSIS
  Paso 2: arranque sin logo y sin pantalla de bloqueo.
.DESCRIPTION
  Planeacion seccion 3.3 y 3.4.
  - Exporta una copia del BCD (solo la primera vez) y fija bootux=disabled.
  - Oculta la pantalla de bloqueo (NoLockScreen) y el fondo del login.
  - Sin contrasena al reanudar (CONSOLELOCK=0 en el plan de energia activo).
  NoLockScreen es directiva: en Windows Home puede ignorarse (anotar en la checklist).
  Inverso: 02_revertir_arranque_silencioso.ps1.
#>
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '02_arranque_silencioso'
Write-Log "== Inicio $Paso (WhatIf=$WhatIfPreference) =="

$bcdCopia = Join-Path $script:DirEstacion 'bcd_respaldo.bcd'
if (Test-Path -LiteralPath $bcdCopia) {
    Write-Log "Copia de BCD ya existe ($bcdCopia): no se sobrescribe."
} elseif ($PSCmdlet.ShouldProcess($bcdCopia, 'Exportar copia del BCD')) {
    & bcdedit.exe /export $bcdCopia | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "bcdedit /export fallo ($LASTEXITCODE); no se sigue." }
    Write-Log "BCD exportado a $bcdCopia."
}

$actual = (& bcdedit.exe /enum '{current}') -join "`n"
if ($actual -match '(?im)^bootux\s+disabled') {
    Write-Log 'Sin cambio: bootux ya esta en disabled.'
} elseif ($PSCmdlet.ShouldProcess('{current} bootux', 'bcdedit /set bootux disabled')) {
    & bcdedit.exe /set '{current}' bootux disabled | Out-Null
    Write-Log "bcdedit /set bootux disabled (codigo $LASTEXITCODE)."
}

$pers = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization'
Set-RegValor -Paso $Paso -Ruta $pers -Nombre 'NoLockScreen' -Valor 1
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\System' -Nombre 'DisableLogonBackgroundImage' -Valor 1
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\LogonUI\SessionData' `
    -Nombre 'AllowLockScreen' -Valor 0

# Sin contrasena al reanudar (CONSOLELOCK), en CA y CC del plan activo.
if ($PSCmdlet.ShouldProcess('SCHEME_CURRENT CONSOLELOCK', 'Fijar a 0')) {
    & powercfg.exe /setacvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 0 | Out-Null
    & powercfg.exe /setdcvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 0 | Out-Null
    & powercfg.exe /setactive SCHEME_CURRENT | Out-Null
    Write-Log 'CONSOLELOCK=0 en el plan activo.'
}
Write-Log "== Fin $Paso =="
