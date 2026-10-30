# _comun.ps1 - Funciones compartidas por los scripts de la estacion Windows.
# Se carga con dot-sourcing desde cada script:  . "$PSScriptRoot\_comun.ps1"
# No hace nada por si solo.
#
# - Carpeta de la estacion (INS-02, tanda 17): <RutaDatos>\estacion, con
#   RutaDatos de HKLM\SOFTWARE\Especifika\Autoclave (vista de 64 bits; la
#   escribe el Setup antes de correr los pasos), p. ej.
#   D:\Especifika\Autoclave\datos\estacion. Sin esa clave (copia anterior o
#   scripts sueltos): %ProgramData%\Especifika\Autoclave\estacion.
# - Log: <carpeta de la estacion>\estacion.log
# - Respaldo de valores previos (para el script inverso):
#   <carpeta de la estacion>\respaldo_<paso>.json
#   Solo se escribe la primera vez que se cambia un valor (idempotencia: volver
#   a correr el script no pisa el valor original con el valor ya cambiado).
#   El paso 08 (red del modulo E/S, T20-05) guarda ahi la configuracion IPv4
#   anterior del adaptador (respaldo_08_red_modulos.json, sin valores de
#   registro); sus funciones puras estan en _red_modulos_puras.ps1.
#
# E9 (tanda 9, D9-11): el Setup da Modificar a Usuarios sobre la carpeta de
# datos (el programa corre sin administrador), y
# los inversos corren como administrador con lo que diga respaldo_<paso>.json.
# Por eso:
#   - la carpeta estacion\ queda solo para Administradores y SYSTEM (dueno
#     Administradores, sin herencia), para que un usuario sin privilegios no
#     pueda leer la contrasena del inicio automatico ni plantar un respaldo;
#   - Restore-RegValores solo restaura los valores de $ValoresGestionados (un
#     respaldo alterado no puede escribir otra clave del registro);
#   - el log nunca muestra el valor de DefaultPassword.

Set-StrictMode -Version 2.0

