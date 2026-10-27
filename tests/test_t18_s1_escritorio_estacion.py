"""Tanda 18, s1 (EST-09): paso 07 de la estación, escritorio de la estación
(fondo de Especifika en modo Rellenar, barra de tareas con ocultar
automáticamente e íconos del escritorio ocultos) y su integración en el Setup.

Prohibido ejecutar el Setup, ISCC con instalación o los .ps1, y escribir en el
registro de Windows. Por eso:
- `test_texto_*`: ESTÁTICAS, solo comprueban lo que declara el texto del .iss
  o de los .ps1 (no prueban que funcione en Windows);
- `test_parser_*`: solo analizan los .ps1 con el parser de PowerShell (no los
  ejecutan); se saltan sin powershell.exe.
La comprobación real queda en las pruebas manuales I-07b e I-15 (hoja de
banco) y en la lista de verificación de tools/instalador/LEEME.md."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ESTACION = RAIZ / "tools" / "estacion"
INSTALADOR = RAIZ / "tools" / "instalador"
ISS = (INSTALADOR / "autoclave.iss").read_text(encoding="utf-8-sig")
CODIGO = ISS[ISS.index("[Code]"):]

PASO07 = "07_escritorio_estacion.ps1"
REVERTIR07 = "07_revertir_escritorio_estacion.ps1"
FONDO_ORIGEN = RAIZ / "src" / "autoclave" / "ui_qml" / "assets" / "fondos" / "fondo-arranque.png"

pytestmark = pytest.mark.req("EST-09")

ESCRITORIO = "Control Panel\\Desktop"
WALLPAPERS = "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Wallpapers"
AVANZADO = "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced"
STUCKRECTS3 = "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\StuckRects3"
GESTIONADOS = {
    f"{ESCRITORIO}|WallpaperStyle", f"{ESCRITORIO}|TileWallpaper", f"{ESCRITORIO}|Wallpaper",
    f"{WALLPAPERS}|BackgroundType", f"{AVANZADO}|HideIcons", f"{STUCKRECTS3}|Settings",
}


def _ps(nombre: str) -> str:
    return (ESTACION / nombre).read_text(encoding="ascii")


def _cuerpo(texto: str) -> str:
    """Código del script sin el bloque de ayuda <# ... #> inicial."""
    return texto.split("#>", 1)[1]


def _funcion(nombre: str) -> str:
    m = re.search(rf"^(function|procedure) {nombre}\b.*?(?=^(function|procedure) |\Z)", CODIGO, re.M | re.S)
    assert m, nombre
    return m.group(0)


def _mensaje(idioma: str, clave: str) -> str:
    m = re.search(rf"^{idioma}\.{clave}=(.*)$", ISS, re.M)
    assert m, f"{idioma}.{clave}"
    return m.group(1)


def _gestionados_usuario() -> set[str]:
    bloque = re.search(r"\$script:ValoresUsuarioGestionados = @\((.*?)\n\)", _ps("_comun.ps1"), re.S).group(1)
    return set(re.findall(r"'([^']+\|[^']+)'", bloque))


def _valores_escritos_07() -> dict[str, tuple[str, str]]:
    """(Ruta|Nombre) -> (valor, tipo) de cada Set-ValorUsuario del paso 07."""
    s = _cuerpo(_ps(PASO07))
    variables = dict(re.findall(r"^\$(\w+)\s*=\s*'([^']+)'", s, re.M))
    escritos = {}
    for linea in s.splitlines():
        if "Set-ValorUsuario " not in linea:
            continue
        ruta = variables[re.search(r"-Ruta \$(\w+)", linea).group(1)]
        nombre = re.search(r"-Nombre '([^']+)'", linea).group(1)
        valor = re.search(r"-Valor ('[^']*'|\S+)", linea).group(1)
        tipo = re.search(r"-Tipo (\w+)", linea).group(1)
        escritos[f"{ruta}|{nombre}"] = (valor, tipo)
    return escritos


# ── Scripts del paso 07 ──────────────────────────────────────────────────────

