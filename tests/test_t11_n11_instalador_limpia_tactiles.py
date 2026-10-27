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
    i_vaciado = limpia.index("VaciarDatos(")
    i_borrado = limpia.index("BorrarArbol(")
    assert i_respaldo < i_vaciado < i_borrado
    # si el respaldo falla (copia o verificación) se sale con mensaje antes de mover nada
    tramo = limpia[i_respaldo:i_vaciado]
    assert "LimpiaRespaldoFallo" in tramo and "exit" in tramo
    # verificación: original antes y después, iguales a la copia (archivos y bytes)
    assert limpia.count("ContarArbol(") == 3
    assert "(ArchivosAntes = ArchivosCopia) and (ArchivosDespues = ArchivosCopia)" in limpia
    # si el vaciado no salió, no se borra nada
    assert "Result := VaciarDatos(Datos, CarpetaBorrar);\n  if Result <> '' then\n    exit;" in limpia
    # con el programa abierto no se toca nada
    assert limpia.index("EstadoAutoclave") < i_respaldo
    # el respaldo (con estacion\ y la base de usuarios) no queda legible por Usuarios
    assert limpia.index("ProtegerRespaldos") < i_respaldo
    proteger = _funcion("ProtegerRespaldos")
    assert "/setowner *S-1-5-32-544" in proteger
    assert "/inheritance:r" in proteger and "*S-1-5-32-544" in proteger and "*S-1-5-18" in proteger
    assert "Users" not in proteger and "S-1-5-32-545" not in proteger
    # las únicas llamadas que borran: BorrarArbol (definición, recursión, llamada) y DelTree en ninguna parte
    assert CODIGO.count("BorrarArbol(") == 3
    assert "DelTree(" not in CODIGO


def test_saf01_vaciado_atomico_con_un_solo_renombrado_y_deshacer():
    vaciar = _funcion("VaciarDatos")
    # primero se aparta TODA la carpeta (perfil incluido) con un solo renombrado
    assert vaciar.index("RenameFile(Datos, CarpetaBorrar)") < vaciar.index("CreateDir(Datos)")
    # vuelve solo estacion\
    assert "RenameFile(CarpetaBorrar + '\\estacion', Datos + '\\estacion')" in vaciar
    # si algo falla, se deshace (los datos vuelven) y se informa
    assert "RenameFile(CarpetaBorrar, Datos)" in vaciar
    assert "LimpiaMoverFallo" in vaciar and "LimpiaDeshacerFallo" in vaciar
    # la carpeta apartada vive en la raíz protegida de respaldos
    assert "CarpetaBorrar := CarpetaRespaldo + '_borrar';" in _funcion("EjecutarLimpia")


def test_saf02_enlaces_y_ruta_de_datos():
    limpia = _funcion("EjecutarLimpia")
    i_respaldo = limpia.index("CopiarArbol(")
    for llamada in ("EsEnlace(ExtractFileDir(Datos))", "EsEnlace(Datos)", "EsEnlace(RaizRespaldos)",
                    "RutaDatosValida(Datos)", "EstaDentro(CarpetaRespaldo, Datos)",
                    "EstaDentro(CarpetaBorrar, Datos)"):
        assert limpia.index(llamada) < i_respaldo, llamada
    assert "LimpiaEnlace" in limpia and "LimpiaRutaInvalida" in limpia
    # Tanda 17 (INS-02, decisión de Cristian): la carpeta de datos es
    # X:\Especifika\Autoclave\datos (antes %ProgramData%\Especifika\Autoclave)
    assert "'\\Especifika\\Autoclave\\datos'" in _funcion("RutaDatosValida")
    assert "FILE_ATTRIBUTE_REPARSE_POINT" in _funcion("EsEnlace")
    # la carpeta de respaldo recién creada no puede ser un enlace
    assert "CreateDir(Destino) and not EsEnlace(Destino)" in _funcion("CopiarArbol")
    # el borrado no sigue enlaces: del enlace se borra solo el enlace
    borrar = _funcion("BorrarArbol")
    assert "FILE_ATTRIBUTE_REPARSE_POINT" in borrar
    assert borrar.index("FILE_ATTRIBUTE_REPARSE_POINT") < borrar.index("BorrarArbol(Ruta)")