function Get-RutaDatosRegistro {
    <# RutaDatos de HKLM\SOFTWARE\Especifika\Autoclave en la vista de 64 bits
       (tambien desde un PowerShell de 32 bits), o $null si no hay clave, falta
       el valor o no es una ruta absoluta X:\... Mismos nombres que
       utils/resources.py (CLAVE_REGISTRO, VALOR_RUTA_DATOS) y autoclave.iss. #>
    $base = $null; $clave = $null
    try {
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry64')
        $clave = $base.OpenSubKey('SOFTWARE\Especifika\Autoclave')
        if ($null -eq $clave) { return $null }
        $valor = $clave.GetValue('RutaDatos')
        if (($valor -is [string]) -and ($valor -match '^[A-Za-z]:\\') -and ($valor -notmatch '\.\.')) {
            return $valor.TrimEnd('\')
        }
        return $null
    } catch {
        return $null
    } finally {
        if ($null -ne $clave) { $clave.Close() }
        if ($null -ne $base) { $base.Close() }
    }
}

function Test-RutaDatos($Ruta) {
    return (($Ruta -is [string]) -and ($Ruta -match '^[A-Za-z]:\\') -and ($Ruta -notmatch '\.\.'))
}

# R1 (V17-s1-05): la variable de entorno AUTOCLAVE_RUTA_DATOS (ruta absoluta
# X:\...\datos), si esta puesta, manda sobre el registro: sirve para revertir a
# mano cuando la clave ya no esta (p. ej. tras desinstalar):
#   $env:AUTOCLAVE_RUTA_DATOS = 'D:\Especifika\Autoclave\datos'
# Orden: AUTOCLAVE_RUTA_DATOS > RutaDatos del registro > %ProgramData%.
$script:RutaDatos = $null
if (Test-RutaDatos $env:AUTOCLAVE_RUTA_DATOS) {
    $script:RutaDatos = $env:AUTOCLAVE_RUTA_DATOS.TrimEnd('\')
} else {
    $script:RutaDatos = Get-RutaDatosRegistro
}
if ($script:RutaDatos) {
    $script:DirEstacion = Join-Path $script:RutaDatos 'estacion'
} else {
    # respaldo: disposicion anterior a la tanda 17 (sin clave de registro)
    $script:DirEstacion = Join-Path $env:ProgramData 'Especifika\Autoclave\estacion'
}
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
       Los archivos de adentro vuelven a heredar de la carpeta ya protegida.
       R1 (V17-s1-01): /inheritance:r /grant:r no quita entradas EXPLICITAS de
       otros SID (p. ej. Todos:F de quien creo antes la carpeta). Por eso la
       DACL se reemplaza entera (SDDL protegida, solo la seccion de acceso) y
       despues se VERIFICA: protegida, dueno Administradores y exactamente esas
       dos entradas. Si no, lanza (falla cerrada). #>
    if ($script:EstacionProtegida) { return }
    & icacls.exe $script:DirEstacion /setowner '*S-1-5-32-544' /T /Q | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls no pudo fijar el dueno de $($script:DirEstacion) (codigo $LASTEXITCODE)." }
    & icacls.exe $script:DirEstacion /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' /Q | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls no pudo proteger $($script:DirEstacion) (codigo $LASTEXITCODE)." }
    $sd = New-Object System.Security.AccessControl.DirectorySecurity
    $sd.SetSecurityDescriptorSddlForm('D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)', [System.Security.AccessControl.AccessControlSections]::Access)
    (Get-Item -LiteralPath $script:DirEstacion -Force).SetAccessControl($sd)
    if (Get-ChildItem -LiteralPath $script:DirEstacion -Force -ErrorAction SilentlyContinue) {
        & icacls.exe (Join-Path $script:DirEstacion '*') /reset /T /Q | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "icacls no pudo restablecer el contenido de $($script:DirEstacion) (codigo $LASTEXITCODE)." }
    }
    Assert-DirEstacionProtegida
    $script:EstacionProtegida = $true
}

