<#
.SYNOPSIS
  Inverso del paso 6: borra las asociaciones tactil-monitor creadas por el paso.
.DESCRIPTION
  Usa respaldo_06_asociar_tactiles.json (valores que habia en
  HKLM\SOFTWARE\Microsoft\Wisp\Pen\Digimon antes de la primera ejecucion del
  paso 6):
  - un valor que no estaba antes se borra;
  - un valor que estaba antes con otro dato recupera el dato anterior;
  - un valor que estaba antes igual no se toca;
  - si la clave no existia antes y queda vacia, se borra.
  Solo escribe en esa clave (un respaldo alterado no puede tocar otra). Sin
  respaldo no borra nada (no sabe que asociaciones eran previas).
#>
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '06_asociar_tactiles'
$RutaDigimon = 'SOFTWARE\Microsoft\Wisp\Pen\Digimon'
Write-Log "== Inicio revertir $Paso (WhatIf=$WhatIfPreference) =="

$resp = Read-Respaldo $Paso
if (-not $resp.ContainsKey('DigimonAntes')) {
    Write-Log 'Sin respaldo de Digimon: no se borra ninguna asociacion.' 'WARN'
    Write-Log "== Fin revertir $Paso =="
    return
}
# DigimonAntes vuelve del JSON como objeto: nombre -> {Valor; Tipo}
$antes = @{}
if ($null -ne $resp['DigimonAntes']) {
    foreach ($prop in $resp['DigimonAntes'].PSObject.Properties) { $antes[$prop.Name] = $prop.Value }
}
$tiposValidos = @('String', 'ExpandString', 'DWord', 'QWord', 'MultiString', 'Binary')

$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry64')
try {
    $clave = $base.OpenSubKey($RutaDigimon, $true)
    if ($null -eq $clave) {
        Write-Log "No existe HKLM\$($RutaDigimon): nada que borrar."
    } else {
        try {
            foreach ($nombre in @($clave.GetValueNames())) {
                $actual = $clave.GetValue($nombre, $null, 'DoNotExpandEnvironmentNames')
                if (-not $antes.ContainsKey($nombre)) {
                    if ($PSCmdlet.ShouldProcess("$RutaDigimon|$nombre", 'Borrar asociacion creada por el paso 6')) {
                        $clave.DeleteValue($nombre, $false)
                        Write-Log "Borrada asociacion creada por el paso 6: $nombre."
                    }
                    continue
                }
                $previo = $antes[$nombre]
                if ("$actual" -ne "$($previo.Valor)") {
                    $tipo = "$($previo.Tipo)"
                    if ($tiposValidos -notcontains $tipo) { $tipo = 'String' }
                    if ($PSCmdlet.ShouldProcess("$RutaDigimon|$nombre", 'Restaurar asociacion anterior')) {
                        $clave.SetValue($nombre, $previo.Valor, [Microsoft.Win32.RegistryValueKind]$tipo)
                        Write-Log "Restaurada asociacion anterior: $nombre."
                    }
                }
            }
            $quedan = $clave.ValueCount + $clave.SubKeyCount
        } finally { $clave.Close() }
        if (-not $resp['DigimonExistia'] -and $quedan -eq 0) {
            if ($PSCmdlet.ShouldProcess($RutaDigimon, 'Borrar la clave vacia (no existia antes)')) {
                $base.DeleteSubKey($RutaDigimon, $false)
                Write-Log "Borrada la clave HKLM\$($RutaDigimon) (no existia antes del paso 6)."
            }
        }
    }
} finally { $base.Close() }

if (-not $WhatIfPreference) {
    foreach ($k in 'DigimonAntes', 'DigimonExistia') { $resp.Remove($k) }
    if ($resp.Count -eq 0) { Remove-Item -LiteralPath (Get-RutaRespaldo $Paso) -Force -ErrorAction SilentlyContinue }
    else { Save-Respaldo $Paso $resp }
}
Write-Log "== Fin revertir $Paso =="
