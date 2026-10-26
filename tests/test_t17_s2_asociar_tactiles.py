"""EST-06 (tanda 17): asociación de pantallas táctiles sin MultiDigitizer.exe.

- armado PURO de los valores Digimon con datos simulados (normalización,
  mayúsculas como las deja Windows, rutas mal formadas, un digitalizador por
  monitor, sin duplicados, prefijo);
- respaldo compatible con 06_revertir_asociar_tactiles.ps1 (mismo formato,
  no se pisa);
- recorrido de la herramienta con dobles (sin registro, sin ventanas): sin
  administrador no escribe; respaldo antes de escribir; Esc no escribe;
- rol `--rol asociar-tactiles` del exe único;
- 06_asociar_tactiles.ps1 ya no lanza `throw` sin MultiDigitizer.

Nunca se escribe en el registro ni se abren ventanas (escritor inyectado)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoclave import exe_unico
from autoclave.estacion import asociar_tactiles as at
from autoclave.estacion import digimon

pytestmark = pytest.mark.req("EST-06")

RAIZ = Path(__file__).resolve().parents[1]
GUID_HID = "{4d1e55b2-f16f-11cf-88cb-001111000030}"
GUID_MON = "{e6f07b5f-ee97-4a90-b076-33f57bf4eaa7}"
HID_A = "\\\\?\\HID#VID_222A&PID_0001&Col01#7&1d1dfc1&0&0000#" + GUID_HID
HID_B = "\\\\?\\HID#VID_222A&PID_0001&Col01#7&2b2bbb2&0&0000#" + GUID_HID
MON_1 = "\\\\?\\DISPLAY#AUO22EC#4&2a5d4cd&0&UID265988#" + GUID_MON
MON_2 = "\\\\?\\DISPLAY#AUO22EC#4&2a5d4cd&0&UID265989#" + GUID_MON


# ── armado puro ─────────────────────────────────────────────────────────────

def test_un_valor_por_digitalizador_con_prefijo_y_dato_del_monitor():
    a = digimon.armar_valores([(HID_A, MON_1), (HID_B, MON_2)])
    assert a.rechazos == []
    assert a.valores == {"20-" + HID_A: MON_1, "20-" + HID_B: MON_2}
    # el nombre del valor empieza con \\?\HID# y el dato con \\?\DISPLAY#
    for nombre, dato in a.valores.items():
        assert nombre.startswith("20-\\\\?\\HID#") and dato.startswith("\\\\?\\DISPLAY#")


def test_normaliza_prefijo_nt_espacios_y_nulos_sin_cambiar_mayusculas():
    hid_nt = "\\??\\" + HID_A[4:]                       # \??\HID#... (prefijo NT)
    mon_minus = MON_1.lower() + "\x00 "
    a = digimon.armar_valores([(" " + hid_nt + "\x00", mon_minus)])
    assert a.rechazos == []
    [(nombre, dato)] = a.valores.items()
    assert nombre == "20-" + HID_A                       # tal cual (mayúsculas de Windows)
    assert dato == MON_1.lower()                         # tal cual (minúsculas)


@pytest.mark.parametrize("hid, mon", [
    ("HID#VID_1#2#" + GUID_HID, MON_1),                  # sin \\?\
    ("\\\\?\\USB#VID_1#2#" + GUID_HID, MON_1),            # no es HID
    ("\\\\?\\HID#VID_1#2#{00000000-0000-0000-0000-000000000000}", MON_1),   # otro GUID
    ("\\\\?\\HID##2#" + GUID_HID, MON_1),                 # segmento vacío
    ("\\\\?\\HID#VID 1#2#" + GUID_HID, MON_1),            # espacio
    (HID_A, "\\\\.\\DISPLAY1"),                           # nombre de adaptador, no interfaz
    (HID_A, "\\\\?\\DISPLAY#AUO#4&2#" + GUID_HID),        # GUID de HID en el monitor
    (HID_A, ""),
    (None, MON_1),
])
def test_rechaza_rutas_mal_formadas(hid, mon):
    a = digimon.armar_valores([(hid, mon)])
    assert a.valores == {}
    assert len(a.rechazos) == 1 and "mal formada" in a.rechazos[0]


def test_par_mal_formado():
    a = digimon.armar_valores([("solo-uno",), 3])
    assert a.valores == {} and len(a.rechazos) == 2


def test_un_digitalizador_por_monitor_y_sin_duplicados():
    a = digimon.armar_valores([
        (HID_A, MON_1),
        (HID_A.lower(), MON_2),     # mismo digitalizador (otra caja): rechazado
        (HID_B, MON_1.upper()),     # mismo monitor: rechazado
        (HID_B, MON_2),
        (HID_B, MON_2),             # duplicado exacto: rechazado
    ])
    assert a.valores == {"20-" + HID_A: MON_1, "20-" + HID_B: MON_2}
    assert len(a.rechazos) == 3


def test_prefijo_siempre_20_salvo_forma_completa_del_mismo_tactil():
    # V17-s2-05: sin valores, o con otros prefijos de origen dudoso → "20-"
    assert digimon.elegir_prefijo({}, [HID_A]) == ("20-", None)
    # todos con la forma completa, mismo prefijo y uno es el táctil tocado → se usa ese
    existentes = {"30-" + HID_A: (MON_2, "String")}
    prefijo, aviso = digimon.elegir_prefijo(existentes, [HID_A.lower()])
    assert prefijo == "30-" and aviso
    # mismo caso pero ningún HID existente fue tocado en esta pasada → "20-" con aviso
    prefijo, aviso = digimon.elegir_prefijo(existentes, [HID_B])
    assert prefijo == "20-" and "30-" in aviso
    # un valor existente mal formado (p. ej. de otro dispositivo) → "20-" con aviso
    raro = {"30-" + HID_A: (MON_2, "String"), "30-\\\\?\\USB#x#y#z": (MON_1, "String")}
    prefijo, aviso = digimon.elegir_prefijo(raro, [HID_A])
    assert prefijo == "20-" and aviso
    # dato que no es una ruta de monitor → "20-"
    assert digimon.elegir_prefijo({"30-" + HID_A: (5, "DWord")}, [HID_A])[0] == "20-"
    # prefijos distintos → "20-"
    mezcla = {"30-" + HID_A: (MON_1, "String"), "40-" + HID_B: (MON_2, "String")}
    assert digimon.elegir_prefijo(mezcla, [HID_A, HID_B])[0] == "20-"
    # ya con "20-" no hay aviso
    assert digimon.elegir_prefijo({"20-" + HID_A: (MON_1, "String")}, [HID_A]) == ("20-", None)
    assert digimon.armar_valores([(HID_A, MON_1)], "30-").valores == {"30-" + HID_A: MON_1}
    with pytest.raises(ValueError):
        digimon.armar_valores([(HID_A, MON_1)], "x-")


def test_conflictos_solo_avisan():
    existentes = {"20-" + HID_B: (MON_1, "String"), "20-" + HID_A: (MON_2, "String")}
    avisos = digimon.conflictos({"20-" + HID_A: MON_1}, existentes)
    assert len(avisos) == 1 and HID_B in avisos[0]


# ── respaldo compatible con el inverso ──────────────────────────────────────

class _Escritor:
    def __init__(self, existentes=None, existe=True, falla_escribir=False, eventos=None):
        self.valores = dict(existentes or {})
        self._existe = existe
        self.falla_escribir = falla_escribir
        self.escritos = []
        self.eventos = eventos if eventos is not None else []

    def existe(self):
        return self._existe

    def leer(self):
        self.eventos.append("leer")
        return dict(self.valores)

    def escribir(self, nombre, dato):
        self.eventos.append("escribir")
        if self.falla_escribir:
            raise PermissionError("acceso denegado")
        self.escritos.append((nombre, dato))
        self.valores[nombre] = (dato, "String")


def test_respaldo_con_el_formato_del_script(tmp_path):
    ruta = tmp_path / "estacion" / digimon.NOMBRE_RESPALDO
    esc = _Escritor({"20-" + HID_A: (MON_1, "String"), "Num": (5, "DWord"),
                     "Bin": (b"\x01\x02", "Binary"), "Multi": (["a", "b"], "MultiString")}, existe=True)
    assert digimon.asegurar_respaldo(str(ruta), esc) is True
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos == {
        "DigimonAntes": {"20-" + HID_A: {"Valor": MON_1, "Tipo": "String"},
                         "Num": {"Valor": 5, "Tipo": "DWord"},
                         "Bin": {"Valor": [1, 2], "Tipo": "Binary"},
                         "Multi": {"Valor": ["a", "b"], "Tipo": "MultiString"}},
        "DigimonExistia": True,
    }


def test_respaldo_existente_no_se_pisa_y_admite_bom(tmp_path):
    ruta = tmp_path / digimon.NOMBRE_RESPALDO
    previo = {"DigimonAntes": {}, "DigimonExistia": False}
    ruta.write_bytes(b"\xef\xbb\xbf" + json.dumps(previo).encode("utf-8"))   # Set-Content -Encoding UTF8
    esc = _Escritor({"20-" + HID_A: (MON_1, "String")})
    assert digimon.asegurar_respaldo(str(ruta), esc) is False
    assert json.loads(ruta.read_text(encoding="utf-8-sig")) == previo


def test_respaldo_conserva_otras_claves_y_clave_inexistente(tmp_path):
    ruta = tmp_path / digimon.NOMBRE_RESPALDO
    ruta.write_text(json.dumps({"Otra": 1}), encoding="utf-8")
    assert digimon.asegurar_respaldo(str(ruta), _Escritor({}, existe=False)) is True
    assert json.loads(ruta.read_text(encoding="utf-8")) == {"Otra": 1, "DigimonAntes": {},
                                                             "DigimonExistia": False}


# ── recorrido de la herramienta con dobles ──────────────────────────────────

def _monitores():
    return [SimpleNamespace(rect=(0, 0, 1920, 1080), interfaz=MON_1),
            SimpleNamespace(rect=(1920, 0, 1920, 1080), interfaz=MON_2)]


def _ejecutar(tmp_path, toques, escritor=None, es_admin=True, **kw):
    lineas = []
    escritor = escritor or _Escritor({})
    pedidos = []

    def pedir(monitor, excluidos, tope_s):
        pedidos.append((monitor.interfaz, set(excluidos), tope_s))
        t = toques.pop(0)
        if isinstance(t, Exception):
            raise t
        return t

    codigo = at.ejecutar(es_admin=lambda: es_admin, listar_monitores=_monitores, pedir_toque=pedir,
                         escritor=escritor, ruta_respaldo=str(tmp_path / digimon.NOMBRE_RESPALDO),
                         log=lambda m, n="INFO": lineas.append((n, m)), **kw)
    return SimpleNamespace(codigo=codigo, escritor=escritor, lineas=lineas, pedidos=pedidos)


def test_recorrido_completo_respalda_antes_y_escribe(tmp_path):
    eventos = []
    esc = _Escritor({}, existe=False, eventos=eventos)
    fin = []
    r = _ejecutar(tmp_path, [HID_A, HID_B], escritor=esc, avisar_fin=lambda: fin.append(1))
    assert r.codigo == at.COMPLETO
    assert esc.escritos == [("20-" + HID_A, MON_1), ("20-" + HID_B, MON_2)]
    assert (tmp_path / digimon.NOMBRE_RESPALDO).is_file()
    assert eventos.index("leer") < eventos.index("escribir")       # respaldo (lee) antes de escribir
    # el digitalizador del primer monitor no cuenta para el segundo
    assert r.pedidos[1][1] == {HID_A.lower()}
    assert r.pedidos[0][2] == at.TOPE_POR_MONITOR_S == 120.0
    assert fin == [1]
    assert any("Reinicie el equipo" in m for _, m in r.lineas)


def test_sin_administrador_no_escribe_ni_respalda(tmp_path):
    r = _ejecutar(tmp_path, [HID_A, HID_B], es_admin=False)
    assert r.codigo == at.SIN_ADMIN != 0
    assert r.escritor.escritos == [] and r.pedidos == []
    assert not (tmp_path / digimon.NOMBRE_RESPALDO).exists()
    assert any(n == "ERROR" and "administrador" in m for n, m in r.lineas)


def test_esc_cancela_sin_escribir(tmp_path):
    r = _ejecutar(tmp_path, [HID_A, at.Cancelado()])
    assert r.codigo == at.INCOMPLETO
    assert r.escritor.escritos == []


def test_pantalla_sin_toque_queda_incompleta(tmp_path):
    r = _ejecutar(tmp_path, [None, HID_B])
    assert r.codigo == at.INCOMPLETO
    assert r.escritor.escritos == [("20-" + HID_B, MON_2)]


def test_toque_mal_formado_se_descarta(tmp_path):
    r = _ejecutar(tmp_path, ["\\\\?\\USB#raro#1#x", HID_B])
    assert r.codigo == at.INCOMPLETO
    assert r.escritor.escritos == [("20-" + HID_B, MON_2)]
    assert any(n == "WARN" and "Descartado" in m for n, m in r.lineas)


def test_sin_respaldo_posible_no_toca_el_registro(tmp_path):
    (tmp_path / digimon.NOMBRE_RESPALDO).write_text("[1, 2]", encoding="utf-8")   # formato inesperado
    r = _ejecutar(tmp_path, [HID_A, HID_B])
    assert r.codigo == at.ERROR
    assert r.escritor.escritos == [] and r.pedidos == []


def test_error_al_escribir_da_error(tmp_path):
    r = _ejecutar(tmp_path, [HID_A, HID_B], escritor=_Escritor({}, falla_escribir=True))
    assert r.codigo == at.ERROR


def test_usa_el_prefijo_que_ya_hay_solo_para_el_mismo_tactil(tmp_path):
    esc = _Escritor({"30-" + HID_A: (MON_2, "String")})
    r = _ejecutar(tmp_path, [HID_A, HID_B], escritor=esc)
    assert r.escritor.escritos[0] == ("30-" + HID_A, MON_1)
    assert any(n == "WARN" and "prefijo 30-" in m for n, m in r.lineas)


def test_otro_prefijo_de_otro_dispositivo_solo_se_avisa(tmp_path):
    otro = "\\\\?\\HID#VID_9999&PID_0001&Col02#1&1&0&0000#" + GUID_HID
    esc = _Escritor({"10-" + otro: (MON_2, "String")})
    r = _ejecutar(tmp_path, [HID_A, HID_B], escritor=esc)
    assert [n for n, _ in r.escritor.escritos] == ["20-" + HID_A, "20-" + HID_B]
    assert any(n == "WARN" and "10-" in m for n, m in r.lineas)


class _WinregDoble:
    """winreg falso: registra cada apertura (clave, ruta, permisos) y cada
    SetValueEx. Nunca toca el registro real."""
    HKEY_LOCAL_MACHINE = "HKLM"
    KEY_READ, KEY_SET_VALUE, KEY_QUERY_VALUE, KEY_WOW64_64KEY = 0x20019, 0x2, 0x1, 0x100
    REG_SZ, REG_DWORD = 1, 4

    def __init__(self, valores=None):
        self.valores = list(valores or [])
        self.aperturas, self.escritos = [], []

    class _K:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def OpenKey(self, raiz, ruta, reservado, permisos):
        self.aperturas.append((raiz, ruta, permisos))
        return self._K()

    def CreateKeyEx(self, raiz, ruta, reservado, permisos):
        self.aperturas.append((raiz, ruta, permisos))
        return self._K()

    def EnumValue(self, k, i):
        if i >= len(self.valores):
            raise OSError("no hay más")
        return self.valores[i]

    def SetValueEx(self, k, nombre, reservado, tipo, dato):
        self.escritos.append((nombre, tipo, dato))


def test_escritor_real_usa_la_vista_de_64_bits_y_solo_reg_sz():
    esc = digimon.EscritorRegistro.__new__(digimon.EscritorRegistro)
    esc._w = falso = _WinregDoble([("20-" + HID_A, MON_1, 1), ("N", 7, 4)])
    assert esc.existe() is True
    assert esc.leer() == {"20-" + HID_A: (MON_1, "String"), "N": (7, "DWord")}
    esc.escribir("20-" + HID_B, MON_2)
    assert falso.escritos == [("20-" + HID_B, falso.REG_SZ, MON_2)]
    assert all(r == "HKLM" and ruta == "SOFTWARE\\Microsoft\\Wisp\\Pen\\Digimon"
               and permisos & falso.KEY_WOW64_64KEY for r, ruta, permisos in falso.aperturas)
    assert not hasattr(digimon.EscritorRegistro, "borrar")   # nunca borra


def test_main_fuera_de_windows_o_sin_admin_no_lanza(monkeypatch, tmp_path):
    monkeypatch.setattr(at, "_es_admin_win32", lambda: False)
    codigo = at.main(["--respaldo", str(tmp_path / "r.json"), "--log", str(tmp_path / "e.log")])
    assert codigo in (at.SIN_ADMIN, at.ERROR)
    assert not (tmp_path / "r.json").exists()
    assert (tmp_path / "e.log").is_file()


# ── rol del exe único ───────────────────────────────────────────────────────

def test_rol_asociar_tactiles_sigue_sin_log_de_archivo(monkeypatch):
    """V17-s2-04: si _log_a_archivo falla, el rol sigue."""
    def falla(nombre):
        raise PermissionError("sin permiso en data")

    monkeypatch.setattr(exe_unico, "_log_a_archivo", falla)
    monkeypatch.setattr(at, "main", lambda argv: 0)
    assert exe_unico.main(["--rol", "asociar-tactiles"]) == 0


def test_rol_asociar_tactiles_pasa_sus_opciones(monkeypatch):
    llamadas = []
    monkeypatch.setattr(exe_unico, "_log_a_archivo", lambda nombre: llamadas.append(nombre))
    monkeypatch.setattr(at, "main", lambda argv: llamadas.append(list(argv)) or 3)
    codigo = exe_unico.main(["--rol", "asociar-tactiles", "--respaldo", "C:\\d\\r.json", "--log", "C:\\d\\e.log"])
    assert codigo == 3
    assert llamadas == ["asociar_tactiles.log", ["--respaldo", "C:\\d\\r.json", "--log", "C:\\d\\e.log"]]


def test_otros_roles_siguen_rechazando_opciones_desconocidas():
    with pytest.raises(SystemExit):
        exe_unico._parse_args(["--rol", "ui", "--respaldo", "x"])
    assert exe_unico._parse_args([]).sobrantes == []


def test_asociar_tactiles_no_importa_pyside():
    import subprocess
    import sys
    import os
    import autoclave
    entorno = {**os.environ, "PYTHONPATH": str(Path(autoclave.__file__).resolve().parents[1])}
    codigo = ("import sys; import autoclave.estacion.asociar_tactiles, autoclave.estacion.digimon; "
              "print(any(m.split('.')[0] == 'PySide6' for m in sys.modules))")
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=60, env=entorno)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "False"


# ── 06_asociar_tactiles.ps1 ─────────────────────────────────────────────────

def _ps06():
    return (RAIZ / "tools/estacion/06_asociar_tactiles.ps1").read_text(encoding="ascii")


def test_06_sin_multidigitizer_usa_la_herramienta_propia_y_no_lanza():
    s = _ps06()
    assert "throw" not in s                                   # EST-06.4: nunca corta la estación
    assert "'System32\\MultiDigitizer.exe'" in s and "'Sysnative\\MultiDigitizer.exe'" in s
    assert "Join-Path (Split-Path -Parent $PSScriptRoot) 'Autoclave.exe'" in s
    assert "--rol asociar-tactiles --respaldo" in s
    assert "Get-RutaRespaldo $Paso" in s
    # respaldo antes de abrir cualquiera de las dos herramientas
    assert s.index("Save-Respaldo") < s.index("Start-Process")
    # el fallo de la herramienta queda en el log
    assert "No se pudo ejecutar la herramienta de asociacion" in s
    assert "Tampoco se encuentra la herramienta propia" in s
    assert "exit 1" not in s


def test_06_pide_reinicio_solo_si_la_herramienta_escribio():
    """V17-s2-06: código 0, o 3 con más valores que antes de abrirla."""
    s = _ps06()
    assert s.index("$cuentaAntes = (Get-ValoresDigimon).Count") < s.index("Start-Process")
    assert "$codigoPropio = $codigo" in s
    assert "$masValores = ($null -ne $cuentaAntes) -and ($despues.Count -gt $cuentaAntes)" in s
    assert "$escribio = ($codigoPropio -eq 0) -or (($codigoPropio -eq 3) -and $masValores)" in s
    bloque = s[s.index("$escribio ="):]
    assert bloque.index("if ($propia -and $escribio)") < bloque.index("Reinicie el equipo")
    assert s.count("Reinicie el equipo") == 1