function Assert-DirEstacionProtegida {
    <# Lee la ACL de la carpeta de la estacion y lanza si no es exactamente:
       protegida, dueno Administradores, Administradores y SYSTEM control total
       (OI)(CI), sin ninguna otra entrada. #>
    $sid = [System.Security.Principal.SecurityIdentifier]
    $acl = Get-Acl -LiteralPath $script:DirEstacion
    $dueno = $acl.GetOwner($sid).Value
    $reglas = @($acl.GetAccessRules($true, $true, $sid) | ForEach-Object {
        '{0}:{1}:{2}:{3}:{4}:{5}' -f $_.IdentityReference.Value, [int]$_.FileSystemRights,
            [int]$_.AccessControlType, [int]$_.InheritanceFlags, [int]$_.PropagationFlags, $_.IsInherited
    } | Sort-Object)
    $esperadas = @(@('S-1-5-32-544:2032127:0:3:0:False', 'S-1-5-18:2032127:0:3:0:False') | Sort-Object)
    if ((-not $acl.AreAccessRulesProtected) -or ($dueno -ne 'S-1-5-32-544') -or
        (($reglas -join '|') -ne ($esperadas -join '|'))) {
        throw "La ACL de $($script:DirEstacion) no es la esperada (dueno $dueno; $($reglas -join ' | '))."
    }
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

# ---------------------------------------------------------------------------
# Paso 07 (EST-09, tanda 18): escritorio de la estacion. Valores del perfil
# (HKCU) de la cuenta del inicio automatico, que es la que instala. El Setup y
# los scripts corren elevados: HKCU del proceso puede no ser esa cuenta (si se
# eleva con otra), asi que se escribe en HKEY_USERS\<SID de la cuenta>; si su
# perfil no esta cargado (sesion cerrada) se carga NTUSER.DAT con reg.exe load
# en HKU\EspecifikaEstacion07 y se descarga al terminar.
# ---------------------------------------------------------------------------

# Unicos valores (relativos a HKCU) que cambia y restaura el paso 07. El
# inverso ignora cualquier otra clave de respaldo_07_escritorio_estacion.json.
$script:ValoresUsuarioGestionados = @(
    'Control Panel\Desktop|WallpaperStyle',
    'Control Panel\Desktop|TileWallpaper',
    'Control Panel\Desktop|Wallpaper',
    'Software\Microsoft\Windows\CurrentVersion\Explorer\Wallpapers|BackgroundType',
    'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced|HideIcons',
    'Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3|Settings'
)
$script:ColmenaTemporal = 'EspecifikaEstacion07'
$script:TiposValorUsuario = @('String', 'ExpandString', 'DWord', 'QWord', 'Binary', 'MultiString')

function Test-SidCuenta($Sid) {
    <# SID de una cuenta de usuario local o de dominio (S-1-5-21-...). #>
    return (($Sid -is [string]) -and ($Sid -match '^S-1-5-21(-\d+)+$'))
}

function Resolve-CuentaEstacion {
    <# Cuenta del inicio automatico: -Usuario/-Dominio si llegan; si no,
       Winlogon DefaultUserName/DefaultDomainName (lo escribe el paso 01); si
       tampoco, la cuenta que ejecuta el script. Devuelve @{Nombre; Sid}. #>
    param([string]$Usuario, [string]$Dominio)
    if (-not $Usuario) {
        $wl = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -ErrorAction SilentlyContinue
        if (($null -ne $wl) -and ($wl.PSObject.Properties.Name -contains 'DefaultUserName') -and $wl.DefaultUserName) {
            $Usuario = [string]$wl.DefaultUserName
            if ($wl.PSObject.Properties.Name -contains 'DefaultDomainName') { $Dominio = [string]$wl.DefaultDomainName }
        }
    }
    if (-not $Usuario) {
        $actual = [Security.Principal.WindowsIdentity]::GetCurrent()
        return @{ Nombre = $actual.Name; Sid = $actual.User.Value }
    }
    if ((-not $Dominio) -or ($Dominio -eq '.')) { $Dominio = $env:COMPUTERNAME }
    $nombre = "$Dominio\$Usuario"
    $sid = (New-Object System.Security.Principal.NTAccount($Dominio, $Usuario)).Translate(
        [System.Security.Principal.SecurityIdentifier]).Value
    if (-not (Test-SidCuenta $sid)) { throw "La cuenta $nombre no es una cuenta de usuario ($sid)." }
    return @{ Nombre = $nombre; Sid = $sid }
}

function Test-SesionDeLaCuenta([string]$Sid) {
    <# True si el proceso corre con esa cuenta: solo entonces SystemParametersInfo
       y SHAppBarMessage actuan sobre su sesion. #>
    return ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -eq $Sid)
}

function Open-ColmenaUsuario([string]$Sid) {
    <# Raiz de HKEY_USERS donde estan los valores HKCU de la cuenta. Si la
       sesion esta abierta, HKU\<SID>; si no, carga su NTUSER.DAT (se carga
       tambien con -WhatIf, solo para leer: se descarga al terminar). #>
    if (-not (Test-SidCuenta $Sid)) { throw "SID de cuenta invalido: $Sid." }
    $clave = [Microsoft.Win32.Registry]::Users.OpenSubKey($Sid, $false)
    if ($null -ne $clave) {
        $clave.Close()
        return @{ Raiz = $Sid; Cargada = $false }
    }
    $lista = Get-ItemProperty -LiteralPath "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\$Sid" -ErrorAction SilentlyContinue
    if (($null -eq $lista) -or (-not ($lista.PSObject.Properties.Name -contains 'ProfileImagePath'))) {
        throw "La cuenta $Sid no tiene perfil (nunca inicio sesion): inicie sesion una vez con ella y repita el paso."
    }
    $dat = Join-Path ([Environment]::ExpandEnvironmentVariables([string]$lista.ProfileImagePath)) 'NTUSER.DAT'
    if (-not (Test-Path -LiteralPath $dat)) { throw "No se encuentra $dat." }
    $existente = [Microsoft.Win32.Registry]::Users.OpenSubKey($script:ColmenaTemporal, $false)
    if ($null -ne $existente) {
        $existente.Close()
        throw "HKU\$($script:ColmenaTemporal) ya esta cargada (ejecucion anterior interrumpida): descarguela con 'reg unload HKU\$($script:ColmenaTemporal)'."
    }
    & reg.exe load "HKU\$($script:ColmenaTemporal)" $dat | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "reg load de $dat fallo (codigo $LASTEXITCODE)." }
    Write-Log "Perfil de $Sid cargado desde $dat en HKU\$($script:ColmenaTemporal) (sesion cerrada)."
    return @{ Raiz = $script:ColmenaTemporal; Cargada = $true }
}

