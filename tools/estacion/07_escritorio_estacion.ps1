<#
.SYNOPSIS
  Paso 7: escritorio de la estacion (EST-09, tanda 18): fondo de Especifika,
  barra de tareas con ocultar automaticamente e iconos del escritorio ocultos.
.DESCRIPTION
  Decision EST-09 (docs/mis_plans/decisiones_tanda_18.md). El PC tiene una
  sola cuenta: la que instala y entra con el inicio automatico. Los tres
  ajustes son del perfil de esa cuenta (HKCU). Como el script corre elevado,
  no se usa el HKCU del proceso: se resuelve la cuenta (-Usuario/-Dominio; si
  no llegan, Winlogon DefaultUserName/DefaultDomainName del paso 01; si
  tampoco, la cuenta que ejecuta) y se escribe en HKEY_USERS\<SID>. Con la
  sesion de esa cuenta cerrada se carga su NTUSER.DAT (reg load) y se
  descarga al terminar (_comun.ps1, Open-ColmenaUsuario).

  Ajuste -> valor de registro / API -> fuente -> cuando surte efecto:
  1. Fondo de pantalla: la imagen de la intro (ui_qml/assets/fondos/
     fondo-arranque.png), instalada por el Setup como
     {app}\estacion\fondo_estacion.png (carpeta programa, solo
     administradores escriben).
     - HKCU\Control Panel\Desktop: WallpaperStyle = "10" (REG_SZ, Rellenar /
       Fill) y TileWallpaper = "0" (REG_SZ, sin mosaico); Wallpaper = ruta de
       la imagen (REG_SZ). Fuente: Microsoft Learn, "Desktop wallpaper"
       (directiva Wallpaper/WallpaperStyle) y SystemParametersInfoW,
       SPI_SETDESKWALLPAPER.
     - HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Wallpapers:
       BackgroundType = 0 (REG_DWORD; 0 Imagen, 1 Color solido, 2 Presentacion,
       3 Windows Spotlight): tipo de fondo "Imagen", sin presentacion ni
       Spotlight. Valor no documentado formalmente por Microsoft (es el que
       escribe Configuracion > Personalizacion > Fondo); DECISION SIN CONFIRMAR.
     - API: user32!SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, ruta,
       SPIF_UPDATEINIFILE | SPIF_SENDCHANGE). Fija la MISMA imagen en todos
       los monitores (quita un fondo distinto por monitor) y lo aplica en el
       acto. Solo se llama si el script corre con la cuenta de la estacion
       (si no, la API cambiaria el fondo de otra cuenta); en ese caso el
       fondo queda en el registro y surte efecto en el siguiente inicio de
       sesion de la cuenta (el Setup ya pide reiniciar).
  2. Barra de tareas "Ocultar automaticamente":
     - HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3,
       valor Settings (REG_BINARY): byte 8, bit 0x01 = ocultar
       automaticamente (0x03 activa, 0x02 desactiva); solo se cambia ese bit.
       Formato no documentado por Microsoft (lo escribe el Explorador al
       guardar el estado de la barra); DECISION SIN CONFIRMAR. Si el valor no
       existe (perfil donde el Explorador nunca corrio) se anota un aviso y no
       se crea: Reparar lo vuelve a intentar.
     - API: shell32!SHAppBarMessage(ABM_SETSTATE, lParam = ABS_AUTOHIDE |
       ABS_ALWAYSONTOP). Fuente: Microsoft Learn, "ABM_SETSTATE message".
       Solo con la cuenta de la estacion: aplica en el acto y el Explorador
       guarda el estado el mismo (si solo se cambiara el registro con el
       Explorador abierto, este lo pisaria al cerrar la sesion). Sin esa
       sesion: surte efecto en el siguiente inicio de sesion. No se reinicia
       el Explorador a la fuerza (DECISION SIN CONFIRMAR).
     - Se mantiene ademas el ocultamiento total mientras corre Autoclave
       (ui_qml/barra_tareas.py, sin cambios).
  3. Iconos del escritorio ocultos:
     - HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced:
       HideIcons = 1 (REG_DWORD), el mismo que "Ver > Mostrar iconos del
       escritorio" del escritorio. Fuente: valor del Explorador, documentado
       en Microsoft Learn junto a la directiva "Hide and disable all items on
       the desktop" (NoDesktop) como alternativa por usuario; DECISION SIN
       CONFIRMAR. Surte efecto en el siguiente inicio de sesion (o al
       reiniciar el Explorador).

  Respaldo: respaldo_07_escritorio_estacion.json en <RutaDatos>\estacion
  (solo Administradores y SYSTEM), con el SID de la cuenta y cada valor
  original (tambien si no existia). Se guarda solo la primera vez: volver a
  correr el paso no pisa el original. Idempotente: un valor que ya esta se
  anota "Sin cambio". Log: estacion.log. -WhatIf simula (solo lee; si la
  sesion de la cuenta esta cerrada carga su perfil para leerlo y lo descarga).
  Inverso: 07_revertir_escritorio_estacion.ps1.
