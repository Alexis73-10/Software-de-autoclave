"""D11-4 y D11-5 (tanda 11, N11): Setup con "Instalación limpia" y paso 06 de
la estación (asociación de los táctiles con las pantallas).

Pruebas ESTÁTICAS (prohibido ejecutar el Setup y los .ps1): comprueban que el
.iss y los scripts declaran lo que piden las decisiones. La lógica Pascal se
revisa además con una tabla de casos en
docs/informes/tanda11/N11_instalador_limpia_tactiles.md y se comprueba que
ISCC.exe la compila. El análisis con el parser de PowerShell (sin ejecutar) va
al final y se salta si no hay powershell.exe."""
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

PASO06 = "06_asociar_tactiles.ps1"
REVERTIR06 = "06_revertir_asociar_tactiles.ps1"


def _funcion(nombre: str) -> str:
    """Cuerpo de una función/procedimiento Pascal del .iss (hasta la siguiente)."""
    m = re.search(rf"^(function|procedure) {nombre}\b.*?(?=^(function|procedure) |\Z)", CODIGO, re.M | re.S)
    assert m, nombre
    return m.group(0)


def _mensaje(idioma: str, clave: str) -> str:
    m = re.search(rf"^{idioma}\.{clave}=(.*)$", ISS, re.M)
    assert m, f"{idioma}.{clave}"
    return m.group(1)


def _ps(nombre: str) -> str:
    return (ESTACION / nombre).read_text(encoding="ascii")


# ── D11-4: Actualizar o Instalación limpia ───────────────────────────────────

def test_pagina_con_version_vieja_actualizar_por_defecto_y_limpia():
    iw = _funcion("InitializeWizard")
    bloque = iw[iw.index("Modo = ModoActualizar"):]
    assert "CustomMessage('ActActualizar')" in bloque
    assert "CustomMessage('OpcionLimpia')" in bloque
    assert bloque.index("ActActualizar") < bloque.index("OpcionLimpia")
    assert "Values[0] := True" in bloque
    assert "conserva" in _mensaje("es", "ActActualizar")


def test_pagina_misma_version_reparar_limpia_desinstalar_sin_reinstalar():
    iw = _funcion("InitializeWizard")
    bloque = iw[iw.index("Modo = ModoMantenimiento"):iw.index("Modo = ModoActualizar")]
    orden = [bloque.index(f"CustomMessage('{m}')") for m in ("MantReparar", "OpcionLimpia", "MantDesinstalar")]
    assert orden == sorted(orden)
    assert "Reinstalar" not in ISS and "DesinstalarParaReinstalar" not in ISS


def test_doble_confirmacion_con_no_por_defecto():
    conf = _funcion("ConfirmarLimpia")
    assert conf.count("MsgBox(") == 2
    assert conf.count("MB_DEFBUTTON2") == 2 and conf.count("IDYES") == 2
    segunda_es = _mensaje("es", "LimpiaConfirmar2").lower()
    assert "ciclos registrados" in segunda_es and "usuarios" in segunda_es
    segunda_en = _mensaje("en", "LimpiaConfirmar2").lower()
    assert "cycle" in segunda_en and "users" in segunda_en
    # el modo limpio solo lo fija la página, tras las dos confirmaciones
    nbc = _funcion("NextButtonClick")
    assert "Result := ConfirmarLimpia" in nbc
    assert nbc.index("ConfirmarLimpia") < nbc.index("Modo := ModoLimpia")
    assert CODIGO.count("Modo := ModoLimpia") == 1


def test_borrado_solo_en_preparar_instalacion_despues_del_respaldo():
    pti = _funcion("PrepareToInstall")
    assert "Modo = ModoLimpia" in pti and "EjecutarLimpia" in pti
    limpia = _funcion("EjecutarLimpia")
    i_respaldo = limpia.index("CopiarArbol(")
    i_borrado = limpia.index("BorrarContenidoDatos(")
    assert i_respaldo < i_borrado
    # si el respaldo falla (copia o verificación) se sale con mensaje antes de borrar
    tramo = limpia[i_respaldo:i_borrado]
    assert "LimpiaRespaldoFallo" in tramo and "exit" in tramo
    assert "ContarArbol(" in tramo                     # verifica la copia (archivos y bytes)
    # con el programa abierto no se toca nada
    assert limpia.index("AutoclaveEnEjecucion") < i_respaldo
    # el respaldo (con estacion\ y la base de usuarios) no queda legible por Usuarios
    assert limpia.index("ProtegerRespaldos") < i_respaldo
    proteger = _funcion("ProtegerRespaldos")
    assert "/inheritance:r" in proteger and "*S-1-5-32-544" in proteger and "*S-1-5-18" in proteger
    assert "Users" not in proteger and "S-1-5-32-545" not in proteger
    # la única llamada que borra datos es esa
    assert CODIGO.count("BorrarContenidoDatos(") == 2   # definición + llamada


def test_carpeta_de_respaldo_fuera_de_la_que_se_borra_y_con_fecha():
    assert "{commonappdata}\\Especifika\\Autoclave_respaldos" in CODIGO
    assert "'yyyymmdd-hhnnss'" in CODIGO
    borrar = _funcion("BorrarContenidoDatos")
    # no borra la carpeta de la estación (respaldos de los pasos de Windows)
    assert "'estacion'" in borrar
    # nunca sigue enlaces: un punto de reanálisis cancela antes de copiar/borrar
    assert "FILE_ATTRIBUTE_REPARSE_POINT" in _funcion("CopiarArbol")


def test_version_mas_nueva_se_sigue_negando():
    ini = _funcion("InitializeSetup")
    assert "CustomMessage('VersionMasNueva')" in ini and "Result := False" in ini