def test_texto_scripts_existen_ascii_usan_comun_y_admiten_whatif():
    for nombre in (PASO07, REVERTIR07):
        s = _ps(nombre)                                    # ASCII (lo exige el resto de pruebas)
        assert '. "$PSScriptRoot\\_comun.ps1"' in s, nombre
        assert "[CmdletBinding(SupportsShouldProcess)]" in s, nombre
        assert "Assert-Administrador" in s, nombre
        assert "$Paso = '07_escritorio_estacion'" in s, nombre
        assert "WhatIf=$WhatIfPreference" in s, nombre
        assert "Write-Log" in s, nombre
        assert "Read-Host" not in s and "ConfirmImpact" not in s, nombre
        # nunca reinicia el Explorador a la fuerza
        cuerpo = _cuerpo(s)
        assert "Stop-Process" not in cuerpo and "taskkill" not in cuerpo.lower(), nombre


def test_texto_escribe_los_tres_ajustes_con_sus_valores():
    escritos = _valores_escritos_07()
    assert escritos[f"{ESCRITORIO}|WallpaperStyle"] == ("'10'", "String")    # Rellenar
    assert escritos[f"{ESCRITORIO}|TileWallpaper"] == ("'0'", "String")
    assert escritos[f"{ESCRITORIO}|Wallpaper"] == ("$Imagen", "String")
    assert escritos[f"{WALLPAPERS}|BackgroundType"] == ("0", "DWord")        # tipo «Imagen»
    assert escritos[f"{AVANZADO}|HideIcons"] == ("1", "DWord")
    assert escritos[f"{STUCKRECTS3}|Settings"] == ("$nuevo", "Binary")
    # la lista blanca cubre exactamente lo que escribe el paso
    assert set(escritos) == GESTIONADOS == _gestionados_usuario()


def test_texto_estilo_antes_que_la_ruta_del_fondo():
    s = _cuerpo(_ps(PASO07))
    # SystemParametersInfo lee WallpaperStyle del registro al aplicar la ruta
    assert s.index("'WallpaperStyle'") < s.index("'Wallpaper' ") < s.index("FijarFondo")


def test_texto_barra_solo_bit_autoocultar_del_byte_8():
    s = _cuerpo(_ps(PASO07))
    assert "$nuevo[8] = [byte]($nuevo[8] -bor 0x01)" in s
    assert "-lt 9" in s                                  # formato inesperado -> aviso, sin escribir
    assert "FijarEstadoBarra(0x03)" in s                 # ABS_AUTOHIDE | ABS_ALWAYSONTOP


def test_texto_fondo_instalado_junto_al_script_y_misma_imagen_que_la_intro():
    s = _cuerpo(_ps(PASO07))
    assert "Join-Path $PSScriptRoot 'fondo_estacion.png'" in s
    assert "fondo-arranque.png" in s                     # suelto en el repositorio
    assert "throw" in s[s.index("fondo_estacion.png"):s.index("Resolve-CuentaEstacion")]
    assert FONDO_ORIGEN.is_file()


def test_texto_api_solo_en_la_sesion_de_la_cuenta():
    for nombre in (PASO07, REVERTIR07):
        s = _cuerpo(_ps(nombre))
        assert "Test-SesionDeLaCuenta" in s, nombre
        i = s.index("FijarFondo")
        assert "if ($enSesion" in s[:i], nombre
        assert "$PSCmdlet.ShouldProcess(" in s[s.rindex("if ($enSesion", 0, i):i], nombre


def test_texto_comun_api_y_valores_documentados():
    comun = _ps("_comun.ps1")
    assert "SPI_SETDESKWALLPAPER = 0x0014" in comun
    assert "SPIF_UPDATEINIFILE | SPIF_SENDCHANGE" in comun
    assert "ABM_SETSTATE = 0x0000000A" in comun and "Shell_TrayWnd" in comun
    cabecera = _ps(PASO07).split("#>", 1)[0]
    for texto in ("WallpaperStyle", "TileWallpaper", "BackgroundType", "StuckRects3", "HideIcons",
                  "SPI_SETDESKWALLPAPER", "ABM_SETSTATE", "Microsoft Learn", "siguiente inicio de sesion",
                  "DECISION SIN CONFIRMAR"):
        assert texto in cabecera, texto


