"""Tanda 17, s1: Setup (tools/instalador/autoclave.iss) con zona horaria
(INS-01), unidad y disposición X:\\Especifika\\Autoclave\\{programa,datos}
(INS-02) y el mensaje de repetición de los táctiles (EST-06, punto 3); y
tools/estacion/_comun.ps1 leyendo RutaDatos del registro.

Prohibido ejecutar el Setup, ISCC con instalación o los .ps1. Por eso:
- `test_texto_*`: ESTÁTICAS, solo comprueban lo que declara el texto del .iss
  o del .ps1 (no prueban que funcione en Windows);
- `test_replica_*`: réplica en Python de una función Pascal sencilla, para
  fijar el formato que se parsea (no ejecutan el Pascal);
- `test_ejecuta_*`: ejecutan con powershell.exe el MISMO comando que arma el
  .iss (extraído del texto), sobre una carpeta temporal o solo leyendo (bus de
  los discos); se saltan sin powershell.exe;
- `test_parser_*`: solo analizan los .ps1 con el parser (no los ejecutan).
La comprobación real queda en la lista de pruebas manuales de
tools/instalador/LEEME.md."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from autoclave.utils import resources

RAIZ = Path(__file__).resolve().parents[1]
INSTALADOR = RAIZ / "tools" / "instalador"
ESTACION = RAIZ / "tools" / "estacion"
ISS = (INSTALADOR / "autoclave.iss").read_text(encoding="utf-8-sig")
CODIGO = ISS[ISS.index("[Code]"):]
COMUN = (ESTACION / "_comun.ps1").read_text(encoding="ascii")

INS01 = pytest.mark.req("INS-01")
INS02 = pytest.mark.req("INS-02")
EST06 = pytest.mark.req("EST-06")


def _funcion(nombre: str) -> str:
    m = re.search(rf"^(function|procedure) {nombre}\b.*?(?=^(function|procedure) |\Z)", CODIGO, re.M | re.S)
    assert m, nombre
    return m.group(0)


def _seccion(nombre: str) -> str:
    m = re.search(rf"^\[{nombre}\]\s*$(.*?)(?=^\[\w+\]\s*$)", ISS, re.M | re.S)
    assert m, nombre
    return m.group(1)


def _mensaje(idioma: str, clave: str) -> str:
    m = re.search(rf"^{idioma}\.{clave}=(.*)$", ISS, re.M)
    assert m, f"{idioma}.{clave}"
    return m.group(1)


# ── INS-01: zona horaria ─────────────────────────────────────────────────────

@INS01
def test_texto_pagina_de_zona_lista_del_registro_ordenada_y_preseleccion_actual():
    cargar = _funcion("CargarZonas")
    assert "RegGetSubkeyNames(HKLM64, ClaveZonas" in cargar
    assert "'Display'" in cargar
    assert "ClaveZonas = 'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Time Zones';" in CODIGO
    # zona actual de Windows (lo mismo que devuelve tzutil /g)
    assert "'TimeZoneKeyName'" in cargar
    assert "ClaveZonaActual = 'SYSTEM\\CurrentControlSet\\Control\\TimeZoneInformation';" in CODIGO
    # orden por desfase (de '(UTC±hh:mm)') y luego por nombre
    assert "ZonaDesfase[I] < ZonaDesfase[J]" in _funcion("ZonaAntes")
    assert "'(UTC'" in _funcion("DesfaseZona")
    crear = _funcion("CrearPaginaZona")
    assert "CreateInputOptionPage(" in crear and "CompareText(ZonaIds[I], ZonaElegida) = 0" in crear
    # fecha y hora locales de referencia, refrescadas al mostrar la página
    assert "GetDateTimeString(" in _funcion("TextoZonaExplicacion")
    assert "SubCaptionLabel.Caption := TextoZonaExplicacion" in _funcion("CurPageChanged")


@INS01
def test_replica_desfase_de_ejemplos():
    """Réplica en Python de DesfaseZona para fijar el formato que se parsea."""
    def desfase(nombre):
        if nombre[:4].upper() != "(UTC":
            return 0
        signo = nombre[4:5]
        if signo not in "+-" or not signo:
            return 0
        valor = int(nombre[5:7]) * 60 + int(nombre[8:10])
        return -valor if signo == "-" else valor
    assert desfase("(UTC-05:00) Bogotá, Lima, Quito") == -300
    assert desfase("(UTC+05:30) Chennai") == 330
    assert desfase("(UTC) Hora universal coordinada") == 0
    cuerpo = _funcion("DesfaseZona")
    assert "Copy(Nombre, 6, 2)" in cuerpo and "Copy(Nombre, 9, 2)" in cuerpo


@INS01
def test_texto_pagina_de_zona_tambien_al_actualizar_y_reparar():
    skip = _funcion("ShouldSkipPage")
    bloque = skip[skip.index("PageID = PaginaZona.ID"):]
    assert bloque.index("Result := GetArrayLength(ZonaIds) = 0") < bloque.index("ModoReparar")
    iw = _funcion("InitializeWizard")
    assert "CrearPaginaZona(PaginaUnidad.ID)" in iw
    # se aplica en ssPostInstall antes de la rama de Reparar
    csc = _funcion("CurStepChanged")
    assert csc.index("AplicarZona;") < csc.index("RepararEstacion;")
    assert csc.index("ssPostInstall") < csc.index("AplicarZona;")


@INS01
def test_texto_aplica_con_tzutil_s_y_verifica_con_tzutil_g_sin_abortar():
    ap = _funcion("AplicarZona")
    assert "'{sys}\\tzutil.exe'), '/s \"' + ZonaElegida + '\"'" in ap
    assert "ExecAndCaptureOutput(ExpandConstant('{sys}\\tzutil.exe'), '/g'" in ap
    assert "CompareText(SinDstOff(Leida), ZonaElegida) = 0" in ap
    # si falla: mensaje con el procedimiento manual, sin abortar (no hay Abort ni Result)
    assert "CustomMessage('ZonaFallo')" in ap
    assert "Abort" not in ap and "RaiseException" not in ap
    assert "tzutil /s" in _mensaje("es", "ZonaFallo") and "Configuración" in _mensaje("es", "ZonaFallo")
    # la zona queda en el log del Setup
    assert ap.count("Log(") >= 3


@INS01
def test_texto_parametro_zona_silencioso_validado():
    ini = _funcion("InitializeSetup")
    assert "ExpandConstant('{param:ZONA|}')" in ini
    assert ini.index("IndiceZona(ZonaParametro) < 0") < ini.index("CustomMessage('ZonaInvalida')")
    bloque = ini[ini.index("IndiceZona(ZonaParametro) < 0"):ini.index("ZonaElegida := ZonaIds")]
    assert "Result := False" in bloque


# ── INS-02: unidad ───────────────────────────────────────────────────────────

@INS02
def test_texto_unidad_solo_discos_fijos_con_etiqueta_y_espacio():
    assert "external 'GetDriveTypeW@kernel32.dll stdcall'" in CODIGO
    assert "DRIVE_FIXED = 3;" in CODIGO
    assert "GetDriveType(Chr(L) + ':\\') = DRIVE_FIXED" in _funcion("CargarUnidades")
    agregar = _funcion("AgregarUnidad")
    assert "GetVolumeInformation(" in agregar and "GetSpaceOnDisk64(" in agregar
    assert "UnidadesEtiqueta[N]" in agregar


@INS02
def test_texto_preseleccion_distinta_del_sistema_y_si_no_la_del_sistema():
    pre = _funcion("PreseleccionarUnidad")
    assert pre.index("Unidad := ExpandConstant('{sd}')") < pre.index("for I")
    assert "CompareText(UnidadesLetra[I], ExpandConstant('{sd}')) <> 0" in pre


@INS02
def test_texto_espacio_minimo_programa_mas_2_gb_calculado_al_compilar():
    assert "MinimoMB = {#TamProgramaMB} + 2048;" in CODIGO
    assert "#define TamProgramaMB TamKB / 1024 + 1" in ISS
    assert "FileSize(TamDir" in ISS and "FindFirst(TamDir" in ISS
    val = _funcion("ValidarUnidad")
    assert "UnidadesLibreMB[I] < MinimoMB" in val and "'NTFS'" in val
    # validada en la página y otra vez antes de instalar (sin asistente)
    assert "ValidarUnidad(Indice)" in _funcion("NextButtonClick")
    assert "ValidarUnidad(I)" in _funcion("PrepareToInstall")


@INS02
def test_texto_disposicion_programa_y_datos():
    assert "DefaultDirName={code:DirProgramaParam}" in ISS
    assert re.search(r"^DisableDirPage=yes", ISS, re.M)
    assert "{autopf}" not in _seccion("Setup")
    assert "U + '\\Especifika\\Autoclave'" in _funcion("RaizAutoclave")
    assert "RaizAutoclave + '\\programa'" in _funcion("DirPrograma")
    assert "RaizAutoclave + '\\datos'" in _funcion("CarpetaDatos")
    assert "WizardForm.DirEdit.Text := DirPrograma" in _funcion("NextButtonClick")
    assert "CompareText(RemoveBackslashUnlessRoot(WizardDirValue), DirPrograma) <> 0" in _funcion("PrepareToInstall")
    # mismos nombres de subcarpeta que utils/resources
    assert resources.SUBCARPETA_PROGRAMA == "programa" and resources.SUBCARPETA_DATOS == "datos"


@INS02
def test_texto_ya_no_quedan_rutas_a_commonappdata():
    assert "{commonappdata}" not in ISS.split("[Code]")[0].split("[Setup]")[1]
    assert "{commonappdata}" not in CODIGO
    assert "CarpetaDatos + '\\estacion\\estacion.log'" in _funcion("ArchivoLogEstacion")
    assert "[CarpetaDatos]" in _funcion("CurUninstallStepChanged")


@INS02
def test_texto_acl_explicitas_sin_herencia_con_los_tres_sids():
    consts = CODIGO[:CODIGO.index("var")]
    assert ("PermisosPrograma = '*S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F "
            "*S-1-5-32-545:(OI)(CI)RX';") in consts
    assert ("PermisosDatos = '*S-1-5-32-544:(OI)(CI)F *S-1-5-18:(OI)(CI)F "
            "*S-1-5-32-545:(OI)(CI)M';") in consts
    # R1 (V17-s1-01): DACL entera y protegida, sin otras entradas explícitas
    assert "SddlPrograma = 'D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;0x1200a9;;;BU)';" in consts
    assert "SddlDatos = 'D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;0x1301bf;;;BU)';" in consts
    assert "SddlSoloAdmin = 'D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)';" in consts
    assert "AclPrograma = 'S-1-5-32-544:2032127;S-1-5-18:2032127;S-1-5-32-545:1179817';" in consts
    assert "AclDatos = 'S-1-5-32-544:2032127;S-1-5-18:2032127;S-1-5-32-545:1245631';" in consts
    assert "AclSoloAdmin = 'S-1-5-32-544:2032127;S-1-5-18:2032127';" in consts
    prot = _funcion("ProtegerCarpeta")
    assert "/setowner *S-1-5-32-544" in prot
    assert prot.index("'/inheritance:r /grant:r ' + Permisos") < prot.index("AplicarAcl(Ruta, Sddl, Esperado)")
    assert "'/reset /T /Q'" in prot
    prep = _funcion("PrepararCarpetas")
    # X:\Especifika, X:\Especifika\Autoclave y programa: sin escritura para Usuarios
    for llamada in ("ProtegerCarpeta(Especifika, PermisosPrograma, SddlPrograma, AclPrograma, False)",
                    "ProtegerCarpeta(Raiz, PermisosPrograma, SddlPrograma, AclPrograma, False)",
                    "ProtegerCarpeta(Programa, PermisosPrograma, SddlPrograma, AclPrograma, True)",
                    "ProtegerDatos", "PrepararEstacion"):
        assert llamada in prep, llamada
    assert ("ProtegerCarpeta(CarpetaDatos, PermisosDatos, SddlDatos, AclDatos, False)"
            in _funcion("ProtegerDatos"))
    # icacls con verificación del código de salida y sin /C (falla cerrada)
    ic = _funcion("Icacls")
    assert "(Codigo = 0)" in ic and "/C" not in ic


@INS02
def test_texto_aplicar_acl_reemplaza_y_verifica():
    ap = _funcion("AplicarAcl")
    assert "AccessControlSections]::Access" in ap and ".SetAccessControl($s)" in ap
    assert "Set-Acl -LiteralPath" not in ap   # pediría SeSecurityPrivilege
    # verifica: protegida, reglas exactas y dueño Administradores; si no, código <> 0
    assert "AreAccessRulesProtected) { exit 2 }" in ap
    assert "-ne ($e -join ''|'')) { exit 4 }" in ap
    assert "-ne ''S-1-5-32-544'') { exit 3 }" in ap
    assert "and (Codigo = 0)" in ap
    # valores por el entorno, que se limpia
    for v in ("AUTOCLAVE_ACL_RUTA", "AUTOCLAVE_ACL_SDDL", "AUTOCLAVE_ACL_ESPERADO"):
        assert f"SetEnvironmentVariable('{v}', '')" in ap


@INS02
def test_texto_respaldos_y_estacion_con_dacl_verificada():
    pr = _funcion("ProtegerRespaldos")
    assert "AplicarAcl(RaizRespaldos, SddlSoloAdmin, AclSoloAdmin)" in pr
    est = _funcion("PrepararEstacion")
    assert est.count("ProtegerCarpeta(Estacion, PermisosSoloAdmin, SddlSoloAdmin, AclSoloAdmin, True)") == 2
    # R1 (V17-s1-06): en instalación nueva, una estacion\ con algo se aparta (no se borra)
    assert "(not UnidadFija) and not CarpetaVacia(Estacion)" in est
    assert "'\\estacion_anterior_'" in est and "RenameFile(Estacion, Apartada)" in est
    assert "DeleteFile" not in est and "DelTree" not in est and "BorrarArbol" not in est
    assert est.index("RenameFile(Estacion, Apartada)") < est.index("ForceDirectories(Estacion)")
    assert "EstacionNoApartada" in est


@INS02
def test_texto_permisos_antes_de_copiar_y_un_fallo_detiene_el_setup():
    pti = _funcion("PrepareToInstall")
    assert "Result := PrepararCarpetas;\n  if Result <> '' then\n    exit;" in pti
    # tras la limpia, datos\ (recreada) vuelve a sus permisos
    assert pti.index("EjecutarLimpia") < pti.rindex("ProtegerDatos")
    prep = _funcion("PrepararCarpetas")
    assert prep.count("CustomMessage('PermisosFallo')") == 3
    assert "PermisosFallo" in _funcion("ProtegerDatos")
    # enlaces o uniones en el camino detienen el Setup
    assert "EsEnlace(Especifika) or EsEnlace(Raiz) or EsEnlace(Programa) or EsEnlace(Datos)" in prep
    # instalación nueva con programa\ ya ocupada (archivos ajenos): se detiene
    assert "(not UnidadFija) and not CarpetaVacia(Programa)" in prep
    assert "ProgramaExistente" in prep
    # R1 (V17-s1-02): la comprobación va DESPUÉS de proteger programa\
    assert (prep.index("ProtegerCarpeta(Programa, PermisosPrograma")
            < prep.index("(not UnidadFija) and not CarpetaVacia(Programa)"))


@INS02
def test_texto_registro_hklm64_con_las_dos_rutas_sin_romper_las_subclaves():
    reg = _seccion("Registry")
    assert '#define ClaveAutoclave "SOFTWARE\\Especifika\\Autoclave"' in ISS
    assert ('Root: HKLM64; Subkey: "{#ClaveAutoclave}"; ValueType: string; ValueName: "RutaPrograma"; '
            'ValueData: "{app}"; Flags: uninsdeletevalue') in reg
    assert ('Root: HKLM64; Subkey: "{#ClaveAutoclave}"; ValueType: string; ValueName: "RutaDatos"; '
            'ValueData: "{code:DatosParam}"; Flags: uninsdeletevalue') in reg
    # la clave padre nunca se borra entera (tiene Instalacion y Estacion)
    linea_padre = [l for l in reg.splitlines() if '"{#ClaveAutoclave}"' in l]
    assert all("uninsdeletekey" not in l for l in linea_padre)
    assert "uninsdeletekey" in [l for l in reg.splitlines() if "ClaveInstalacion" in l][0]
    # mismos nombres que utils/resources
    assert resources.CLAVE_REGISTRO == "SOFTWARE\\Especifika\\Autoclave"
    assert (resources.VALOR_RUTA_PROGRAMA, resources.VALOR_RUTA_DATOS) == ("RutaPrograma", "RutaDatos")


@INS02
def test_texto_actualizacion_reutiliza_la_unidad_fija():
    ini = _funcion("InitializeSetup")
    assert "RegQueryStringValue(HKLM64, '{#ClaveAutoclave}', 'RutaPrograma', RutaRegistro)" in ini
    assert "UnidadFija := TieneRuta;" in ini
    assert "Unidad := ExtractFileDrive(RutaRegistro);" in ini
    assert "Unidad + '\\Especifika\\Autoclave\\programa'" in ini and "RegistroInvalido" in ini
    crear = _funcion("CrearPaginaUnidad")
    assert "(not UnidadFija) or (CompareText(UnidadesLetra[I], Unidad) = 0)" in crear
    assert "UnidadFijaExplicacion" in crear
    # la página de unidad nunca se salta
    skip = _funcion("ShouldSkipPage")
    assert "(PageID = PaginaUnidad.ID) then\n    Result := False" in skip


@INS02
def test_texto_disposicion_anterior_detiene_el_setup():
    ini = _funcion("InitializeSetup")
    i_bloqueo = ini.index("CustomMessage('DisposicionAnterior')")
    # antes de comparar versiones y de las opciones (nada se toca)
    assert i_bloqueo < ini.index("CompararVersiones(")
    assert "(not TieneRuta) or (Previa = '') or (CompareText(Previa, RutaRegistro) <> 0)" in ini
    assert "'{commonpf64}\\Especifika\\Autoclave'" in ini
    assert "FileExists(Anterior + '\\Autoclave.exe')" in ini
    assert ini.count("CustomMessage('DisposicionAnterior')") == 2
    tramo = ini[i_bloqueo:ini.index("CargarUnidades")]
    assert tramo.count("Result := False") == 2
    previa = _funcion("RutaInstalacionPrevia")
    assert "'Inno Setup: App Path'" in previa and "'InstallLocation'" in previa
    # pide desinstalar; sin migración
    es = _mensaje("es", "DisposicionAnterior").lower()
    assert "desinstale" in es and "no los traslada" in es
    assert "uninstall" in _mensaje("en", "DisposicionAnterior").lower()


@INS02
def test_texto_limpia_y_respaldos_en_la_carpeta_nueva():
    assert "'\\Especifika\\Autoclave\\datos'" in _funcion("RutaDatosValida")
    assert "'\\Autoclave_respaldos'" in _funcion("RaizRespaldos")
    limpia = _funcion("EjecutarLimpia")
    assert "EsEnlace(ExtractFileDir(ExtractFileDir(Datos)))" in limpia


@INS02
def test_replica_ruta_datos_valida():
    """Réplica en Python de RutaDatosValida: solo X:\\Especifika\\Autoclave\\datos."""
    def valida(datos):
        letra = datos[:1].upper()
        if not ("A" <= letra <= "Z") or datos[1:3] != ":\\":
            return False
        return datos[2:].lower() == "\\especifika\\autoclave\\datos"
    assert valida("D:\\Especifika\\Autoclave\\datos")
    assert valida("c:\\especifika\\autoclave\\DATOS")
    assert not valida("D:\\Especifika\\Autoclave")
    assert not valida("D:\\Especifika\\Autoclave\\datos\\..\\programa")
    assert not valida("D:\\X\\Especifika\\Autoclave\\datos")
    assert "Copy(Datos, 3, Length(Datos))" in _funcion("RutaDatosValida")


# ── EST-06 punto 3 ───────────────────────────────────────────────────────────

@EST06
def test_texto_tactiles_repetir_remite_a_la_herramienta_propia_o_al_script():
    for idioma in ("es", "en"):
        texto = _mensaje(idioma, "TactilesRepetir")
        assert "Tablet PC" not in texto
        assert '"%2\\Autoclave.exe" --rol asociar-tactiles' in texto
        assert "%2\\estacion\\06_asociar_tactiles.ps1" in texto
    assert "ExpandConstant('{app}')" in _funcion("CurStepChanged")
    # el paso 06 lo sigue llamando el Setup igual
    assert "EjecutarPaso('06', 'Aplicar', '')" in _funcion("AplicarEstacion")


# ── Mensajes y _comun.ps1 ────────────────────────────────────────────────────

@INS02
def test_texto_mensajes_nuevos_en_los_dos_idiomas():
    for clave in ("UnidadTitulo", "UnidadSubtitulo", "UnidadExplicacion", "UnidadFijaExplicacion",
                  "UnidadElemento", "UnidadSinEtiqueta", "UnidadSinEspacio", "UnidadSinPermisos",
                  "DisposicionAnterior", "RegistroInvalido", "ProgramaExistente", "CarpetaEnlace",
                  "PermisosFallo", "CarpetaNoCreada", "RutaInesperada", "ZonaTitulo",
                  "ZonaSubtitulo", "ZonaExplicacion", "ZonaInvalida", "ZonaFallo"):
        _mensaje("es", clave)
        _mensaje("en", clave)


@INS02
def test_texto_comun_lee_ruta_datos_del_registro_64_bits_con_respaldo():
    assert "[Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry64')" in COMUN
    assert "OpenSubKey('SOFTWARE\\Especifika\\Autoclave')" in COMUN
    assert "GetValue('RutaDatos')" in COMUN
    i_reg = COMUN.index("$script:RutaDatos = Get-RutaDatosRegistro")
    bloque = COMUN[i_reg:COMUN.index("$script:ArchivoLog")]
    assert "Join-Path $script:RutaDatos 'estacion'" in bloque
    assert "Join-Path $env:ProgramData 'Especifika\\Autoclave\\estacion'" in bloque
    assert bloque.index("RutaDatos 'estacion'") < bloque.index("ProgramData")


@INS02
def test_texto_setup_escribe_el_registro_antes_de_los_pasos_de_la_estacion():
    """[Registry] se procesa en la instalación, antes de ssPostInstall, donde
    corren los pasos (EjecutarPaso desde AplicarEstacion/RepararEstacion)."""
    csc = _funcion("CurStepChanged")
    assert "CurStep = ssPostInstall" in csc
    assert "ssInstall" not in csc.replace("ssPostInstall", "")
    assert "AplicarEstacion(" in csc and "RepararEstacion" in csc


@pytest.mark.req("INS-02")
@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="sin powershell.exe")
def test_parser_de_powershell_comun_sin_errores():
    """Solo analiza (Parser::ParseFile): no ejecuta ningún script."""
    archivos = [str(ESTACION / "_comun.ps1"), str(INSTALADOR / "estacion_setup.ps1")]
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
    assert [d["n"] for d in datos] == [0, 0], datos


# ── R1 (revisión de la tanda 17) ─────────────────────────────────────────────

@INS02
def test_texto_unidades_usb_excluidas_y_sin_preseleccion_si_falla_la_consulta():
    consts = CODIGO[:CODIGO.index("var")]
    assert "BusesExcluidos = '|USB|SD|MMC|';" in consts
    cb = _funcion("ConsultarBuses")
    assert "Get-Partition" in cb and "Get-Disk -Number $_.DiskNumber).BusType" in cb
    assert "ConsultaBusFallida := True;" in cb
    assert cb.index("ConsultaBusFallida := True;") < cb.index("ConsultaBusFallida := False;")
    cu = _funcion("CargarUnidades")
    assert cu.index("ConsultarBuses;") < cu.index("AgregarUnidad(")
    assert "Pos(Chr(L), LetrasExcluidas) > 0" in cu
    pre = _funcion("PreseleccionarUnidad")
    assert pre.index("Unidad := ExpandConstant('{sd}')") < pre.index("if ConsultaBusFallida then\n    exit;")


@INS02
def test_texto_reversion_fallida_conserva_rutas_y_pasos():
    rev = _funcion("RevertirEstacion")
    assert "ReversionFallida := Fallas <> '';" in rev
    # la clave de pasos solo se borra si todo revirtió
    bloque = rev[rev.index("if not ReversionFallida then"):]
    assert bloque.index("RegDeleteKeyIncludingSubkeys(HKLM64, '{#ClaveEstacion}')") < bloque.index("end;")
    assert "CarpetaDatos + '\\estacion'" in rev
    cus = _funcion("CurUninstallStepChanged")
    i_un = cus.index("CurUninstallStep = usUninstall")
    assert cus.index("'RutaDatos', RutaDatosDesinstalada") < cus.index("RevertirEstacion;")
    assert i_un < cus.index("RevertirEstacion;")
    post = cus[cus.index("CurUninstallStep = usPostUninstall"):]
    assert "RegWriteStringValue(HKLM64, '{#ClaveAutoclave}', 'RutaDatos', RutaDatosDesinstalada)" in post
    assert "RegWriteStringValue(HKLM64, '{#ClaveAutoclave}', 'RutaPrograma', RutaProgramaDesinstalada)" in post
    for idioma in ("es", "en"):
        assert "%3" in _mensaje(idioma, "ReversionFallo")
        _mensaje(idioma, "EstacionNoApartada")


@INS02
def test_texto_comun_dacl_verificada_y_ruta_por_entorno():
    prot = COMUN[COMUN.index("function Protect-DirEstacion"):COMUN.index("function Initialize-Estacion")]
    assert "SetSecurityDescriptorSddlForm('D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)'" in prot
    assert "AccessControlSections]::Access" in prot and ".SetAccessControl($sd)" in prot
    assert prot.index(".SetAccessControl($sd)") < prot.index("Assert-DirEstacionProtegida")
    assert "/C" not in prot
    asegurar = prot[prot.index("function Assert-DirEstacionProtegida"):]
    assert "AreAccessRulesProtected" in asegurar and "'S-1-5-32-544'" in asegurar and "throw" in asegurar
    assert "'S-1-5-18:2032127:0:3:0:False'" in asegurar
    # AUTOCLAVE_RUTA_DATOS > registro > ProgramData
    i_env = COMUN.index("Test-RutaDatos $env:AUTOCLAVE_RUTA_DATOS")
    assert i_env < COMUN.index("$script:RutaDatos = Get-RutaDatosRegistro")
    assert "AUTOCLAVE_RUTA_DATOS" in (INSTALADOR / "LEEME.md").read_text(encoding="utf-8")


def _comando_pascal(funcion: str) -> str:
    """Texto que el .iss pasa a powershell.exe tras -Command (literales Pascal
    concatenados, '' -> ')."""
    cuerpo = _funcion(funcion)
    tramo = cuerpo[cuerpo.index("'-NoProfile"):cuerpo.index("'', SW_HIDE")]
    texto = "".join(p.replace("''", "'") for p in re.findall(r"'((?:[^']|'')*)'", tramo))
    return texto[texto.index('-Command "') + len('-Command "'):texto.rindex('"')]


@INS02
@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="sin powershell.exe")
def test_ejecuta_aplicar_acl_quita_entradas_ajenas_y_verifica(tmp_path):
    """El mismo comando de AplicarAcl sobre una carpeta temporal con Todos:F
    explícito: queda solo la DACL esperada (sin elevar, el dueño no es
    Administradores: código 3; elevado: 0). Nunca toca carpetas reales."""
    import os
    carpeta = tmp_path / "acl"
    carpeta.mkdir()
    subprocess.run(["icacls", str(carpeta), "/grant", "*S-1-1-0:(OI)(CI)F", "/Q"],
                   capture_output=True, check=True)
    entorno = dict(os.environ, AUTOCLAVE_ACL_RUTA=str(carpeta),
                   AUTOCLAVE_ACL_SDDL="D:P(A;OICI;FA;;;BA)(A;OICI;FA;;;SY)(A;OICI;0x1200a9;;;BU)",
                   AUTOCLAVE_ACL_ESPERADO="S-1-5-32-544:2032127;S-1-5-18:2032127;S-1-5-32-545:1179817")
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-Command", _comando_pascal("AplicarAcl")],
                           capture_output=True, text=True, env=entorno, timeout=120)
        assert r.returncode in (0, 3), r.stdout + r.stderr
        assert ("reglas=S-1-5-18:2032127:0:3:0:False|S-1-5-32-544:2032127:0:3:0:False|"
                "S-1-5-32-545:1179817:0:3:0:False") in r.stdout.replace("\n", "")
        assert "S-1-1-0" not in r.stdout
        # con lo esperado distinto, falla (código 4)
        entorno["AUTOCLAVE_ACL_ESPERADO"] = "S-1-5-32-544:2032127;S-1-5-18:2032127"
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                            "-Command", _comando_pascal("AplicarAcl")],
                           capture_output=True, text=True, env=entorno, timeout=120)
        assert r.returncode == 4, r.stdout
    finally:
        subprocess.run(["icacls", str(carpeta), "/reset", "/T", "/Q"], capture_output=True)


@INS02
@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="sin powershell.exe")
def test_ejecuta_consulta_de_buses_solo_lectura():
    """El mismo comando de ConsultarBuses (solo lee particiones y discos)."""
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-Command", _comando_pascal("ConsultarBuses")],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        pytest.skip("Get-Partition/Get-Disk no disponibles aquí (el Setup no preselecciona otra unidad)")
    lineas = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    assert lineas and all(re.fullmatch(r"L=[A-Z]:\w*", l) for l in lineas), lineas
