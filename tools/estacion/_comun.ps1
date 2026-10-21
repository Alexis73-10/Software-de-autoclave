# _comun.ps1 - Funciones compartidas por los scripts de la estacion Windows.
# Se carga con dot-sourcing desde cada script:  . "$PSScriptRoot\_comun.ps1"
# No hace nada por si solo.
#
# - Log: %ProgramData%\Especifika\Autoclave\estacion\estacion.log
# - Respaldo de valores previos (para el script inverso):
#   %ProgramData%\Especifika\Autoclave\estacion\respaldo_<paso>.json
#   Solo se escribe la primera vez que se cambia un valor (idempotencia: volver
#   a correr el script no pisa el valor original con el valor ya cambiado).

Set-StrictMode -Version 2.0

$script:DirEstacion = Join-Path $env:ProgramData 'Especifika\Autoclave\estacion'
$script:ArchivoLog  = Join-Path $script:DirEstacion 'estacion.log'

function Initialize-Estacion {
    if (-not (Test-Path -LiteralPath $script:DirEstacion)) {
        # Se crea aunque haya -WhatIf, para poder registrar la simulacion.
        New-Item -ItemType Directory -Path $script:DirEstacion -Force -WhatIf:$false | Out-Null
    }
}

function Write-Log {
    param([Parameter(Mandatory)][string]$Mensaje, [string]$Nivel = 'INFO')
    Initialize-Estacion
    $linea = '{0} [{1}] [{2}] {3}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Nivel, $env:USERNAME, $Mensaje
    Add-Content -LiteralPath $script:ArchivoLog -Value $linea -Encoding UTF8 -WhatIf:$false
    Write-Host $linea
}

function Assert-Administrador {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Este script debe ejecutarse como administrador.'
    }
}

function Get-RutaRespaldo([string]$Paso) { Join-Path $script:DirEstacion ("respaldo_{0}.json" -f $Paso) }

function Read-Respaldo([string]$Paso) {
    $ruta = Get-RutaRespaldo $Paso
    $tabla = @{}
    if (Test-Path -LiteralPath $ruta) {
        $obj = Get-Content -LiteralPath $ruta -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($prop in $obj.PSObject.Properties) { $tabla[$prop.Name] = $prop.Value }
    }
    return $tabla
}

function Save-Respaldo([string]$Paso, [hashtable]$Tabla) {
    Initialize-Estacion
    $Tabla | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Get-RutaRespaldo $Paso) -Encoding UTF8 -WhatIf:$false
}

function Set-RegValor {
    <# Fija un valor de registro guardando antes el original (una sola vez). #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)][string]$Paso,
        [Parameter(Mandatory)][string]$Ruta,
        [Parameter(Mandatory)][string]$Nombre,
        [Parameter(Mandatory)]$Valor,
        [ValidateSet('DWord','String','QWord')][string]$Tipo = 'DWord'
    )
    $clave = "$Ruta|$Nombre"
    $actual = $null; $existe = $false
    if (Test-Path -LiteralPath $Ruta) {
        $item = Get-ItemProperty -LiteralPath $Ruta -Name $Nombre -ErrorAction SilentlyContinue
        if ($null -ne $item) { $existe = $true; $actual = $item.$Nombre }
    }
    if ($existe -and ("$actual" -eq "$Valor")) {
        Write-Log "Sin cambio: $clave ya vale '$Valor'."
        return
    }
    if ($PSCmdlet.ShouldProcess($clave, "Fijar a '$Valor' ($Tipo)")) {
        $resp = Read-Respaldo $Paso
        if (-not $resp.ContainsKey($clave)) {
            $resp[$clave] = @{ Existia = $existe; Valor = $actual; Tipo = $Tipo }
            Save-Respaldo $Paso $resp
        }
        if (-not (Test-Path -LiteralPath $Ruta)) { New-Item -Path $Ruta -Force | Out-Null }
        New-ItemProperty -LiteralPath $Ruta -Name $Nombre -Value $Valor -PropertyType $Tipo -Force | Out-Null
        Write-Log "Cambiado: $clave = '$Valor' (antes: existia=$existe, valor='$actual')."
    }
}

function Restore-RegValores {
    <# Restaura todos los valores de registro respaldados por un paso. #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)][string]$Paso)
    $resp = Read-Respaldo $Paso
    if ($resp.Count -eq 0) { Write-Log "Sin respaldo de registro para '$Paso': nada que restaurar."; return }
    foreach ($clave in @($resp.Keys)) {
        if ($clave -notlike '*|*') { continue }   # datos no de registro (p. ej. PlanActivo)
        $ruta, $nombre = $clave -split '\|', 2
        $orig = $resp[$clave]
        if ($PSCmdlet.ShouldProcess($clave, 'Restaurar valor original')) {
            if ($orig.Existia) {
                if (-not (Test-Path -LiteralPath $ruta)) { New-Item -Path $ruta -Force | Out-Null }
                New-ItemProperty -LiteralPath $ruta -Name $nombre -Value $orig.Valor -PropertyType $orig.Tipo -Force | Out-Null
                Write-Log "Restaurado: $clave = '$($orig.Valor)'."
            } elseif (Test-Path -LiteralPath $ruta) {
                Remove-ItemProperty -LiteralPath $ruta -Name $nombre -ErrorAction SilentlyContinue
                Write-Log "Eliminado (no existia antes): $clave."
            }
            $resp.Remove($clave)
        }
    }
    if (-not $WhatIfPreference) {
        if ($resp.Count -eq 0) { Remove-Item -LiteralPath (Get-RutaRespaldo $Paso) -Force -ErrorAction SilentlyContinue }
        else { Save-Respaldo $Paso $resp }
    }
}