def test_silencioso_nunca_hace_limpia():
    # en modo silencioso no hay página: Modo queda en Actualizar/Mantenimiento
    ini = _funcion("InitializeSetup")
    assert "ModoLimpia" not in ini
    assert "ModoLimpia" not in _funcion("CurStepChanged").split("ssPostInstall")[0]


# ── D11-5: asociación de los táctiles ────────────────────────────────────────

def test_tarea_tactiles_hija_de_estacion_marcada_y_solo_con_dos_monitores():
    m = re.search(r'^Name: "estacion\\tactiles"; Description: "\{cm:TareaTactiles\}"(.*)$', ISS, re.M)
    assert m, "falta la tarea estacion\\tactiles"
    assert "unchecked" not in m.group(1)
    assert "Check: HayDosMonitores" in m.group(1)
    hay = _funcion("HayDosMonitores")
    assert "GetSystemMetrics(SM_CMONITORS) >= 2" in hay


def test_paso_06_se_aplica_marcado_antes_y_cuenta_asociaciones():
    ae = _funcion("AplicarEstacion")
    bloque = ae[ae.index("WizardIsTaskSelected('estacion\\tactiles')"):]
    assert bloque.index("MarcarPaso('06')") < bloque.index("EjecutarPaso('06', 'Aplicar'")
    assert "WizardSilent" in bloque                    # nunca abre la herramienta sin asistente
    assert "ContarAsociacionesTactiles" in bloque
    assert "RegGetValueNames(HKLM64, ClaveDigimon" in _funcion("ContarAsociacionesTactiles")
    assert "ClaveDigimon = 'SOFTWARE\\Microsoft\\Wisp\\Pen\\Digimon';" in CODIGO
    # aviso al final, sin fallar la instalación
    assert "TactilesRepetir" in CODIGO
    assert "repita la asociación de pantallas táctiles" in _mensaje("es", "TactilesRepetir").lower()


def test_reparar_no_reabre_la_herramienta_y_desinstalar_revierte_06_primero():
    assert "'06'" not in _funcion("RepararEstacion")
    orden = [CODIGO.index(f"EjecutarReversion('{p}'") for p in ("06", "05", "04", "02", "01")]
    assert orden == sorted(orden)


def test_scripts_06_instalados_y_en_el_puente():
    for nombre in (PASO06, REVERTIR06):
        assert (ESTACION / nombre).is_file()
        assert f'Source: "..\\estacion\\{nombre}"; DestDir: "{{app}}\\estacion"' in ISS
    puente = (INSTALADOR / "estacion_setup.ps1").read_text(encoding="ascii")
    assert "ValidateSet('01', '02', '04', '05', '06')" in puente
    assert f"'06' = @('{PASO06}', '{REVERTIR06}')" in puente


def test_script_06_abre_multidigitizer_y_registra_en_el_log():
    s = _ps(PASO06)
    assert "MultiDigitizer.exe" in s
    assert "Wisp\\Pen\\Digimon" in s
    assert "Assert-Administrador" in s and "Write-Log" in s
    assert "Read-Host" not in s
    # respaldo del estado previo una sola vez (idempotente), antes de abrir la herramienta
    assert s.index("Save-Respaldo") < s.index("Start-Process")
    assert "ContainsKey('DigimonAntes')" in s
    # espera acotada: nunca deja el Setup colgado
    assert "WaitForExit(" in s
    # menos de 2 no es falla
    assert "exit 1" not in s


def test_revertir_06_solo_toca_la_clave_digimon_y_lo_creado():
    s = _ps(REVERTIR06)
    assert "Wisp\\Pen\\Digimon" in s
    assert "DigimonAntes" in s
    assert "DeleteValue" in s and "Read-Host" not in s
    # no escribe en ninguna otra clave: una sola ruta de registro
    rutas = set(re.findall(r"SOFTWARE\\[\w\\]+", s))
    assert rutas == {"SOFTWARE\\Microsoft\\Wisp\\Pen\\Digimon"}, rutas


def test_leeme_estacion_paso_06_y_puertos_usb():
    leeme = (ESTACION / "LEEME.md").read_text(encoding="utf-8")
    assert PASO06 in leeme and REVERTIR06 in leeme
    assert "puerto USB" in leeme or "puertos USB" in leeme


def test_mensajes_nuevos_en_los_dos_idiomas():
    for clave in ("ActTitulo", "ActSubtitulo", "ActExplicacion", "ActActualizar", "OpcionLimpia",
                  "LimpiaConfirmar1", "LimpiaConfirmar2", "LimpiaProgramaAbierto",
                  "LimpiaRespaldoFallo", "LimpiaBorradoFallo", "TareaTactiles", "Paso06",
                  "TactilesRepetir"):
        _mensaje("es", clave)
        _mensaje("en", clave)


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="sin powershell.exe")
def test_parser_de_powershell_sin_errores():
    """Solo analiza (Parser::ParseFile): no ejecuta ningún script."""
    archivos = [str(ESTACION / PASO06), str(ESTACION / REVERTIR06), str(INSTALADOR / "estacion_setup.ps1")]
    lista = ",".join(f"'{a}'" for a in archivos)
    orden = (
        f"$r=@(); foreach($f in @({lista})){{$t=$null;$e=$null;"
        "[void][System.Management.Automation.Language.Parser]::ParseFile($f,[ref]$t,[ref]$e);"
        "$r+=@{f=$f;n=$e.Count}}; $r | ConvertTo-Json -Compress"
    )
    salida = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", orden],
                            capture_output=True, text=True, timeout=120)
    datos = json.loads(salida.stdout)
    if isinstance(datos, dict):
        datos = [datos]
    assert [d["n"] for d in datos] == [0, 0, 0], datos