.EXAMPLE
  .\07_escritorio_estacion.ps1 -WhatIf
  .\07_escritorio_estacion.ps1 -Usuario operador
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Usuario,
    [string]$Dominio,
    # Por defecto la que instala el Setup junto al script; suelto en el
    # repositorio, la imagen de la intro.
    [string]$Imagen
)
. "$PSScriptRoot\_comun.ps1"
Assert-Administrador
$Paso = '07_escritorio_estacion'
$Escritorio  = 'Control Panel\Desktop'
$Wallpapers  = 'Software\Microsoft\Windows\CurrentVersion\Explorer\Wallpapers'
$Avanzado    = 'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'
$StuckRects3 = 'Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3'
Write-Log "== Inicio $Paso (WhatIf=$WhatIfPreference) =="

if (-not $Imagen) {
    $Imagen = Join-Path $PSScriptRoot 'fondo_estacion.png'
    if (-not (Test-Path -LiteralPath $Imagen)) {
        $repo = Join-Path $PSScriptRoot '..\..\src\autoclave\ui_qml\assets\fondos\fondo-arranque.png'
        if (Test-Path -LiteralPath $repo) { $Imagen = $repo }
    }
}
if (-not (Test-Path -LiteralPath $Imagen -PathType Leaf)) { throw "No se encuentra la imagen de fondo ${Imagen}: no se cambia nada." }
$Imagen = [IO.Path]::GetFullPath($Imagen)

$cuenta = Resolve-CuentaEstacion -Usuario $Usuario -Dominio $Dominio
$enSesion = Test-SesionDeLaCuenta $cuenta.Sid
Write-Log "Cuenta de la estacion: $($cuenta.Nombre) ($($cuenta.Sid)); sesion del proceso=$enSesion; imagen=$Imagen."

$resp = Read-Respaldo $Paso
if ($resp.ContainsKey('Sid') -and ($resp['Sid'] -ne $cuenta.Sid)) {
    throw "El respaldo del paso 07 es de otra cuenta ($($resp['Sid'])): revierta primero con 07_revertir_escritorio_estacion.ps1. No se cambia nada."
}
if ((-not $resp.ContainsKey('Sid')) -and (-not $WhatIfPreference)) {
    $resp['Sid'] = $cuenta.Sid
    Save-Respaldo $Paso $resp
}

$autoocultar = $false
$colmena = Open-ColmenaUsuario $cuenta.Sid
try {
    # 1. Fondo: estilo antes que la ruta (SystemParametersInfo lee el estilo del registro)
    Set-ValorUsuario -Paso $Paso -Colmena $colmena -Ruta $Escritorio -Nombre 'WallpaperStyle' -Valor '10' -Tipo String
    Set-ValorUsuario -Paso $Paso -Colmena $colmena -Ruta $Escritorio -Nombre 'TileWallpaper' -Valor '0' -Tipo String
    Set-ValorUsuario -Paso $Paso -Colmena $colmena -Ruta $Escritorio -Nombre 'Wallpaper' -Valor $Imagen -Tipo String
    Set-ValorUsuario -Paso $Paso -Colmena $colmena -Ruta $Wallpapers -Nombre 'BackgroundType' -Valor 0 -Tipo DWord

    # 3. Iconos del escritorio ocultos
    Set-ValorUsuario -Paso $Paso -Colmena $colmena -Ruta $Avanzado -Nombre 'HideIcons' -Valor 1 -Tipo DWord

    # 2. Barra de tareas: solo el bit 0x01 del byte 8 de StuckRects3\Settings
    $barra = Get-ValorUsuario $colmena.Raiz $StuckRects3 'Settings'
    if ((-not $barra.Existe) -or ($barra.Tipo -ne 'Binary') -or (@($barra.Valor).Count -lt 9)) {
        Write-Log "No existe HKCU\$StuckRects3\Settings (o no tiene el formato esperado): no se fija ocultar automaticamente. Inicie sesion con la cuenta y use Reparar o repita el paso." 'WARN'
    } else {
        $nuevo = [byte[]]@($barra.Valor)   # copia nueva
        $nuevo[8] = [byte]($nuevo[8] -bor 0x01)
        Set-ValorUsuario -Paso $Paso -Colmena $colmena -Ruta $StuckRects3 -Nombre 'Settings' -Valor $nuevo -Tipo Binary
        $autoocultar = $true
    }
} finally {
    Close-ColmenaUsuario $colmena
}

if ($enSesion) {
    Initialize-Win32Escritorio
    if ($PSCmdlet.ShouldProcess($Imagen, 'SystemParametersInfo(SPI_SETDESKWALLPAPER) en todos los monitores')) {
        if ([EspecifikaEscritorio07]::FijarFondo($Imagen)) {
            Write-Log 'Fondo aplicado en la sesion actual (todos los monitores).'
        } else {
            Write-Log "SystemParametersInfo no aplico el fondo (error $([Runtime.InteropServices.Marshal]::GetLastWin32Error())): queda en el registro para el siguiente inicio de sesion." 'WARN'
        }
    }
    if ($autoocultar -and $PSCmdlet.ShouldProcess('Barra de tareas', 'SHAppBarMessage(ABM_SETSTATE, ABS_AUTOHIDE)')) {
        [EspecifikaEscritorio07]::FijarEstadoBarra(0x03)
        Write-Log 'Barra de tareas en ocultar automaticamente (sesion actual).'
    }
    Write-Log 'Iconos del escritorio: se ocultan en el siguiente inicio de sesion (o al reiniciar el Explorador).'
} else {
    Write-Log 'El proceso no corre con la cuenta de la estacion: fondo, barra e iconos surten efecto en su siguiente inicio de sesion.'
}
Write-Log "== Fin $Paso =="
