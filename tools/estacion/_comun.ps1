# _comun.ps1 - Funciones compartidas por los scripts de la estacion Windows.
# Se carga con dot-sourcing desde cada script:  . "$PSScriptRoot\_comun.ps1"
# No hace nada por si solo.
#
# - Log: %ProgramData%\Especifika\Autoclave\estacion\estacion.log
# - Respaldo de valores previos (para el script inverso):
#   %ProgramData%\Especifika\Autoclave\estacion\respaldo_<paso>.json
#   Solo se escribe la primera vez que se cambia un valor (idempotencia: volver
#   a correr el script no pisa el valor original con el valor ya cambiado).
#
# E9 (tanda 9, D9-11): el Setup da Modificar a Usuarios sobre
# %ProgramData%\Especifika\Autoclave (el programa corre sin administrador), y
# los inversos corren como administrador con lo que diga respaldo_<paso>.json.
# Por eso:
#   - la carpeta estacion\ queda solo para Administradores y SYSTEM (dueno
#     Administradores, sin herencia), para que un usuario sin privilegios no
#     pueda leer la contrasena del inicio automatico ni plantar un respaldo;
#   - Restore-RegValores solo restaura los valores de $ValoresGestionados (un
#     respaldo alterado no puede escribir otra clave del registro);
#   - el log nunca muestra el valor de DefaultPassword.

Set-StrictMode -Version 2.0

$script:DirEstacion = Join-Path $env:ProgramData 'Especifika\Autoclave\estacion'
$script:ArchivoLog  = Join-Path $script:DirEstacion 'estacion.log'
$script:EstacionProtegida = $false

# Unicos valores de registro que cambian (y restauran) los pasos 01, 02, 04 y 05.
$script:ValoresGestionados = @(
    'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon|AutoAdminLogon',
    'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon|DefaultUserName',
    'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon|DefaultDomainName',
    'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon|DefaultPassword',
    'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\PasswordLess\Device|DevicePasswordLessBuildVersion',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization|NoLockScreen',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\System|DisableLogonBackgroundImage',
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Authentication\LogonUI\SessionData|AllowLockScreen',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Explorer|DisableNotificationCenter',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CurrentVersion\PushNotifications|NoToastApplicationNotification',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent|DisableWindowsConsumerFeatures',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent|DisableSoftLanding',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU|NoAutoRebootWithLoggedOnUsers',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU|AUOptions',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate|SetActiveHours',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate|ActiveHoursStart',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate|ActiveHoursEnd',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate|DeferQualityUpdates',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate|DeferQualityUpdatesPeriodInDays',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate|DeferFeatureUpdates',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate|DeferFeatureUpdatesPeriodInDays',
    'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings|ActiveHoursStart',
    'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings|ActiveHoursEnd',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\EdgeUI|AllowEdgeSwipe',
    'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power|HiberbootEnabled'
)
# Valores que nunca se escriben en el log
$script:NombresSecretos = @('DefaultPassword')

function Protect-DirEstacion {
    <# Solo Administradores (S-1-5-32-544) y SYSTEM (S-1-5-18), dueno
       Administradores, sin herencia de la carpeta de datos (Modificar a Usuarios).
       Los archivos de adentro vuelven a heredar de la carpeta ya protegida. #>
    if ($script:EstacionProtegida) { return }
    & icacls.exe $script:DirEstacion /setowner '*S-1-5-32-544' /T /C /Q | Out-Null
    & icacls.exe $script:DirEstacion /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' /C /Q | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls no pudo proteger $($script:DirEstacion) (codigo $LASTEXITCODE)." }
    if (Get-ChildItem -LiteralPath $script:DirEstacion -Force -ErrorAction SilentlyContinue) {
        & icacls.exe (Join-Path $script:DirEstacion '*') /reset /T /C /Q | Out-Null
    }
    $script:EstacionProtegida = $true
}

function Initialize-Estacion {
    if (-not (Test-Path -LiteralPath $script:DirEstacion)) {
        # Se crea aunque haya -WhatIf, para poder registrar la simulacion.
        New-Item -ItemType Directory -Path $script:DirEstacion -Force -WhatIf:$false | Out-Null
    }
    Protect-DirEstacion
}

function Write-Log {
    param([Parameter(Mandatory)][string]$Mensaje, [string]$Nivel = 'INFO')
    Initialize-Estacion
    $linea = '{0} [{1}] [{2}] {3}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Nivel, $env:USERNAME, $Mensaje
    Add-Content -LiteralPath $script:ArchivoLog -Value $linea -Encoding UTF8 -WhatIf:$false
    Write-Host $linea
}

function Format-ValorLog([string]$Nombre, $Valor) {
    if ($script:NombresSecretos -contains $Nombre) { return '********' }
    return "$Valor"
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
    Initialize-Estacion
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
    if ($script:ValoresGestionados -notcontains $clave) { throw "Valor de registro no gestionado: $clave (agregarlo a ValoresGestionados en _comun.ps1)." }
    $actual = $null; $existe = $false
    if (Test-Path -LiteralPath $Ruta) {
        $item = Get-ItemProperty -LiteralPath $Ruta -Name $Nombre -ErrorAction SilentlyContinue
        if ($null -ne $item) { $existe = $true; $actual = $item.$Nombre }
    }
    if ($existe -and ("$actual" -eq "$Valor")) {
        Write-Log "Sin cambio: $clave ya vale '$(Format-ValorLog $Nombre $Valor)'."
        return
    }
    if ($PSCmdlet.ShouldProcess($clave, "Fijar a '$(Format-ValorLog $Nombre $Valor)' ($Tipo)")) {
        $resp = Read-Respaldo $Paso
        if (-not $resp.ContainsKey($clave)) {
            $resp[$clave] = @{ Existia = $existe; Valor = $actual; Tipo = $Tipo }
            Save-Respaldo $Paso $resp
        }
        if (-not (Test-Path -LiteralPath $Ruta)) { New-Item -Path $Ruta -Force | Out-Null }
        New-ItemProperty -LiteralPath $Ruta -Name $Nombre -Value $Valor -PropertyType $Tipo -Force | Out-Null
        Write-Log "Cambiado: $clave = '$(Format-ValorLog $Nombre $Valor)' (antes: existia=$existe, valor='$(Format-ValorLog $Nombre $actual)')."
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
        if ($script:ValoresGestionados -notcontains $clave) {
            Write-Log "Ignorado (no es un valor gestionado por los scripts): $clave." 'WARN'
            continue
        }
        $ruta, $nombre = $clave -split '\|', 2
        $orig = $resp[$clave]
        if ($PSCmdlet.ShouldProcess($clave, 'Restaurar valor original')) {
            if ($orig.Existia) {
                if (-not (Test-Path -LiteralPath $ruta)) { New-Item -Path $ruta -Force | Out-Null }
                New-ItemProperty -LiteralPath $ruta -Name $nombre -Value $orig.Valor -PropertyType $orig.Tipo -Force | Out-Null
                Write-Log "Restaurado: $clave = '$(Format-ValorLog $nombre $orig.Valor)'."
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
