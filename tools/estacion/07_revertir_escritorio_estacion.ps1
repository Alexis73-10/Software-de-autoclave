<#
.SYNOPSIS
  Inverso del paso 7 (EST-09): devuelve el fondo, el modo de la barra de
  tareas y la visibilidad de los iconos del escritorio a lo respaldado.
.DESCRIPTION
  Usa respaldo_07_escritorio_estacion.json (en <RutaDatos>\estacion, solo
  Administradores y SYSTEM): el SID de la cuenta y el valor original de cada
  ajuste que el paso 7 cambio. Para cada uno: si existia, se le devuelve su
  dato y su tipo; si no existia, se borra. Solo restaura los valores de la
  lista ValoresUsuarioGestionados de _comun.ps1 y solo en el perfil de ese
  SID (un respaldo alterado no puede escribir otra clave).

  Valores y APIs (detalle y fuentes en el encabezado de 07_escritorio_estacion.ps1):
  - Fondo: HKCU\Control Panel\Desktop (Wallpaper, WallpaperStyle,
    TileWallpaper) y HKCU\...\Explorer\Wallpapers (BackgroundType); si el
    script corre con la cuenta de la estacion, se vuelve a aplicar con
    user32!SystemParametersInfoW(SPI_SETDESKWALLPAPER, SPIF_UPDATEINIFILE |
    SPIF_SENDCHANGE) en el acto. Una presentacion o Windows Spotlight
    anteriores vuelven en el siguiente inicio de sesion.
  - Barra de tareas: HKCU\...\Explorer\StuckRects3\Settings (se restaura el
    valor completo respaldado); con la cuenta de la estacion, ademas
    shell32!SHAppBarMessage(ABM_SETSTATE) con el estado original (byte 8).
  - Iconos: HKCU\...\Explorer\Advanced\HideIcons; surte efecto en el
    siguiente inicio de sesion (o al reiniciar el Explorador).
  Sin la sesion de la cuenta, todo surte efecto en su siguiente inicio de
  sesion (si su perfil no esta cargado, se carga NTUSER.DAT y se descarga).
  Cada valor se revierte por separado; si alguno falla, el respaldo se
  conserva y el script termina con error (el desinstalador lo avisa).
#>
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '07_escritorio_estacion'
$Escritorio  = 'Control Panel\Desktop'
$StuckRects3 = 'Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3'
Write-Log "== Inicio revertir $Paso (WhatIf=$WhatIfPreference) =="

$resp = Read-Respaldo $Paso
$ids = @($script:ValoresUsuarioGestionados | Where-Object { $resp.ContainsKey($_) })
if ($ids.Count -eq 0) {
    Write-Log "Sin respaldo de valores para '$Paso': nada que restaurar."
    if (-not $WhatIfPreference) { Remove-Item -LiteralPath (Get-RutaRespaldo $Paso) -Force -ErrorAction SilentlyContinue }
    Write-Log "== Fin revertir $Paso =="
    return
}
$sid = [string]$resp['Sid']
if (-not (Test-SidCuenta $sid)) { throw "El respaldo del paso 07 no tiene un SID de cuenta valido ('$sid'): no se restaura nada." }
foreach ($clave in @($resp.Keys)) {
    if (($clave -ne 'Sid') -and ($script:ValoresUsuarioGestionados -notcontains $clave)) {
        Write-Log "Ignorado (no es un valor gestionado por el paso 07): $clave." 'WARN'
    }
}
$enSesion = Test-SesionDeLaCuenta $sid
Write-Log "Cuenta de la estacion: $sid; sesion del proceso=$enSesion."

