"""D9-11 (tanda 9, E9): Setup con "Configurar este PC como estación del autoclave".

Pruebas ESTÁTICAS (no se ejecuta ningún .ps1 ni el Setup, por regla de la
tanda): el .iss declara las casillas, la página de cuenta, los scripts que
instala y la reversión; los scripts de tools/estacion aceptan correr sin
interacción; la lista blanca de valores de registro de _comun.ps1 cubre todo lo
que escriben los pasos (si no, Set-RegValor lanzaría y el paso fallaría)."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ESTACION = RAIZ / "tools" / "estacion"
INSTALADOR = RAIZ / "tools" / "instalador"
ISS = (INSTALADOR / "autoclave.iss").read_text(encoding="utf-8-sig")


def _ps(nombre):
    return (ESTACION / nombre).read_text(encoding="ascii")


def _gestionados() -> set[str]:
    bloque = re.search(r"\$script:ValoresGestionados = @\((.*?)\n\)", _ps("_comun.ps1"), re.S).group(1)
    return set(re.findall(r"'([^']+\|[^']+)'", bloque))


def _valores_escritos(texto: str) -> set[str]:
    """(Ruta|Nombre) de cada Set-RegValor, resolviendo $variables simples."""
    variables = {}
    for var, valor in re.findall(r"^\$(\w+)\s*=\s*['\"]([^'\"]+)['\"]", texto, re.M):
        variables[var] = re.sub(r"\$(\w+)", lambda m: variables.get(m.group(1), m.group(0)), valor)
    texto = texto.replace("`\r\n", " ").replace("`\n", " ")
    pares = set()
    for linea in texto.splitlines():
        if not linea.lstrip().startswith("Set-RegValor"):
            continue
        ruta = re.search(r"-Ruta\s+('([^']+)'|\$(\w+))", linea)
        nombre = re.search(r"-Nombre\s+'([^']+)'", linea).group(1)
        r = ruta.group(2) or variables[ruta.group(3)]
        pares.add(f"{r}|{nombre}")
    return pares


def test_lista_blanca_cubre_todo_lo_que_escriben_los_pasos():
    escritos = set()
    for paso in ("01_cuenta_autologon.ps1", "02_arranque_silencioso.ps1",
                 "04_notificaciones_actualizaciones_gestos.ps1", "05_plan_energia.ps1"):
        escritos |= _valores_escritos(_ps(paso))
    assert len(escritos) == 25
    assert escritos == _gestionados()


def test_restaurar_solo_valores_gestionados_y_log_sin_contrasena():
    comun = _ps("_comun.ps1")
    restaurar = comun[comun.index("function Restore-RegValores"):]
    assert "ValoresGestionados -notcontains $clave" in restaurar
    assert "'DefaultPassword'" in comun and "Format-ValorLog" in comun
    # ningún Write-Log muestra $Valor/$actual/$orig.Valor sin enmascarar
    for linea in comun.splitlines():
        if "Write-Log" in linea:
            assert not re.search(r"'\$(Valor|actual)'|'\$\(\$orig\.Valor\)'", linea), linea


def test_carpeta_estacion_protegida():
    comun = _ps("_comun.ps1")
    assert "/inheritance:r" in comun and "*S-1-5-32-544" in comun and "*S-1-5-18" in comun
    assert "/setowner" in comun


def test_paso_01_sin_interaccion():
    s = _ps("01_cuenta_autologon.ps1")
    assert "[switch]$ContrasenaDesdeEntorno" in s and "[switch]$NoCrearCuenta" in s
    assert "[string]$Dominio" in s
    # la contraseña sale del entorno y se borra de él; Read-Host solo si no llegó
    assert "Remove-Item Env:AUTOCLAVE_CLAVE_AUTOLOGON" in s
    assert s.index("ContrasenaDesdeEntorno) {") < s.index("Read-Host")
    # AutoAdminLogon se activa al final
    assert s.rindex("'AutoAdminLogon'") > s.rindex("'DefaultPassword'")


def test_los_pasos_no_piden_nada():
    for nombre in ("02_arranque_silencioso.ps1", "04_notificaciones_actualizaciones_gestos.ps1",
                   "05_plan_energia.ps1", "01_revertir_cuenta_autologon.ps1",
                   "02_revertir_arranque_silencioso.ps1",
                   "04_revertir_notificaciones_actualizaciones_gestos.ps1",
                   "05_revertir_plan_energia.ps1"):
        s = _ps(nombre)
        assert "Read-Host" not in s and "ConfirmImpact" not in s, nombre


def test_puente_del_setup():
    s = (INSTALADOR / "estacion_setup.ps1").read_text(encoding="ascii")
    assert "$ErrorActionPreference = 'Stop'" in s
    assert "-NoCrearCuenta -ContrasenaDesdeEntorno" in s
    assert "EliminarCuenta" not in s.split("#>")[1]
    assert "exit 1" in s and "exit 0" in s


def test_iss_casillas():
    tareas = dict(re.findall(r'^Name: "(\w+)"; Description: "\{cm:\w+\}"(.*)$', ISS, re.M))
    assert set(tareas) == {"autoarranque", "estacion", "sinlogo"}
    assert "unchecked" not in tareas["estacion"]          # marcada por defecto
    assert "unchecked" in tareas["sinlogo"]                # desmarcada por defecto


def test_iss_pasos_y_reversion():
    assert re.search(r"EjecutarPaso\('01', 'Aplicar'", ISS)
    assert re.search(r"EjecutarPaso\('04', 'Aplicar'", ISS)
    assert re.search(r"EjecutarPaso\('05', 'Aplicar'", ISS)
    assert re.search(r"EjecutarPaso\('02', 'Aplicar'", ISS)
    # el 02 solo con su casilla
    bloque_sinlogo = ISS[ISS.index("if WizardIsTaskSelected('sinlogo') then"):]
    assert "EjecutarPaso('02'" in bloque_sinlogo[:300]
    assert ISS.count("EjecutarPaso('02', 'Aplicar'") == 1
    # desinstalación: orden inverso y solo lo marcado
    orden = [ISS.index(f"EjecutarReversion('{p}'") for p in ("05", "04", "02", "01")]
    assert orden == sorted(orden)
    assert "usUninstall" in ISS and "RegValueExists(HKLM64" in ISS


def test_iss_pagina_de_cuenta_y_contrasena_por_entorno():
    assert "CreateInputQueryPage(wpSelectTasks" in ISS
    assert "PaginaCuenta.Add(CustomMessage('CuentaClave'), True)" in ISS        # oculta
    assert "SetEnvironmentVariable(VarClave, PaginaCuenta.Values[1])" in ISS
    assert "SetEnvironmentVariable(VarClave, '')" in ISS
    assert "Values[1] + " not in ISS                                            # nunca en la línea de comandos


def test_iss_instala_los_scripts_y_da_permisos():
    for nombre in ("_comun.ps1", "01_cuenta_autologon.ps1", "01_revertir_cuenta_autologon.ps1",
                   "02_arranque_silencioso.ps1", "02_revertir_arranque_silencioso.ps1",
                   "04_notificaciones_actualizaciones_gestos.ps1",
                   "04_revertir_notificaciones_actualizaciones_gestos.ps1",
                   "05_plan_energia.ps1", "05_revertir_plan_energia.ps1"):
        assert f'Source: "..\\estacion\\{nombre}"; DestDir: "{{app}}\\estacion"' in ISS, nombre
        assert (ESTACION / nombre).is_file()
    assert 'Source: "estacion_setup.ps1"; DestDir: "{app}\\estacion"' in ISS
    assert 'Name: "{commonappdata}\\Especifika\\Autoclave"; Permissions: users-modify' in ISS
    assert "AppId={{81C9DAB1-5CF8-4AD2-A7BE-15053E6ED43F}" in ISS              # no cambia nunca


def test_mensajes_en_los_dos_idiomas():
    es = set(re.findall(r"^es\.(\w+)=", ISS, re.M))
    en = set(re.findall(r"^en\.(\w+)=", ISS, re.M))
    assert es == en
    usados = set(re.findall(r"CustomMessage\('(\w+)'\)", ISS)) | set(re.findall(r"\{cm:(\w+)\}", ISS))
    usados |= {"Paso01", "Paso02", "Paso04", "Paso05"}
    assert usados <= es
