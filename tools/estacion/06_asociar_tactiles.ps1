<#
.SYNOPSIS
  Paso 6: asociar cada pantalla tactil con su monitor (D11-5, tanda 11).
.DESCRIPTION
  Con dos paneles identicos Windows no puede deducir que tactil corresponde a
  que monitor: hace falta un toque en cada pantalla, una sola vez. Este paso
  abre la herramienta de Windows (%windir%\System32\MultiDigitizer.exe,
  "Configuracion de Tablet PC > Configurar > Entrada tactil"), que pide tocar
  la pantalla que muestra el mensaje y pasar a la siguiente (Enter salta una
  pantalla, Esc cancela).

  Windows guarda la asociacion por puerto USB en
  HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon (un valor por tactil). Cambiar el
  cable de un tactil a otro puerto la deshace: marcar los puertos (LEEME.md).

  - Solo con 2 o mas monitores (con uno no hay nada que asociar: lo anota y
    sale sin abrir nada).
  - La primera vez guarda los valores que habia en Digimon (respaldo
    respaldo_06_asociar_tactiles.json), para que el inverso borre solo lo que
    creo o cambio este paso. Volver a correrlo no pisa ese respaldo.
  - Espera a la herramienta como maximo -MinutosEspera minutos (por defecto
    10); si no se cerro, la cierra y sigue (nunca deja el Setup colgado).
  - Al terminar escribe en estacion.log cuantas asociaciones quedaron. Menos
    de 2 NO es una falla del paso (sale con 0): el Setup lo cuenta en el
    registro y avisa "Repita la asociacion de pantallas tactiles".
  Inverso: 06_revertir_asociar_tactiles.ps1.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [int]$MinutosEspera = 10
)
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '06_asociar_tactiles'
$RutaDigimon = 'SOFTWARE\Microsoft\Wisp\Pen\Digimon'
Write-Log "== Inicio $Paso (WhatIf=$WhatIfPreference) =="

function Get-ValoresDigimon {
    <# Valores actuales de HKLM\...\Digimon (vista de 64 bits): nombre -> @{Valor; Tipo}. #>
    $tabla = @{}
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry64')
    try {
        $clave = $base.OpenSubKey($RutaDigimon, $false)
        if ($null -ne $clave) {
            try {
                foreach ($nombre in $clave.GetValueNames()) {
                    $tabla[$nombre] = @{
                        Valor = $clave.GetValue($nombre, $null, 'DoNotExpandEnvironmentNames')
                        Tipo  = $clave.GetValueKind($nombre).ToString()
                    }
                }
            } finally { $clave.Close() }
        }
    } finally { $base.Close() }
    return $tabla
}

function Test-ExisteDigimon {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry64')
    try {
        $clave = $base.OpenSubKey($RutaDigimon, $false)
        if ($null -eq $clave) { return $false }
        $clave.Close()
        return $true
    } finally { $base.Close() }
}

# Monitores conectados
Add-Type -AssemblyName System.Windows.Forms
$monitores = @([System.Windows.Forms.Screen]::AllScreens).Count
Write-Log "Monitores detectados: $monitores."
if ($monitores -lt 2) {
    Write-Log 'Menos de 2 monitores: no hay pantallas tactiles que asociar; no se abre la herramienta.' 'WARN'
    Write-Log "== Fin $Paso =="
    return
}

# Herramienta de Windows (64 bits; Sysnative si este PowerShell fuera de 32 bits)
$herramienta = Join-Path $env:windir 'System32\MultiDigitizer.exe'
if (-not (Test-Path -LiteralPath $herramienta)) {
    $alterna = Join-Path $env:windir 'Sysnative\MultiDigitizer.exe'
    if (Test-Path -LiteralPath $alterna) { $herramienta = $alterna }
    else { throw "No se encuentra $herramienta (Configuracion de Tablet PC)." }
}

# Respaldo del estado previo (solo la primera vez)
$resp = Read-Respaldo $Paso
if (-not $resp.ContainsKey('DigimonAntes')) {
    $antes = Get-ValoresDigimon
    if ($PSCmdlet.ShouldProcess($RutaDigimon, "Respaldar $($antes.Count) asociaciones previas")) {
        $resp['DigimonAntes'] = $antes
        $resp['DigimonExistia'] = (Test-ExisteDigimon)
        Save-Respaldo $Paso $resp
        Write-Log "Respaldo de Digimon: $($antes.Count) asociaciones previas (clave existia=$($resp['DigimonExistia']))."
    }
} else {
    Write-Log 'Respaldo de Digimon ya existe: no se sobrescribe.'
}

if ($PSCmdlet.ShouldProcess($herramienta, 'Abrir la asociacion de pantallas tactiles')) {
    Write-Log "Abriendo $herramienta (espera maxima $MinutosEspera min)."
    $proceso = Start-Process -FilePath $herramienta -PassThru
    if (-not $proceso.WaitForExit($MinutosEspera * 60 * 1000)) {
        Write-Log "La herramienta no se cerro en $MinutosEspera min: se cierra." 'WARN'
        try { $proceso.Kill() } catch { Write-Log "No se pudo cerrar la herramienta: $($_.Exception.Message)" 'WARN' }
    } else {
        Write-Log "Herramienta cerrada (codigo $($proceso.ExitCode))."
    }
}

$despues = Get-ValoresDigimon
$nivel = if ($despues.Count -ge 2) { 'INFO' } else { 'WARN' }
Write-Log "Asociaciones tactiles en HKLM\$($RutaDigimon): $($despues.Count)." $nivel
if ($despues.Count -lt 2) {
    Write-Log 'Quedaron menos de 2 asociaciones: repita la asociacion de pantallas tactiles.' 'WARN'
}
Write-Log "== Fin $Paso =="
