<#
.SYNOPSIS
  Paso 5: plan de energia del quiosco.
.DESCRIPTION
  Planeacion seccion 7:
  - Sin suspension ni hibernacion (el software maneja su propio reposo).
  - Pantalla nunca se apaga por Windows.
  - Boton de encendido y tapa: "no hacer nada" (el apagado normal es "Apagar equipo").
  La primera vez exporta el plan activo a un .pow y guarda su GUID y el estado
  de hibernacion, para el inverso. powercfg es idempotente por naturaleza.
  "Restaurar tras perdida de energia" es de BIOS: va en la checklist, no aqui.
  Inverso: 05_revertir_plan_energia.ps1.
#>
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '05_plan_energia'
Write-Log "== Inicio $Paso (WhatIf=$WhatIfPreference) =="

$resp = Read-Respaldo $Paso
if (-not $resp.ContainsKey('PlanActivo')) {
    $linea = (& powercfg.exe /getactivescheme) -join ' '
    $guid = [regex]::Match($linea, '[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}').Value
    $hib  = (Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Power' -Name HibernateEnabled -ErrorAction SilentlyContinue).HibernateEnabled
    $pow  = Join-Path $script:DirEstacion 'plan_energia_respaldo.pow'
    if ($PSCmdlet.ShouldProcess($pow, "Exportar plan activo $guid")) {
        & powercfg.exe /export $pow $guid | Out-Null
        $resp['PlanActivo'] = $guid; $resp['HibernateEnabled'] = $hib; $resp['ArchivoPow'] = $pow
        Save-Respaldo $Paso $resp
        Write-Log "Plan activo $guid exportado a $pow (hibernacion=$hib)."
    }
} else {
    Write-Log "Respaldo del plan ya existe ($($resp['PlanActivo'])): no se sobrescribe."
}

$ajustes = @(
    @('SUB_SLEEP',   'STANDBYIDLE', 0),
    @('SUB_SLEEP',   'HIBERNATEIDLE', 0),
    @('SUB_SLEEP',   'HYBRIDSLEEP', 0),
    @('SUB_VIDEO',   'VIDEOIDLE', 0),
    @('SUB_BUTTONS', 'PBUTTONACTION', 0),
    @('SUB_BUTTONS', 'SBUTTONACTION', 0),
    @('SUB_BUTTONS', 'LIDACTION', 0)
)
foreach ($a in $ajustes) {
    if ($PSCmdlet.ShouldProcess("SCHEME_CURRENT $($a[0]) $($a[1])", "Fijar a $($a[2]) (CA y CC)")) {
        & powercfg.exe /setacvalueindex SCHEME_CURRENT $a[0] $a[1] $a[2] | Out-Null
        & powercfg.exe /setdcvalueindex SCHEME_CURRENT $a[0] $a[1] $a[2] | Out-Null
        Write-Log "powercfg $($a[0]) $($a[1]) = $($a[2]) (codigo $LASTEXITCODE)."
    }
}
if ($PSCmdlet.ShouldProcess('SCHEME_CURRENT', 'Activar cambios')) { & powercfg.exe /setactive SCHEME_CURRENT | Out-Null }

if ($PSCmdlet.ShouldProcess('Hibernacion', 'powercfg /hibernate off')) {
    & powercfg.exe /hibernate off | Out-Null
    Write-Log "Hibernacion desactivada (codigo $LASTEXITCODE)."
}
# Inicio rapido depende de la hibernacion; se deja explicito en 0.
Set-RegValor -Paso $Paso -Ruta 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Nombre 'HiberbootEnabled' -Valor 0
Write-Log "== Fin $Paso =="