def test_texto_perfil_de_la_cuenta_del_inicio_automatico():
    comun = _ps("_comun.ps1")
    resolver = comun[comun.index("function Resolve-CuentaEstacion"):comun.index("function Test-SesionDeLaCuenta")]
    assert "DefaultUserName" in resolver and "DefaultDomainName" in resolver
    assert "WindowsIdentity]::GetCurrent()" in resolver
    abrir = comun[comun.index("function Open-ColmenaUsuario"):comun.index("function Close-ColmenaUsuario")]
    assert "Registry]::Users.OpenSubKey($Sid" in abrir
    assert "reg.exe load" in abrir and "NTUSER.DAT" in abrir and "ProfileList" in abrir
    assert "reg.exe unload" in comun
    for nombre in (PASO07, REVERTIR07):
        s = _cuerpo(_ps(nombre))
        assert "Open-ColmenaUsuario" in s and "Close-ColmenaUsuario $colmena" in s, nombre
        assert s.index("finally") < s.index("Close-ColmenaUsuario $colmena"), nombre


def test_texto_respaldo_una_sola_vez_y_con_ausencia():
    comun = _ps("_comun.ps1")
    fijar = comun[comun.index("function Set-ValorUsuario"):comun.index("function Initialize-Win32Escritorio")]
    assert "ValoresUsuarioGestionados -notcontains $id" in fijar
    assert "if (-not $resp.ContainsKey($id))" in fijar
    assert "Existia = $actual.Existe" in fijar
    assert fijar.index("Save-Respaldo") < fijar.index("Write-ValorUsuario")
    assert "Sin cambio" in fijar                         # idempotente
    s = _cuerpo(_ps(PASO07))
    assert "$resp['Sid'] = $cuenta.Sid" in s
    assert "-ne $cuenta.Sid" in s                        # respaldo de otra cuenta -> no cambia nada


def test_texto_reversion_exacta_solo_valores_gestionados():
    s = _cuerpo(_ps(REVERTIR07))
    assert "$script:ValoresUsuarioGestionados | Where-Object { $resp.ContainsKey($_) }" in s
    assert "Test-SidCuenta $sid" in s
    assert "if ($orig.Existia)" in s
    assert "Write-ValorUsuario $Colmena.Raiz $ruta $nombre $orig.Valor $tipo" in s
    assert "Remove-ValorUsuario $Colmena.Raiz $ruta $nombre" in s
    assert "TiposValorUsuario -notcontains $tipo" in s
    # tras SystemParametersInfo se vuelve a dejar exactamente lo respaldado
    i = s.index("FijarFondo")
    assert "Restore-ValoresEscritorio $colmena -Silencioso" in s[i:]
    # la barra vuelve al estado original del byte 8
    assert "-band 0x03" in s and "FijarEstadoBarra($estadoBarra)" in s
    # un fallo conserva el respaldo y termina con error
    assert s.index("throw \"No se pudieron restaurar") < s.index("Remove-Item -LiteralPath (Get-RutaRespaldo $Paso)", s.index("$script:Errores -gt 0"))


def test_texto_lista_blanca_de_usuario_no_toca_la_de_hklm():
    comun = _ps("_comun.ps1")
    bloque = re.search(r"\$script:ValoresGestionados = @\((.*?)\n\)", comun, re.S).group(1)
    assert "StuckRects3" not in bloque and "HideIcons" not in bloque


# ── Puente y Setup ───────────────────────────────────────────────────────────

def test_texto_puente_admite_el_paso_07_con_la_cuenta():
    puente = (INSTALADOR / "estacion_setup.ps1").read_text(encoding="ascii")
    assert "ValidateSet('01', '02', '04', '05', '06', '07')" in puente
    assert f"'07' = @('{PASO07}', '{REVERTIR07}')" in puente
    assert "elseif ($Paso -eq '07' -and $Accion -eq 'Aplicar' -and $Usuario)" in puente
    assert "& $ruta -Usuario $Usuario -Dominio $Dominio\n" in puente