def test_saf03_wmi_fallido_cuenta_como_abierto():
    estado = _funcion("EstadoAutoclave")
    assert "Result := 2;" in estado.split("except")[1]
    for nombre in ("Autoclave.exe", "AutoclaveBackend.exe", "AutoclaveSettings.exe"):
        assert f"''{nombre}''" in estado
    limpia = _funcion("EjecutarLimpia")
    assert "LimpiaSinComprobar" in limpia and "LimpiaProgramaAbierto" in limpia


def test_saf04_carpeta_que_no_se_lista_es_falla():
    copiar = _funcion("CopiarArbol")
    assert "if not FindFirst(Origen + '\\*', Busqueda) then" in copiar
    contar = _funcion("ContarArbol")
    assert contar.startswith("function ContarArbol") and ": Boolean;" in contar.splitlines()[0]
    assert "Result := FindFirst(Carpeta + '\\*', Busqueda);" in contar


def test_saf05_silencioso_rechaza_la_limpia():
    nbc = _funcion("NextButtonClick")
    bloque = nbc[nbc.index("if Indice = IndiceLimpia then"):nbc.index("else if Indice = IndiceDesinstalar")]
    assert bloque.index("if WizardSilent then") < bloque.index("Modo := ModoLimpia")
    limpia = _funcion("EjecutarLimpia")
    assert limpia.index("if WizardSilent then") < limpia.index("CopiarArbol(")


def test_saf06_sin_versionnum_compara_displayversion_o_se_niega():
    ini = _funcion("InitializeSetup")
    assert "VersionNumDesdeTexto(VersionInstalada)" in ini
    assert "CustomMessage('VersionDesconocida')" in ini
    assert "Comparacion := -1" not in ini
    conv = _funcion("VersionNumDesdeTexto")
    assert "Ord(Letra[1]) - Ord('a') + 1" in conv


def test_carpeta_de_respaldo_fuera_de_la_que_se_borra_y_con_fecha():
    # Tanda 17 (INS-02, decisión de Cristian): los respaldos van a
    # X:\Especifika\Autoclave_respaldos (misma unidad que datos\), no a {commonappdata}
    assert "ExtractFileDir(RaizAutoclave) + '\\Autoclave_respaldos'" in _funcion("RaizRespaldos")
    assert "'yyyymmdd-hhnnss'" in CODIGO
    # no borra la carpeta de la estación (respaldos de los pasos de Windows): vuelve a su lugar
    assert "\\estacion" in _funcion("VaciarDatos")
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
    # EST-09 (tanda 18): el puente admite además el paso 07 (escritorio de la estación)
    assert "ValidateSet('01', '02', '04', '05', '06', '07')" in puente
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


def test_saf08_revertir_valor_por_valor_y_tipos():
    s = _ps(REVERTIR06)
    assert "function ConvertTo-ValorRegistro" in s
    assert "[string[]]" in s and "[byte[]]" in s
    assert "ConvertTo-ValorRegistro $previo.Valor $tipo" in s
    bucle = s[s.index("foreach ($nombre in @($clave.GetValueNames()))"):]
    assert bucle.index("try {") < bucle.index("DeleteValue") < bucle.index("} catch {")
    # con errores conserva el respaldo y falla (el desinstalador avisa)
    assert s.index("if ($errores -gt 0)") < s.index("$resp.Remove($k)")


def test_saf07_y_texto_de_progreso_del_paso_06():
    leeme = (ESTACION / "LEEME.md").read_text(encoding="utf-8")
    assert "también borra las asociaciones rehechas después" in leeme
    ae = _funcion("AplicarEstacion")
    assert ae.index("CustomMessage('TactilesTocar')") < ae.index("EjecutarPaso('06'")
    assert "AppActivate" in _ps(PASO06)


def test_leeme_estacion_paso_06_y_puertos_usb():
    leeme = (ESTACION / "LEEME.md").read_text(encoding="utf-8")
    assert PASO06 in leeme and REVERTIR06 in leeme
    assert "puerto USB" in leeme or "puertos USB" in leeme


def test_mensajes_nuevos_en_los_dos_idiomas():
    for clave in ("ActTitulo", "ActSubtitulo", "ActExplicacion", "ActActualizar", "OpcionLimpia",
                  "LimpiaConfirmar1", "LimpiaConfirmar2", "LimpiaProgramaAbierto",
                  "LimpiaRespaldoFallo", "LimpiaMoverFallo", "LimpiaDeshacerFallo", "LimpiaEnlace",
                  "LimpiaRutaInvalida", "LimpiaSinComprobar", "LimpiaSilenciosa",
                  "VersionDesconocida", "TareaTactiles", "Paso06", "TactilesRepetir", "TactilesTocar"):
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