function Close-ColmenaUsuario($Colmena) {
    if (($null -eq $Colmena) -or (-not $Colmena.Cargada)) { return }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
    & reg.exe unload "HKU\$($Colmena.Raiz)" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "No se pudo descargar HKU\$($Colmena.Raiz) (codigo $LASTEXITCODE): reinicie o 'reg unload HKU\$($Colmena.Raiz)'." 'WARN'
    } else {
        Write-Log "Perfil descargado de HKU\$($Colmena.Raiz)."
    }
}

function Get-ValorUsuario([string]$Raiz, [string]$Ruta, [string]$Nombre) {
    <# @{Existe; Valor; Tipo} de HKU\<Raiz>\<Ruta>\<Nombre> (sin expandir %variables%). #>
    $clave = [Microsoft.Win32.Registry]::Users.OpenSubKey("$Raiz\$Ruta", $false)
    if ($null -eq $clave) { return @{ Existe = $false; Valor = $null; Tipo = $null } }
    try {
        if (-not ($clave.GetValueNames() -contains $Nombre)) { return @{ Existe = $false; Valor = $null; Tipo = $null } }
        return @{
            Existe = $true
            Valor  = $clave.GetValue($Nombre, $null, 'DoNotExpandEnvironmentNames')
            Tipo   = $clave.GetValueKind($Nombre).ToString()
        }
    } finally { $clave.Close() }
}

function ConvertTo-ValorUsuario($Valor, [string]$Tipo) {
    <# El JSON devuelve los arreglos como object[] y los numeros como int/long
       (la coma evita que PowerShell desarme el arreglo al devolverlo). #>
    switch ($Tipo) {
        'Binary'      { return , ([byte[]]@($Valor)) }
        'MultiString' { return , ([string[]]@($Valor)) }
        'DWord' {
            $n = [long]$Valor
            if ($n -gt [int]::MaxValue) { $n -= 4294967296 }   # REG_DWORD sin signo guardado como positivo
            return [int]$n
        }
        'QWord'       { return [long]$Valor }
        default       { return [string]$Valor }
    }
}

function Write-ValorUsuario([string]$Raiz, [string]$Ruta, [string]$Nombre, $Valor, [string]$Tipo) {
    if ($script:TiposValorUsuario -notcontains $Tipo) { throw "Tipo de valor no admitido: $Tipo." }
    $clave = [Microsoft.Win32.Registry]::Users.CreateSubKey("$Raiz\$Ruta")
    try {
        $clave.SetValue($Nombre, (ConvertTo-ValorUsuario $Valor $Tipo), [Microsoft.Win32.RegistryValueKind]$Tipo)
    } finally { $clave.Close() }
}

function Remove-ValorUsuario([string]$Raiz, [string]$Ruta, [string]$Nombre) {
    $clave = [Microsoft.Win32.Registry]::Users.OpenSubKey("$Raiz\$Ruta", $true)
    if ($null -eq $clave) { return }
    try { $clave.DeleteValue($Nombre, $false) } finally { $clave.Close() }
}

