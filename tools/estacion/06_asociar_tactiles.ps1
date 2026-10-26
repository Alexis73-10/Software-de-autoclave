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
  EST-06 (tanda 17): si Windows no trae MultiDigitizer.exe (ni en System32
  ni en Sysnative), se usa la herramienta propia del programa:
      "<carpeta del exe>\Autoclave.exe" --rol asociar-tactiles
  Criterio para hallar el exe: este script se instala en {app}\estacion, asi
  que Autoclave.exe esta en la carpeta padre de $PSScriptRoot ({app}). La
  herramienta muestra "Toque esta pantalla / Touch this screen" en cada
  monitor, identifica el tactil por Raw Input y escribe en Digimon con el
  mismo formato; recibe la ruta del respaldo de este paso (ya creado aqui
  antes de abrirla, no lo pisa) y escribe en el mismo estacion.log. Codigos
  de salida: 0 todas asociadas, 2 sin administrador, 3 incompleta o
  cancelada, 4 error, 5 sin monitores.
  Si tampoco hay herramienta propia, o falla, se anota en el log y el paso
  termina igual con 0 (EST-06.4: el 06 no interrumpe los demas pasos; el
  Setup cuenta las asociaciones y avisa TactilesRepetir).
  Inverso: 06_revertir_asociar_tactiles.ps1 (igual para las dos herramientas).
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
$herramienta = $null
$argumentos = $null
$propia = $false
foreach ($candidata in @((Join-Path $env:windir 'System32\MultiDigitizer.exe'),
                         (Join-Path $env:windir 'Sysnative\MultiDigitizer.exe'))) {
    if (Test-Path -LiteralPath $candidata) { $herramienta = $candidata; break }
}
if ($null -eq $herramienta) {
    # EST-06: herramienta propia; el exe esta en {app}, carpeta padre de {app}\estacion
    Write-Log 'No se encuentra MultiDigitizer.exe (Configuracion de Tablet PC) en System32 ni Sysnative.' 'WARN'
    $exePropio = Join-Path (Split-Path -Parent $PSScriptRoot) 'Autoclave.exe'
    if (Test-Path -LiteralPath $exePropio) {
        $herramienta = $exePropio
        $propia = $true
        $logEstacion = Join-Path (Split-Path -Parent (Get-RutaRespaldo $Paso)) 'estacion.log'
        $argumentos = '--rol asociar-tactiles --respaldo "{0}" --log "{1}"' -f (Get-RutaRespaldo $Paso), $logEstacion
        Write-Log "Se usa la herramienta propia: $exePropio --rol asociar-tactiles."
    } else {
        Write-Log "Tampoco se encuentra la herramienta propia ($exePropio): no se asocian las pantallas tactiles. Repita la asociacion despues de instalar." 'WARN'
    }
}

if ($null -ne $herramienta) {
    # Respaldo del estado previo (solo la primera vez), antes de abrir cualquiera de las dos herramientas
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
        try {
            if ($propia) {
                $proceso = Start-Process -FilePath $herramienta -ArgumentList $argumentos `
                    -WorkingDirectory (Split-Path -Parent $herramienta) -PassThru -WindowStyle Normal
            } else {
                $proceso = Start-Process -FilePath $herramienta -PassThru -WindowStyle Normal
            }
            # al frente, si Windows lo permite (el asistente del Setup puede taparla)
            try {
                [void]$proceso.WaitForInputIdle(5000)
                Add-Type -AssemblyName Microsoft.VisualBasic
                [Microsoft.VisualBasic.Interaction]::AppActivate($proceso.Id)
            } catch {
                Write-Log "No se pudo traer la herramienta al frente: $($_.Exception.Message)" 'WARN'
            }
            if (-not $proceso.WaitForExit($MinutosEspera * 60 * 1000)) {
                Write-Log "La herramienta no se cerro en $MinutosEspera min: se cierra." 'WARN'
                try { $proceso.Kill() } catch { Write-Log "No se pudo cerrar la herramienta: $($_.Exception.Message)" 'WARN' }
            } elseif ($propia) {
                $codigo = $proceso.ExitCode
                $significado = switch ($codigo) {
                    0 { 'todas las pantallas asociadas' }
                    2 { 'sin permisos de administrador: no se cambio nada' }
                    3 { 'asociacion incompleta o cancelada' }
                    5 { 'no se encontro ningun monitor' }
                    default { 'error de la herramienta (detalle arriba en el log)' }
                }
                $nivelCodigo = if ($codigo -eq 0) { 'INFO' } else { 'WARN' }
                Write-Log "Herramienta propia cerrada (codigo $codigo, $significado)." $nivelCodigo
            } else {
                Write-Log "Herramienta cerrada (codigo $($proceso.ExitCode))."
            }
        } catch {
            # EST-06.4: el fallo de la herramienta no interrumpe los demas pasos
            Write-Log "No se pudo ejecutar la herramienta de asociacion: $($_.Exception.Message)" 'WARN'
        }
    }
}

$despues = Get-ValoresDigimon
$nivel = if ($despues.Count -ge 2) { 'INFO' } else { 'WARN' }
Write-Log "Asociaciones tactiles en HKLM\$($RutaDigimon): $($despues.Count)." $nivel
if ($despues.Count -lt 2) {
    Write-Log 'Quedaron menos de 2 asociaciones: repita la asociacion de pantallas tactiles.' 'WARN'
}
if ($propia -and $despues.Count -gt 0) {
    Write-Log 'Reinicie el equipo: Windows aplica la asociacion de pantallas tactiles al iniciar sesion.' 'WARN'
}
Write-Log "== Fin $Paso =="
