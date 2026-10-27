"""Tanda 20, s3 (T20-05): Setup con Modbus (tools/instalador/autoclave.iss):
página «Red de los módulos de E/S» y paso 08, contraseña web del módulo y
prueba de conexión con `Autoclave.exe --rol configurar-modulo` (T20-04).

Prohibido ejecutar el Setup, ISCC o los .ps1 de la estación. Por eso:
- `test_texto_*`: ESTÁTICAS, solo comprueban lo que declara el texto del .iss;
- `test_replica_*`: réplica en Python de una función Pascal sencilla, para
  fijar el formato que se parsea (no ejecutan el Pascal);
- `test_ejecuta_*`: ejecutan con powershell.exe el MISMO comando de SOLO
  LECTURA que arma el .iss (lista de adaptadores); se saltan sin powershell.exe.
La comprobación real queda en M-7 (hoja de banco) y en la lista de
verificación de tools/instalador/LEEME.md."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
INSTALADOR = RAIZ / "tools" / "instalador"
ESTACION = RAIZ / "tools" / "estacion"
ISS = (INSTALADOR / "autoclave.iss").read_text(encoding="utf-8-sig")
CODIGO = ISS[ISS.index("[Code]"):]

pytestmark = pytest.mark.req("T20-05")

CODIGOS = ("ok", "backend_activo", "sin_conexion", "composicion", "orden", "firmware", "expansor",
           "clave_invalida", "clave_no_quedo", "error", "argumentos")


def _funcion(nombre: str) -> str:
    m = re.search(rf"^(function|procedure) {nombre}\b.*?(?=^(function|procedure) |\Z)", CODIGO, re.M | re.S)
    assert m, nombre
    return m.group(0)


def _mensaje(idioma: str, clave: str) -> str:
    m = re.search(rf"^{idioma}\.{clave}=(.*)$", ISS, re.M)
    assert m, f"{idioma}.{clave}"
    return m.group(1)


def _seccion(nombre: str) -> str:
    m = re.search(rf"^\[{nombre}\]\s*$(.*?)(?=^\[\w+\]\s*$)", ISS, re.M | re.S)
    assert m, nombre
    return m.group(1)


def _sin_comentarios_pascal(texto: str) -> str:
    return "\n".join(l.split("//", 1)[0] for l in texto.splitlines())


# ── Página «Red de los módulos de E/S» ───────────────────────────────────────

def test_texto_pagina_de_red_propia_con_casilla_marcada_y_sin_tarea_nueva():
    crear = _funcion("CrearPaginaRed")
    assert "CreateCustomPage(Despues, CustomMessage('RedTitulo'), CustomMessage('RedSubtitulo'))" in crear
    assert "TNewCheckBox.Create(PaginaRed)" in crear
    assert "CasillaRed.Caption := CustomMessage('RedCasilla')" in crear
    assert "CasillaRed.Checked := True;" in crear
    assert "TNewListBox.Create(PaginaRed)" in crear
    assert "LlenarListaRed(MacPreseleccion)" in crear
    iw = _funcion("InitializeWizard")
    assert iw.index("PaginaCuenta := CreateInputQueryPage(wpSelectTasks") < iw.index("CrearPaginaRed(PaginaCuenta.ID)")
    # la casilla de red NO es una tarea: [Tasks] queda igual
    tareas = re.findall(r'^Name: "([\w\\]+)"; Description:', _seccion("Tasks"), re.M)
    assert tareas == ["autoarranque", "estacion", "estacion\\tactiles", "sinlogo"]
    assert _mensaje("es", "RedCasilla") == "Configurar la red de los módulos"
    assert _mensaje("es", "RedTitulo") == "Red de los módulos de E/S"


def test_texto_lista_de_adaptadores_solo_lectura_y_solo_ethernet():
    cr = _funcion("ConsultarRed")
    assert "ExecAndCaptureOutput(" in cr
    assert "Get-NetAdapter -Physical" in cr and "NdisPhysicalMedium -eq 14" in cr and "-not $_.Virtual" in cr
    for cmdlet in ("Set-Net", "New-Net", "Remove-Net", "Set-Dns", "netsh", "Disable-Net", "Enable-Net"):
        assert cmdlet not in cr, cmdlet
    assert "''A=''" in cr and "''O=''" in cr
    # solo las líneas A= (Ethernet físico con MAC válida) se ofrecen
    assert "if Ethernet and (NormalizarMac(Mac) = '') then" in cr
    llenar = _funcion("LlenarListaRed")
    assert "if AdapEthernet[I] then" in llenar
    # preselección: la elegida/guardada; si no, la que ya tiene 192.168.3.10; si no, ninguna
    assert "ListaTieneIp(AdapIps[I], IpEstacionModulos)" in llenar
    assert "Elegida := -1;" in llenar and "ListaRed.ItemIndex := Elegida;" in llenar
    assert "IpEstacionModulos = '192.168.3.10';" in CODIGO
    assert "'Adaptador08'" in _funcion("MacPreseleccion")


def test_texto_no_deja_seguir_sin_elegir_conflicto_y_aviso_de_puerta_de_enlace():
    nb = _funcion("NextButtonClick")
    bloque = nb[nb.index("CurPageID = PaginaRed.ID"):nb.index("CurPageID = PaginaClave.ID")]
    assert "if not CasillaRed.Checked then" in bloque
    assert bloque.index("if not CasillaRed.Checked then") < bloque.index("AdaptadorElegido := '';")
    i_sin = bloque.index("ListaRed.ItemIndex < 0")
    assert "CustomMessage('RedFaltaAdaptador')" in bloque[i_sin:i_sin + 200]
    assert "Result := False" in bloque[i_sin:i_sin + 200]
    i_val = bloque.index("ValidarRed(Indice, Advertir)")
    assert "Result := False" in bloque[i_val:bloque.index("if Advertir then")]
    aviso = bloque[bloque.index("if Advertir then"):]
    assert "CustomMessage('RedPerderaRed')" in aviso and "MB_YESNO or MB_DEFBUTTON2" in aviso
    assert "<> IDYES" in aviso and "Result := False" in aviso
    vr = _funcion("ValidarRed")
    assert "(J <> I) and IpsEnRedModulos(AdapIps[J])" in vr
    assert "CustomMessage('RedConflicto')" in vr
    assert "Advertir := not OtraPuerta;" in vr
    assert "PERDERÁ" in _mensaje("es", "RedPerderaRed")


def test_texto_parametro_adaptador_silencioso():
    ini = _funcion("InitializeSetup")
    assert "ExpandConstant('{param:ADAPTADOR|}')" in ini
    bloque = ini[ini.index("{param:ADAPTADOR|}"):ini.index("if not HayInstalacion then")]
    assert "IndiceAdaptadorEthernet(AdaptadorParametro)" in bloque
    assert "CustomMessage('RedAdaptadorInvalido')" in bloque and "Result := False" in bloque
    assert "ValidarRed(I, AdvertirRed)" in bloque
    # sin /ADAPTADOR= y sin asistente: no se toca la red y se anota
    assert "else if WizardSilent then" in bloque
    assert "no se toca la red de los módulos" in bloque
    # sin asistente no se muestran ni validan las páginas nuevas
    skip = _funcion("ShouldSkipPage")
    assert "(PageID = PaginaRed.ID) then\n    Result := WizardSilent" in skip.replace("\r\n", "\n")
    assert "(PageID = PaginaClave.ID) then\n    Result := WizardSilent" in skip.replace("\r\n", "\n")
    # también en Reparar: las páginas nuevas van antes de la rama que salta las tareas
    assert skip.index("PaginaRed.ID") < skip.index("ModoReparar")


def test_texto_paso_08_marcado_antes_con_la_mac_y_tambien_en_reparar():
    arm = _funcion("AplicarRedModulos")
    i_marca = arm.index("MarcarPaso('08');")
    i_mac = arm.index("RegWriteStringValue(HKLM64, '{#ClaveEstacion}', 'Adaptador08', Mac);")
    i_aplica = arm.index("EjecutarPaso('08', 'Aplicar', ' -Adaptador \"' + Mac + '\"')")
    assert i_marca < i_mac < i_aplica
    # solo una MAC validada (12 hexadecimales) llega a la línea de comandos
    assert "Mac := NormalizarMac(AdaptadorElegido);" in arm
    assert arm.index("if Mac = '' then") < i_marca
    # un fallo no interrumpe la instalación
    tramo = arm[i_aplica:]
    assert "RedFallida := True;" in tramo and "Abort" not in tramo and "RaiseException" not in tramo
    csc = _funcion("CurStepChanged")
    i_red = csc.index("AplicarRedModulos;")
    assert csc.index("AplicarZona;") < i_red < csc.index("ProbarModulo;") < csc.index("RepararEstacion;")
    assert i_red < csc.index("exit;")
    # el paso 08 es independiente de la casilla de la estación
    assert "WizardIsTaskSelected" not in arm


def test_texto_desinstalar_revierte_el_08_primero():
    rev = _funcion("RevertirEstacion")
    orden = [rev.index(f"EjecutarReversion('{p}'") for p in ("08", "07", "06", "05", "04", "02", "01")]
    assert orden == sorted(orden)
    assert "EjecutarReversion('08', 'Paso08', Fallas);" in rev
    for idioma in ("es", "en"):
        assert "08" in _mensaje(idioma, "Paso08")


def test_texto_archivos_del_paso_08_instalados():
    archivos = _seccion("Files")
    for nombre in ("_red_modulos_puras.ps1", "08_red_modulos.ps1", "08_revertir_red_modulos.ps1"):
        assert (ESTACION / nombre).is_file(), nombre
        assert f'Source: "..\\estacion\\{nombre}"; DestDir: "{{app}}\\estacion"; Flags: ignoreversion' in archivos


def test_texto_no_instala_enlace_io():
    # decisión 4: enlace Modbus fijo, sin archivo de selección de enlace
    assert "enlace_io" not in ISS


# ── Contraseña web del módulo ────────────────────────────────────────────────

def test_texto_pagina_de_contrasena_con_dos_campos_ocultos():
    crear = _funcion("CrearPaginaClave")
    assert "CreateInputQueryPage(Despues, CustomMessage('ClaveModuloTitulo')" in crear
    assert "PaginaClave.Add(CustomMessage('ClaveModuloClave'), True);" in crear
    assert "PaginaClave.Add(CustomMessage('ClaveModuloRepetir'), True);" in crear
    assert "CrearPaginaClave(PaginaRed.ID)" in _funcion("InitializeWizard")
    # sin MaxLength: un texto pegado más largo se rechaza, nunca se recorta en silencio
    assert "MaxLength" not in CODIGO


def test_texto_validacion_1_a_6_ascii_imprimibles_y_obligatoria_solo_si_es_nueva():
    assert "LargoMaxClaveModulo = 6;" in CODIGO
    val = _funcion("ValidarClaveModulo")
    assert "PaginaClave.Values[0] <> PaginaClave.Values[1]" in val
    assert "Length(PaginaClave.Values[0]) > LargoMaxClaveModulo" in val
    assert "CaracteresImprimibles(PaginaClave.Values[0])" in val
    assert "if ClaveModuloObligatoria then" in val
    imp = _funcion("CaracteresImprimibles")
    assert "(Ord(Texto[K]) < 32) or (Ord(Texto[K]) > 126)" in imp
    obl = _funcion("ClaveModuloObligatoria")
    assert "Result := (Modo = ModoNuevo) or (Modo = ModoLimpia);" in obl
    nb = _funcion("NextButtonClick")
    bloque = nb[nb.index("CurPageID = PaginaClave.ID"):]
    assert "ValidarClaveModulo" in bloque[:300] and "Result := False" in bloque[:300]
    for clave in ("ClaveModuloFalta", "ClaveModuloDistintas", "ClaveModuloLarga", "ClaveModuloCaracteres"):
        assert f"'{clave}'" in val
        _mensaje("es", clave)
        _mensaje("en", clave)


def test_replica_validacion_de_la_contrasena():
    """Réplica de ValidarClaveModulo (mismo orden de reglas)."""
    def validar(a: str, b: str, obligatoria: bool) -> str:
        if a == "" and b == "":
            return "ClaveModuloFalta" if obligatoria else ""
        if a != b:
            return "ClaveModuloDistintas"
        if len(a) > 6:
            return "ClaveModuloLarga"
        if any(ord(c) < 32 or ord(c) > 126 for c in a):
            return "ClaveModuloCaracteres"
        return ""
    assert validar("", "", True) == "ClaveModuloFalta"
    assert validar("", "", False) == ""                     # actualizar/reparar: no se cambia
    assert validar("abc", "abd", False) == "ClaveModuloDistintas"
    assert validar("1234567", "1234567", True) == "ClaveModuloLarga"
    assert validar("añob", "añob", True) == "ClaveModuloCaracteres"
    assert validar("a\tb", "a\tb", True) == "ClaveModuloCaracteres"
    assert validar("a b~1!", "a b~1!", True) == ""
    assert validar("x", "x", True) == ""


def test_texto_contrasena_solo_por_archivo_en_tmp_y_se_borra():
    esc = _funcion("EscribirArchivoClave")
    assert "SaveStringToFile(Ruta, PaginaClave.Values[0], False)" in esc
    pm = _funcion("ProbarModulo")
    assert "ArchivoClave := ExpandConstant('{tmp}\\clave_modulo.txt');" in pm
    assert "Parametros := Parametros + ' --clave-archivo \"' + ArchivoClave + '\"'" in pm
    i_try = pm.index("  try\n") if "  try\n" in pm else pm.index("  try\r\n")
    i_finally = pm.index("finally")
    assert i_try < pm.index("EscribirArchivoClave(ArchivoClave)") < pm.index("Exec(") < i_finally
    final = pm[i_finally:pm.index("end;", pm.index("PaginaClave.Values[1] := '';"))]
    assert "if FileExists(ArchivoClave) then" in final and "DeleteFile(ArchivoClave);" in final
    assert "PaginaClave.Values[0] := '';" in final and "PaginaClave.Values[1] := '';" in final
    # sin asistente no se cambia
    assert "ConClave := (not WizardSilent)" in pm


def test_texto_la_contrasena_nunca_va_al_log_mensajes_ni_linea_de_comandos():
    codigo = _sin_comentarios_pascal(CODIGO)
    secretos = ("PaginaClave.Values", "PaginaCuenta.Values[1]", "PaginaCuenta.Values[2]")
    # en ninguna llamada a Log/MsgBox/Format/FmtMessage (sentencia completa, hasta el ';')
    for llamada in ("Log(", "MsgBox(", "SuppressibleMsgBox(", "Format(", "FmtMessage("):
        for m in re.finditer(re.escape(llamada), codigo):
            sentencia = codigo[m.start():codigo.index(";", m.start())]
            for s in secretos:
                assert s not in sentencia, (llamada, sentencia)
    # ni en los parámetros de ningún Exec/ExecAndCaptureOutput
    for m in re.finditer(r"\bExec(?:AndCaptureOutput)?\(", codigo):
        sentencia = codigo[m.start():codigo.index(";", m.start())]
        assert "PaginaClave" not in sentencia, sentencia
    # ni concatenada con un argumento ' --...'
    for linea in codigo.splitlines():
        if "' --" in linea or "'--" in linea:
            assert "PaginaClave" not in linea, linea
    for m in re.finditer(r"Parametros :=", codigo):
        assert "PaginaClave" not in codigo[m.start():codigo.index(";", m.start())]
    # la contraseña solo se lee en la validación, al escribir el archivo y para saber si hay
    usos = {_nombre_funcion_en(m.start()) for m in re.finditer(r"PaginaClave\.Values\[", CODIGO)}
    assert usos == {"ValidarClaveModulo", "EscribirArchivoClave", "ProbarModulo"}, usos
    pm = _funcion("ProbarModulo")
    lecturas = [l.strip() for l in pm.splitlines() if "PaginaClave.Values[" in l]
    assert lecturas == ["ConClave := (not WizardSilent) and (PaginaClave <> nil) and (PaginaClave.Values[0] <> '');",
                        "PaginaClave.Values[0] := '';", "PaginaClave.Values[1] := '';"]


def _nombre_funcion_en(pos: int) -> str:
    previas = list(re.finditer(r"^(?:function|procedure) (\w+)", CODIGO[:pos], re.M))
    return previas[-1].group(1)


# ── Prueba de conexión (decisión 5) ──────────────────────────────────────────

def test_texto_invoca_el_rol_configurar_modulo():
    pm = _funcion("ProbarModulo")
    assert "Parametros := '--rol configurar-modulo --resultado \"' + ArchivoResultado + '\"';" in pm
    assert "ArchivoResultado := ExpandConstant('{tmp}\\resultado_modulo.json');" in pm
    assert ("Exec(ExpandConstant('{app}\\Autoclave.exe'), Parametros, ExpandConstant('{app}'),\n"
            "      SW_HIDE, ewWaitUntilTerminated, Salida);") in pm.replace("\r\n", "\n")
    assert "LoadStringFromFile(ArchivoResultado, Contenido)" in pm
    assert "CampoJson(Texto, 'codigo')" in pm
    # código desconocido -> error; "ok" solo con salida 0 y "ok": true
    assert "Pos('|' + Codigo + '|', CodigosModulo) = 0" in pm
    assert "(Salida <> 0) or (Texto = '') or (CampoJson(Texto, 'ok') <> 'true')" in pm
    # no aborta la instalación
    assert "Abort" not in pm and "RaiseException" not in pm
    # sin asistente solo el log
    assert "if WizardSilent then\n    TextoResultadoModulo := ''" in pm.replace("\r\n", "\n")


def test_texto_sin_resultado_no_se_adivina_por_el_codigo_de_salida():
    """Un Autoclave.exe sin el rol sale con 2 (error de argumentos de argparse),
    el mismo número que el rol usa para backend_activo: sin JSON, error."""
    pm = _funcion("ProbarModulo")
    assert "if Codigo = '' then\n    Codigo := 'error';" in pm
    assert "CodigoModuloPorSalida" not in CODIGO


def test_texto_pagina_final_del_resultado():
    iw = _funcion("InitializeWizard")
    assert "PaginaResultado := CreateOutputMsgPage(wpInstalling, CustomMessage('ModuloTitulo')," in iw
    skip = _funcion("ShouldSkipPage")
    assert "(PageID = PaginaResultado.ID) then\n    Result := TextoResultadoModulo = ''" in skip.replace("\r\n", "\n")
    pm = _funcion("ProbarModulo")
    assert "PaginaResultado.MsgLabel.Caption := TextoResultadoModulo;" in pm
    assert "FmtMessage(CustomMessage('ModuloRes_ok'), [CampoJson(Texto, 'modelo')," in pm
    for campo in ("'n_modulos'", "'firmware'", "'mac'", "'clave_cambiada'"):
        assert campo in pm
    assert "FmtMessage(CustomMessage('ModuloRes_' + Codigo), [])" in pm
    assert "CustomMessage('RedFallo')" in pm                   # un fallo del paso 08 se muestra ahí


def test_texto_un_texto_por_codigo_en_los_dos_idiomas():
    m = re.search(r"CodigosModulo = '([^']+)';", CODIGO)
    assert m and m.group(1) == "|" + "|".join(CODIGOS) + "|"
    for codigo in CODIGOS:
        for idioma in ("es", "en"):
            texto = _mensaje(idioma, f"ModuloRes_{codigo}")
            assert texto.strip(), (idioma, codigo)
            if codigo != "ok":
                assert ("Qué hacer" if idioma == "es" else "What to do") in texto, (idioma, codigo)
    ok = _mensaje("es", "ModuloRes_ok")
    for marca in ("%1", "%2", "%3", "%4", "%5"):
        assert marca in ok
    assert "cable" in _mensaje("es", "ModuloRes_sin_conexion")
    assert "adaptador" in _mensaje("es", "ModuloRes_sin_conexion")


def test_texto_mensajes_nuevos_en_los_dos_idiomas():
    for clave in ("RedTitulo", "RedSubtitulo", "RedCasilla", "RedExplicacion", "RedSinAdaptadores",
                  "RedActualizarLista", "RedElemento", "RedCableConectado", "RedCableDesconectado",
                  "RedDeshabilitado", "RedFaltaAdaptador", "RedConflicto", "RedPerderaRed",
                  "RedAdaptadorInvalido", "AplicandoRed", "Paso08", "RedFallo", "ClaveModuloTitulo",
                  "ClaveModuloSubtitulo", "ClaveModuloExplicacionNueva", "ClaveModuloExplicacionOpcional",
                  "ClaveModuloClave", "ClaveModuloRepetir", "ProbandoModulo", "ModuloTitulo",
                  "ModuloSubtitulo", "ModuloClaveSi", "ModuloClaveNo", "ModuloClaveNoPedida", "ModuloRepetir"):
        _mensaje("es", clave)
        _mensaje("en", clave)


def test_replica_campo_json_sobre_el_formato_del_rol():
    """Réplica de CampoJson sobre un JSON como el del rol (json.dump con
    ensure_ascii=True e indent=2: una clave por línea)."""
    def campo(texto: str, nombre: str) -> str:
        p = texto.find(f'"{nombre}":')
        if p < 0:
            return ""
        resto = texto[p + len(nombre) + 3:].lstrip()
        if resto.startswith('"'):
            resto = resto[1:]
            q = resto.find('"')
            return resto[:q] if q >= 0 else ""
        k = 0
        while k < len(resto) and resto[k] not in ",\r\n}":
            k += 1
        return resto[:k].strip()
    datos = {"ok": True, "codigo": "ok", "modelo": "M31-XAE6400-U", "composicion": "GXAXX0A00,GAXXXA000",
             "n_modulos": 5, "firmware": "9232-0-13", "mac": "005404849DB1", "clave_cambiada": False,
             "texto_es": "Conexión correcta", "texto_en": "ok", "accion_es": "", "accion_en": ""}
    texto = json.dumps(datos, ensure_ascii=True, indent=2)
    assert campo(texto, "ok") == "true"
    assert campo(texto, "codigo") == "ok"
    assert campo(texto, "modelo") == "M31-XAE6400-U"
    assert campo(texto, "n_modulos") == "5"
    assert campo(texto, "firmware") == "9232-0-13"
    assert campo(texto, "mac") == "005404849DB1"
    assert campo(texto, "clave_cambiada") == "false"
    assert campo(texto, "composicion") == "GXAXX0A00,GAXXXA000"
    assert campo(texto, "inexistente") == ""
    # "ok" al final, sin coma
    assert campo(json.dumps({"codigo": "sin_conexion", "ok": False}, indent=2), "ok") == "false"
    # misma lógica que el Pascal
    cj = _funcion("CampoJson")
    assert "Pos('\"' + Nombre + '\":', Texto)" in cj
    assert "(Resto[K] <> ',') and (Resto[K] <> #13) and (Resto[K] <> #10) and (Resto[K] <> '}')" in cj


def test_replica_ip_en_red_de_los_modulos_y_mac():
    """Réplica de IpEnRedModulos y NormalizarMac."""
    def ip_en_red(ip: str) -> bool:
        ip = ip.strip()
        if not ip.startswith("192.168.3."):
            return False
        resto = ip[len("192.168.3."):]
        return 1 <= len(resto) <= 3 and resto.isdigit() and int(resto) <= 255

    def mac(texto: str) -> str:
        s = texto.strip().upper().replace("-", "").replace(":", "")
        return s if len(s) == 12 and all(c in "0123456789ABCDEF" for c in s) else ""
    assert ip_en_red("192.168.3.10") and ip_en_red("192.168.3.0") and ip_en_red("192.168.3.255")
    assert not ip_en_red("192.168.3.256") and not ip_en_red("192.168.30.1") and not ip_en_red("192.168.3.")
    assert not ip_en_red("192.168.3.1a")
    assert mac("00-54-04-84-9d-b1") == mac("00:54:04:84:9D:B1") == "005404849DB1"
    assert mac('00-54-04-84-9D-B1" -X') == "" and mac("") == ""
    assert "PrefijoRedModulos = '192.168.3.';" in CODIGO
    ipr = _funcion("IpEnRedModulos")
    assert "StrToIntDef(Resto, 999) <= 255" in ipr and "(Length(Resto) < 1) or (Length(Resto) > 3)" in ipr
    nm = _funcion("NormalizarMac")
    assert "if Length(S) <> 12 then" in nm and "Result := S;" in nm


def test_texto_leeme_del_instalador_documenta_t20_05():
    leeme = (INSTALADOR / "LEEME.md").read_text(encoding="utf-8")
    for texto in ("Red de los módulos de E/S", "/ADAPTADOR=", "Adaptador08", "Contraseña web del módulo",
                  "--rol configurar-modulo", "--clave-archivo", "08, 07, 06, 05, 04, 02, 01"):
        assert texto in leeme, texto


def _comando_pascal(funcion: str) -> str:
    """Texto que el .iss pasa a powershell.exe tras -Command (literales Pascal
    concatenados, '' -> ')."""
    cuerpo = _funcion(funcion)
    tramo = cuerpo[cuerpo.index("'-NoProfile"):cuerpo.index("'', SW_HIDE")]
    texto = "".join(p.replace("''", "'") for p in re.findall(r"'((?:[^']|'')*)'", tramo))
    return texto[texto.index('-Command "') + len('-Command "'):texto.rindex('"')]


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="sin powershell.exe")
def test_ejecuta_consulta_de_adaptadores_solo_lectura():
    """El mismo comando de ConsultarRed (solo lee adaptadores, IPv4 y rutas)."""
    orden = _comando_pascal("ConsultarRed")
    for cmdlet in ("Set-", "New-", "Remove-", "Disable-", "Enable-", "Restart-", "netsh"):
        assert cmdlet not in orden, cmdlet
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", orden], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        pytest.skip("Get-NetAdapter no disponible aquí (el Setup muestra la lista vacía)")
    lineas = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    assert lineas, "sin adaptadores"
    for linea in lineas:
        assert re.fullmatch(r"[AO]=[^|]*\|[^|]*\|[^|]*\|[^|]*\|[0-9.;]*\|[01]", linea), linea
        if linea.startswith("A="):
            assert re.fullmatch(r"[0-9A-F]{2}(-[0-9A-F]{2}){5}", linea[2:].split("|")[0]), linea