function Format-ValorUsuario($Valor) {
    if ($null -eq $Valor) { return '' }
    if (($Valor -is [byte[]]) -or ($Valor -is [object[]])) {
        return ((@($Valor) | ForEach-Object { ([int]$_).ToString('X2') }) -join ' ')
    }
    return "$Valor"
}

function Set-ValorUsuario {
    <# Fija un valor HKCU de la cuenta guardando antes el original (una sola
       vez, tambien si no existia) en respaldo_<Paso>.json. #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)][string]$Paso,
        [Parameter(Mandatory)]$Colmena,
        [Parameter(Mandatory)][string]$Ruta,
        [Parameter(Mandatory)][string]$Nombre,
        [Parameter(Mandatory)]$Valor,
        [Parameter(Mandatory)][ValidateSet('String', 'DWord', 'Binary')][string]$Tipo
    )
    $id = "$Ruta|$Nombre"
    if ($script:ValoresUsuarioGestionados -notcontains $id) { throw "Valor de usuario no gestionado: $id (agregarlo a ValoresUsuarioGestionados en _comun.ps1)." }
    $actual = Get-ValorUsuario $Colmena.Raiz $Ruta $Nombre
    if ($actual.Existe -and ($actual.Tipo -eq $Tipo) -and ((Format-ValorUsuario $actual.Valor) -eq (Format-ValorUsuario $Valor))) {
        Write-Log "Sin cambio: HKCU\$id ya vale '$(Format-ValorUsuario $Valor)'."
        return
    }
    if ($PSCmdlet.ShouldProcess("HKCU\$id", "Fijar a '$(Format-ValorUsuario $Valor)' ($Tipo)")) {
        $resp = Read-Respaldo $Paso
        if (-not $resp.ContainsKey($id)) {
            $resp[$id] = @{ Existia = $actual.Existe; Valor = $actual.Valor; Tipo = $actual.Tipo }
            Save-Respaldo $Paso $resp
        }
        Write-ValorUsuario $Colmena.Raiz $Ruta $Nombre $Valor $Tipo
        Write-Log "Cambiado: HKCU\$id = '$(Format-ValorUsuario $Valor)' (antes: existia=$($actual.Existe), valor='$(Format-ValorUsuario $actual.Valor)')."
    }
}

function Initialize-Win32Escritorio {
    <# user32!SystemParametersInfoW y shell32!SHAppBarMessage (paso 07). #>
    if ('EspecifikaEscritorio07' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class EspecifikaEscritorio07 {
    public const uint SPI_SETDESKWALLPAPER = 0x0014;
    public const uint SPIF_UPDATEINIFILE = 0x01;
    public const uint SPIF_SENDCHANGE = 0x02;
    public const uint ABM_SETSTATE = 0x0000000A;
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int left; public int top; public int right; public int bottom; }
    [StructLayout(LayoutKind.Sequential)]
    public struct APPBARDATA {
        public uint cbSize; public IntPtr hWnd; public uint uCallbackMessage;
        public uint uEdge; public RECT rc; public IntPtr lParam;
    }
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern bool SystemParametersInfo(uint uiAction, uint uiParam, string pvParam, uint fWinIni);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("shell32.dll")]
    public static extern UIntPtr SHAppBarMessage(uint dwMessage, ref APPBARDATA pData);
    public static bool FijarFondo(string ruta) {
        return SystemParametersInfo(SPI_SETDESKWALLPAPER, 0, ruta, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE);
    }
    public static void FijarEstadoBarra(int estado) {
        APPBARDATA d = new APPBARDATA();
        d.cbSize = (uint)Marshal.SizeOf(typeof(APPBARDATA));
        d.hWnd = FindWindow("Shell_TrayWnd", null);
        d.lParam = (IntPtr)estado;
        SHAppBarMessage(ABM_SETSTATE, ref d);
    }
}
'@
}
