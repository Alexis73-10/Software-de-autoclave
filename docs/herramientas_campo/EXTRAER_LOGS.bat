<# :
@echo off
rem Extrae los logs del Software de Autoclave a esta USB (solo lectura en el equipo).
rem Archivo hibrido: cmd ejecuta estas lineas; PowerShell lee el resto del mismo archivo.
set "EXTRAER_DIR=%~dp0"
set "EXTRAER_BAT=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((Get-Content -LiteralPath $env:EXTRAER_BAT -Encoding UTF8) -join [char]10)"
exit /b
#>
# extraer_logs.ps1 — Copia los logs del Software de Autoclave (Especifika) a la USB.
# Uso: doble clic en este .bat (en la USB). No ejecuta ningún .ps1.
# Solo lee: no modifica nada en el equipo.
# Destino: <USB>\Especifika_logs\<PC>_<serie>_<fecha>\ y un .zip con el mismo nombre.

$ErrorActionPreference = 'Continue'
$usb = $env:EXTRAER_DIR
$fecha = Get-Date -Format 'yyyyMMdd_HHmmss'

function Escribir($t) { Write-Host $t }

# 1) Carpetas de datos candidatas (en orden de preferencia)
$candidatas = New-Object System.Collections.Generic.List[string]
foreach ($vista in @('Registry64', 'Registry32')) {
    try {
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', $vista)
        $k = $base.OpenSubKey('SOFTWARE\Especifika\Autoclave')
        if ($k) {
            $d = $k.GetValue('RutaDatos'); $p = $k.GetValue('RutaPrograma')
            if ($d) { $candidatas.Add([string]$d) }
            if ($p) { $candidatas.Add((Join-Path ([string]$p) 'data')); $candidatas.Add([string]$p) }
            $k.Close()
        }
        $base.Close()
    } catch { }
}
# Disposición anterior (compilación I y previas)
if ($env:ProgramData) { $candidatas.Add((Join-Path $env:ProgramData 'Especifika\Autoclave')) }
# Cualquier disco fijo: X:\Especifika\Autoclave\datos
try {
    Get-WmiObject Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
        $candidatas.Add("$($_.DeviceID)\Especifika\Autoclave\datos")
        $candidatas.Add("$($_.DeviceID)\Especifika\Autoclave\programa")
    }
} catch { }

$origenes = $candidatas | Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
            ForEach-Object { (Resolve-Path -LiteralPath $_).Path } | Select-Object -Unique
# No buscar dentro de la propia USB
$origenes = $origenes | Where-Object { -not $_.StartsWith($usb.TrimEnd('\')) }

if (-not $origenes) {
    Escribir 'No se encontró la carpeta de datos del Software de Autoclave en este equipo.'
    Read-Host 'Pulse Enter para salir'; exit 2
}

# 2) Serie del equipo (para el nombre de la carpeta), si se puede leer
$serie = 'SINSERIE'
foreach ($o in $origenes) {
    foreach ($f in @('installation_profile.json', 'data\installation_profile.json')) {
        $ruta = Join-Path $o $f
        if (Test-Path -LiteralPath $ruta) {
            try { $j = Get-Content -LiteralPath $ruta -Raw | ConvertFrom-Json
                  if ($j.serial_number) { $serie = [string]$j.serial_number; break } } catch { }
        }
    }
    if ($serie -ne 'SINSERIE') { break }
}

$nombre = "$($env:COMPUTERNAME)_$($serie)_$fecha"
$destino = Join-Path $usb "Especifika_logs\$nombre"
New-Item -ItemType Directory -Force -Path $destino | Out-Null
$resumen = Join-Path $destino '_resumen.txt'
"Extracción de logs $fecha en $env:COMPUTERNAME (serie $serie)" | Out-File $resumen -Encoding utf8

# 3) Copiar *.log (incluidos rotados: *.log.1, *.log.2026-...) y logs del Setup
$total = 0
foreach ($o in $origenes) {
    "Origen: $o" | Out-File $resumen -Append -Encoding utf8
    Escribir "Buscando logs en $o ..."
    $archivos = Get-ChildItem -LiteralPath $o -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like '*.log' -or $_.Name -like '*.log.*' }
    foreach ($a in $archivos) {
        $rel = $a.FullName.Substring($o.Length).TrimStart('\')
        $sub = ($o -replace '[:\\]', '_').Trim('_')
        $dst = Join-Path $destino (Join-Path $sub $rel)
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
        try {
            # Copia aunque el programa tenga el archivo abierto (lectura compartida)
            $in = [System.IO.File]::Open($a.FullName, 'Open', 'Read', 'ReadWrite')
            $out = [System.IO.File]::Create($dst)
            $in.CopyTo($out); $out.Close(); $in.Close()
            "  $rel  ($([math]::Round($a.Length/1KB,1)) KB, $($a.LastWriteTime))" | Out-File $resumen -Append -Encoding utf8
            $total++
        } catch {
            "  NO SE PUDO COPIAR $rel : $($_.Exception.Message)" | Out-File $resumen -Append -Encoding utf8
        }
    }
}
# Logs del instalador (Inno Setup) en %TEMP%
Get-ChildItem -LiteralPath $env:TEMP -Filter 'Setup Log*.txt' -File -ErrorAction SilentlyContinue |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $destino -ErrorAction SilentlyContinue; $total++ }

"Total copiados: $total" | Out-File $resumen -Append -Encoding utf8

# 4) Comprimir
$zip = "$destino.zip"
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($destino, $zip)
    Escribir "Listo: $total archivos. Copia en:`n  $destino`n  $zip"
} catch {
    Escribir "Listo: $total archivos en $destino (no se pudo crear el .zip: $($_.Exception.Message))"
}
Read-Host 'Pulse Enter para salir'