def test_texto_iss_copia_scripts_y_fondo():
    for nombre in (PASO07, REVERTIR07):
        assert (ESTACION / nombre).is_file()
        assert f'Source: "..\\estacion\\{nombre}"; DestDir: "{{app}}\\estacion"' in ISS
    assert ('Source: "..\\..\\src\\autoclave\\ui_qml\\assets\\fondos\\fondo-arranque.png"; '
            'DestDir: "{app}\\estacion"; DestName: "fondo_estacion.png"') in ISS
    # la ruta relativa del .iss (desde tools/instalador) apunta a la imagen de la intro
    assert (INSTALADOR / "../../src/autoclave/ui_qml/assets/fondos/fondo-arranque.png").resolve() == FONDO_ORIGEN.resolve()


def test_texto_iss_aplica_07_con_la_casilla_entre_05_y_06():
    ae = _funcion("AplicarEstacion")
    bloque = ae[ae.index("if WizardIsTaskSelected('estacion') then"):ae.index("if WizardIsTaskSelected('sinlogo') then")]
    assert bloque.index("EjecutarPaso('05', 'Aplicar'") < bloque.index("MarcarPaso('07')") \
        < bloque.index("EjecutarPaso('07', 'Aplicar'") < bloque.index("EjecutarPaso('06', 'Aplicar'")
    # sin casilla propia
    assert "estacion\\escritorio" not in ISS
    tareas = re.findall(r'^Name: "([\w\\]+)"; Description:', ISS, re.M)
    assert tareas == ["autoarranque", "estacion", "estacion\\tactiles", "sinlogo"]
    # el paso 07 aplica al perfil de la cuenta que instala
    assert "' -Usuario \"' + Usuario + '\" -Dominio \"' + Dominio + '\"'" in bloque[bloque.index("MarcarPaso('07')"):]


def test_texto_iss_fallo_del_07_no_interrumpe():
    ae = _funcion("AplicarEstacion")
    i = ae.index("EjecutarPaso('07', 'Aplicar'")
    tramo = ae[i:ae.index("// D11-5", i)]
    assert "Fallas := Fallas + '- ' + CustomMessage('Paso07') + #13#10;" in tramo
    assert "exit" not in tramo.lower() and "Abort" not in tramo and "RaiseException" not in tramo
    assert "Result := False" not in tramo


def test_texto_iss_reparar_reaplica_07_y_desinstalar_lo_revierte_primero():
    reparar = _funcion("RepararEstacion")
    assert "ReaplicarPaso('07', 'Paso07', Fallas);" in reparar
    orden = [CODIGO.index(f"EjecutarReversion('{p}'") for p in ("07", "06", "05", "04", "02", "01")]
    assert orden == sorted(orden)
    assert "EjecutarReversion('07', 'Paso07', Fallas);" in _funcion("RevertirEstacion")


def test_texto_iss_mensajes_paso07_en_los_dos_idiomas():
    assert _mensaje("es", "Paso07") == "escritorio de la estación (paso 07)"
    assert _mensaje("en", "Paso07") == "station desktop (step 07)"


def test_texto_leeme_documentan_el_paso_07():
    estacion = (ESTACION / "LEEME.md").read_text(encoding="utf-8")
    assert PASO07 in estacion and REVERTIR07 in estacion
    for texto in ("StuckRects3", "HideIcons", "SPI_SETDESKWALLPAPER", "WallpaperStyle"):
        assert texto in estacion, texto
    instalador = (INSTALADOR / "LEEME.md").read_text(encoding="utf-8")
    assert "paso 07" in instalador.lower() or "Paso07" in instalador
    assert "07, 06, 05, 04, 02, 01" in instalador


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="sin powershell.exe")
def test_parser_de_powershell_sin_errores():
    """Solo analiza (Parser::ParseFile): no ejecuta ningún script."""
    archivos = [str(ESTACION / n) for n in ("_comun.ps1", PASO07, REVERTIR07)]
    archivos.append(str(INSTALADOR / "estacion_setup.ps1"))
    lista = ",".join(f"'{a}'" for a in archivos)
    orden = (
        f"$r=@(); foreach($f in @({lista})){{$t=$null;$e=$null;"
        "[void][System.Management.Automation.Language.Parser]::ParseFile($f,[ref]$t,[ref]$e);"
        "$r+=@{f=$f;n=$e.Count}}; $r | ConvertTo-Json -Compress"
    )
    salida = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", orden],
                            capture_output=True, text=True, timeout=120)
    datos = json.loads(salida.stdout)
    assert [d["n"] for d in datos] == [0, 0, 0, 0], datos