function Restore-ValoresEscritorio {
    <# Devuelve cada valor respaldado; cuenta los errores en $script:Errores. #>
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)]$Colmena, [switch]$Silencioso)
    foreach ($id in $ids) {
        $ruta, $nombre = $id -split '\|', 2
        $orig = $resp[$id]
        try {
            if ($orig.Existia) {
                $tipo = [string]$orig.Tipo
                if ($script:TiposValorUsuario -notcontains $tipo) { throw "tipo respaldado invalido '$tipo'" }
                if ($PSCmdlet.ShouldProcess("HKCU\$id", 'Restaurar valor original')) {
                    Write-ValorUsuario $Colmena.Raiz $ruta $nombre $orig.Valor $tipo
                    if (-not $Silencioso) { Write-Log "Restaurado: HKCU\$id = '$(Format-ValorUsuario $orig.Valor)'." }
                }
            } elseif ($PSCmdlet.ShouldProcess("HKCU\$id", 'Borrar (no existia antes)')) {
                Remove-ValorUsuario $Colmena.Raiz $ruta $nombre
                if (-not $Silencioso) { Write-Log "Eliminado (no existia antes): HKCU\$id." }
            }
        } catch {
            $script:Errores++
            Write-Log "No se pudo restaurar HKCU\${id}: $($_.Exception.Message)" 'ERROR'
        }
    }
}

$script:Errores = 0
$fondo = ''
$estadoBarra = $null
$colmena = Open-ColmenaUsuario $sid
try {
    Restore-ValoresEscritorio $colmena
    $w = Get-ValorUsuario $colmena.Raiz $Escritorio 'Wallpaper'
    if ($w.Existe) { $fondo = [string]$w.Valor }
    $b = Get-ValorUsuario $colmena.Raiz $StuckRects3 'Settings'
    if ($b.Existe -and ($b.Tipo -eq 'Binary') -and (@($b.Valor).Count -ge 9)) { $estadoBarra = [int](@($b.Valor)[8] -band 0x03) }

    if ($enSesion -and ($script:Errores -eq 0)) {
        Initialize-Win32Escritorio
        if ($PSCmdlet.ShouldProcess("'$fondo'", 'SystemParametersInfo(SPI_SETDESKWALLPAPER)')) {
            if ([EspecifikaEscritorio07]::FijarFondo($fondo)) {
                Write-Log "Fondo original aplicado en la sesion actual ('$fondo')."
            } else {
                Write-Log "SystemParametersInfo no aplico el fondo original (error $([Runtime.InteropServices.Marshal]::GetLastWin32Error())): queda en el registro para el siguiente inicio de sesion." 'WARN'
            }
            # SystemParametersInfo reescribe Wallpaper (y puede tocar el tipo
            # de fondo): se vuelve a dejar exactamente lo respaldado.
            Restore-ValoresEscritorio $colmena -Silencioso
        }
        if (($null -ne $estadoBarra) -and $PSCmdlet.ShouldProcess('Barra de tareas', "SHAppBarMessage(ABM_SETSTATE, $estadoBarra)")) {
            [EspecifikaEscritorio07]::FijarEstadoBarra($estadoBarra)
            Write-Log "Barra de tareas devuelta al estado original ($estadoBarra) en la sesion actual."
        }
    } elseif (-not $enSesion) {
        Write-Log 'El proceso no corre con la cuenta de la estacion: fondo, barra e iconos vuelven en su siguiente inicio de sesion.'
    }
} finally {
    Close-ColmenaUsuario $colmena
}

if ($script:Errores -gt 0) {
    # el respaldo se conserva para volver a intentarlo; el puente devuelve 1 y el desinstalador avisa
    throw "No se pudieron restaurar $($script:Errores) valores del paso 07 (detalle arriba en el log)."
}
if (-not $WhatIfPreference) {
    foreach ($id in $ids) { $resp.Remove($id) }
    $resp.Remove('Sid')
    if ($resp.Count -eq 0) { Remove-Item -LiteralPath (Get-RutaRespaldo $Paso) -Force -ErrorAction SilentlyContinue }
    else { Save-Respaldo $Paso $resp }
}
Write-Log 'Iconos del escritorio: vuelven a su estado en el siguiente inicio de sesion (o al reiniciar el Explorador).'
Write-Log "== Fin revertir $Paso =="
