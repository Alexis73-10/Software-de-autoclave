"""EST-07 (tanda 17, DECISIÓN SIN CONFIRMAR): cubierta de arranque.

- el lanzador abre la cubierta ANTES de importar PySide/la UI QML y antes de
  lanzar el backend o las pantallas (espía de __import__ y orden de llamadas);
- un fallo de la cubierta no impide el arranque;
- la cubierta se cierra con el primer cuadro de las pantallas, por gracia tras
  la primera, o por el tope de 180 s (reloj inyectado, sin dormir), y destruye
  siempre sus ventanas aunque falle a medias;
- la señal de primer cuadro de app.py avisa una sola vez;
- la tarea de arranque pasa a PT0S.

Sin ventanas reales: el núcleo Win32 se reemplaza por dobles."""

import builtins
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoclave import exe_unico
from autoclave.estacion import cubierta_arranque, primer_cuadro
from autoclave.estacion.cubierta_arranque import Cubierta, motivo_cierre

pytestmark = pytest.mark.req("EST-07")

RAIZ = Path(__file__).resolve().parents[1]


# ── decisión de cierre (pura) ───────────────────────────────────────────────

def test_motivo_cierre_tope_gracia_pantallas_y_pedido():
    assert motivo_cierre(10, 0, None, {1, 2}) is None
    assert motivo_cierre(179.9, 0, None, {1, 2}) is None
    assert motivo_cierre(180.0, 0, None, {1, 2}) == "tope"
    assert motivo_cierre(5, 0, 3, set()) == "pantallas"
    assert motivo_cierre(17.9, 0, 3, {2}) is None
    assert motivo_cierre(18.0, 0, 3, {2}) == "gracia"
    assert motivo_cierre(1, 0, None, {1}, solicitado=True) == "solicitado"


def test_tope_y_activacion_por_defecto():
    assert cubierta_arranque.TOPE_S == 180.0
    assert cubierta_arranque.activa({}, congelado=True, plataforma="win32") is True
    assert cubierta_arranque.activa({}, congelado=False, plataforma="win32") is False
    assert cubierta_arranque.activa({"AUTOCLAVE_CUBIERTA": "1"}, congelado=False, plataforma="win32") is True
    assert cubierta_arranque.activa({"AUTOCLAVE_CUBIERTA": "0"}, congelado=True, plataforma="win32") is False
    assert cubierta_arranque.activa({"AUTOCLAVE_CUBIERTA": "1"}, congelado=True, plataforma="linux") is False


# ── hilo de la cubierta con un núcleo doble y reloj inyectado ──────────────

class _Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class _Nucleo:
    """Doble del núcleo Win32: esperar() avanza el reloj falso."""

    def __init__(self, reloj, senales=None, falla_en=None):
        self.reloj = reloj
        self.senales = senales or {}       # puerta -> instante (relativo) en que señala
        self.falla_en = falla_en
        self.llamadas = []
        self.creadas = 0
        self.destruido = False
        self.inicio = reloj.t

    def crear(self, puertas):
        self.llamadas.append(("crear", tuple(puertas)))
        self.creadas = 2
        if self.falla_en == "crear":
            raise OSError("CreateWindowExW falló a medias")

    def senaladas(self):
        ahora = self.reloj.t - self.inicio
        return {p for p, t in self.senales.items() if ahora >= t}

    def esperar(self, ms, pendientes=None):
        self.llamadas.append(("esperar", None if pendientes is None else frozenset(pendientes)))
        if self.falla_en == "esperar":
            raise RuntimeError("bucle roto")
        assert 0 <= ms <= 250
        self.reloj.t += max(ms, 1) / 1000.0
        return True

    def reafirmar(self):
        self.llamadas.append("reafirmar")

    def despertar(self):
        self.llamadas.append("despertar")

    def destruir(self):
        self.destruido = True
        self.creadas = 0


def _correr(nucleo, reloj, **kw):
    c = Cubierta(kw.pop("puertas", (1, 2)), reloj=reloj, fabrica=lambda: nucleo, **kw)
    c.correr()          # en el hilo de la prueba: sin threads ni ventanas reales
    return c


def test_tope_de_180_s_cierra_aunque_ninguna_pantalla_avise():
    reloj = _Reloj()
    nucleo = _Nucleo(reloj)
    c = _correr(nucleo, reloj)
    assert c.motivo == "tope"
    assert 180.0 <= reloj.t - 1000.0 < 180.5
    assert nucleo.destruido and nucleo.creadas == 0
    assert c.cerrada.is_set()


def test_se_cierra_cuando_avisan_las_dos_pantallas():
    reloj = _Reloj()
    nucleo = _Nucleo(reloj, senales={1: 20.0, 2: 24.0})
    c = _correr(nucleo, reloj)
    assert c.motivo == "pantallas"
    assert 24.0 <= reloj.t - 1000.0 < 24.5
    assert nucleo.destruido


def test_gracia_tras_la_primera_si_la_otra_pantalla_no_arranca():
    reloj = _Reloj()
    nucleo = _Nucleo(reloj, senales={1: 30.0})
    c = _correr(nucleo, reloj)
    assert c.motivo == "gracia"
    assert 45.0 <= reloj.t - 1000.0 < 45.5
    assert nucleo.destruido


def test_tras_la_primera_senal_solo_espera_los_eventos_pendientes():
    """V17-s2-02: el evento de la puerta 1 sigue señalado (reinicio manual).
    El doble modela MsgWaitForMultipleObjects: si recibe un evento señalado
    vuelve al instante (sin avanzar el reloj). Con la corrección nunca se le
    pasa, así que cada espera dura su pausa y el bucle no gira en vacío."""
    reloj = _Reloj()

    class _Senalado(_Nucleo):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.giros = 0

        def esperar(self, ms, pendientes=None):
            pendientes = set(self.senales) if pendientes is None else set(pendientes)
            self.llamadas.append(("esperar", frozenset(pendientes)))
            if pendientes & self.senaladas():
                self.giros += 1            # volvería al instante: giro sin pausa
                assert self.giros < 1000, "bucle sin pausa"
                return True
            self.reloj.t += max(ms, 1) / 1000.0
            return True

    nucleo = _Senalado(reloj, senales={1: 2.0})
    c = _correr(nucleo, reloj)
    assert c.motivo == "gracia"
    assert nucleo.giros == 0
    esperas = [x[1] for x in nucleo.llamadas if isinstance(x, tuple) and x[0] == "esperar"]
    assert esperas[0] == {1, 2} and esperas[-1] == {2}


def test_nucleo_win32_pasa_solo_los_handles_pendientes():
    class _Ventanas:
        def __init__(self):
            self.handles = None

        def esperar(self, ms, handles):
            self.handles = list(handles)
            return True

    nucleo = cubierta_arranque._NucleoWin32.__new__(cubierta_arranque._NucleoWin32)
    nucleo.ventanas = _Ventanas()
    nucleo.eventos = {1: 101, 2: 202}
    assert nucleo.esperar(250, frozenset({2})) is True
    assert nucleo.ventanas.handles == [202]
    nucleo.esperar(250)
    assert nucleo.ventanas.handles == [101, 202]
    nucleo.esperar(250, frozenset())
    assert nucleo.ventanas.handles == []


def test_una_pantalla_solo_espera_la_puerta_1():
    reloj = _Reloj()
    nucleo = _Nucleo(reloj, senales={1: 5.0})
    c = _correr(nucleo, reloj, puertas=(1,))
    assert c.motivo == "pantallas"
    assert nucleo.llamadas[0] == ("crear", (1,))


def test_cerrar_desde_otro_hilo():
    reloj = _Reloj()
    nucleo = _Nucleo(reloj)
    c = Cubierta((1, 2), reloj=reloj, fabrica=lambda: nucleo)
    c._pedido.set()
    c.correr()
    assert c.motivo == "solicitado" and nucleo.destruido


@pytest.mark.parametrize("falla_en", ["crear", "esperar"])
def test_un_error_no_lanza_y_no_deja_ventanas_huerfanas(falla_en):
    reloj = _Reloj()
    nucleo = _Nucleo(reloj, falla_en=falla_en)
    c = _correr(nucleo, reloj)
    assert c.motivo == "error" and c.error
    assert nucleo.destruido and nucleo.creadas == 0
    assert c.cerrada.is_set()


def test_abrir_nunca_lanza_aunque_la_fabrica_falle():
    def fabrica():
        raise OSError("sin user32")

    c = cubierta_arranque.abrir((1, 2), fabrica=fabrica)
    assert c.esperar_cierre(5)
    assert c.motivo == "error" and "sin user32" in c.error


def test_abrir_corre_en_su_propio_hilo_y_no_bloquea():
    liberar = threading.Event()

    class _Lento(_Nucleo):
        def esperar(self, ms, pendientes=None):
            liberar.wait(5)
            return False   # WM_DESPERTAR

    reloj = _Reloj()
    c = cubierta_arranque.abrir((1, 2), reloj=reloj, fabrica=lambda: _Lento(reloj))
    assert not c.cerrada.is_set()      # abrir() volvió con la cubierta todavía abierta
    liberar.set()
    assert c.esperar_cierre(5)
    c._respaldo.cancel()


# ── el lanzador: cubierta antes de PySide, y su fallo no impide arrancar ────

class _Proc:
    def __init__(self, pid=4321):
        self.pid = pid

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return None

    def terminate(self):
        pass


@pytest.fixture
def lanzador(monkeypatch):
    from autoclave.installation import backend_guard
    from autoclave.ui_qml import doble_pantalla
    from autoclave.ui_qml.bridge import puente_instalacion

    eventos = []
    monkeypatch.setattr(exe_unico, "_log_a_archivo", lambda nombre: eventos.append("log"))
    monkeypatch.setattr(exe_unico, "_backend_responde", lambda url: False)
    monkeypatch.setattr(exe_unico, "_apagar_backend", lambda *a: None)
    monkeypatch.setattr(backend_guard, "cleanup_stale_backend", lambda: None)
    monkeypatch.setattr(backend_guard, "write_backend_pid", lambda pid: None)
    perfil = {"falta": False}
    monkeypatch.setattr(puente_instalacion, "requiere_instalacion", lambda: perfil["falta"])
    monkeypatch.setattr(doble_pantalla, "vigilar_pantallas",
                        lambda cmds, lanzar, barra=None, detener=None: eventos.append("pantallas"))

    def popen(cmd, cwd=None, env=None):
        rol = cmd[cmd.index("--rol") + 1]
        eventos.append(f"popen:{rol}")
        if rol == "ui" and perfil["falta"]:
            perfil["falta"] = False
            return SimpleNamespace(pid=1, wait=lambda timeout=None: doble_pantalla.CODIGO_INSTALACION_TERMINADA,
                                   poll=lambda: None, terminate=lambda: None)
        return _Proc()

    monkeypatch.setattr(exe_unico.subprocess, "Popen", popen)
    monkeypatch.setattr(cubierta_arranque, "activa", lambda *a, **k: True)
    cubiertas = []

    def abrir(puertas=(1, 2), **kw):
        eventos.append(f"cubierta:{','.join(map(str, puertas))}")
        c = SimpleNamespace(error=None, cerrada_pedida=0)
        c.cerrar = lambda: setattr(c, "cerrada_pedida", c.cerrada_pedida + 1)
        cubiertas.append(c)
        return c

    monkeypatch.setattr(cubierta_arranque, "abrir", abrir)

    # espía de imports: registra cuándo se pide PySide6 o la UI QML
    original = builtins.__import__

    def espia(nombre, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and (nombre.startswith("PySide6") or nombre.startswith("autoclave.ui_qml")
                           or nombre.startswith("autoclave.backend")):
            eventos.append(f"import:{nombre}")
        return original(nombre, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", espia)
    return SimpleNamespace(eventos=eventos, cubiertas=cubiertas, perfil=perfil, monkeypatch=monkeypatch)


def test_lanzador_abre_la_cubierta_antes_de_pyside_backend_y_pantallas(lanzador):
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    ev = lanzador.eventos
    assert ev[0] == "cubierta:1,2", ev
    primer_import_ui = next(i for i, e in enumerate(ev) if e.startswith("import:"))
    assert ev.index("cubierta:1,2") < primer_import_ui
    assert ev.index("cubierta:1,2") < ev.index("popen:backend") < ev.index("pantallas")
    # al terminar el lanzador se pide el cierre (por si no lo cerró la señal)
    assert lanzador.cubiertas[0].cerrada_pedida >= 1


def test_una_pantalla_solo_espera_la_puerta_1_en_el_lanzador(lanzador):
    assert exe_unico._lanzador(exe_unico._parse_args(["--una-pantalla"])) == 0
    assert lanzador.eventos[0] == "cubierta:1"


def test_cubierta_con_error_no_impide_el_arranque(lanzador):
    def abrir_falla(puertas=(1, 2), **kw):
        lanzador.eventos.append("cubierta-fallida")
        return SimpleNamespace(error="OSError: sin user32", cerrar=lambda: None)

    lanzador.monkeypatch.setattr(cubierta_arranque, "abrir", abrir_falla)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    assert "popen:backend" in lanzador.eventos and "pantallas" in lanzador.eventos


def test_cubierta_que_lanza_no_impide_el_arranque(lanzador):
    def abrir_lanza(puertas=(1, 2), **kw):
        raise RuntimeError("inesperado")

    lanzador.monkeypatch.setattr(cubierta_arranque, "abrir", abrir_lanza)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    assert "popen:backend" in lanzador.eventos and "pantallas" in lanzador.eventos


def test_tras_el_asistente_se_vuelve_a_abrir_la_cubierta(lanzador):
    lanzador.perfil["falta"] = True
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    ev = lanzador.eventos
    assert [e for e in ev if e.startswith("cubierta")] == ["cubierta:1,2", "cubierta:1,2"]
    assert lanzador.cubiertas[0].cerrada_pedida >= 1
    # la segunda se abre antes del backend y de las pantallas normales
    segunda = len(ev) - 1 - ev[::-1].index("cubierta:1,2")
    assert segunda < ev.index("popen:backend") < ev.index("pantallas")


def test_cubierta_inactiva_en_desarrollo_no_se_abre(lanzador):
    lanzador.monkeypatch.setattr(cubierta_arranque, "activa", lambda *a, **k: False)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    assert not any(e.startswith("cubierta") for e in lanzador.eventos)


def test_modulos_de_la_cubierta_no_importan_pyside():
    """En un proceso limpio: importar el lanzador y la cubierta no carga Qt."""
    codigo = ("import sys; import autoclave.exe_unico, autoclave.estacion.cubierta_arranque, "
              "autoclave.estacion.primer_cuadro, autoclave.estacion._ventanas; "
              "print(any(m.split('.')[0] == 'PySide6' for m in sys.modules))")
    import autoclave
    entorno = {**os.environ, "PYTHONPATH": str(Path(autoclave.__file__).resolve().parents[1])}
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=60,
                       cwd=str(RAIZ), env=entorno)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "False"


# ── señal de primer cuadro ──────────────────────────────────────────────────

class _ApiEventos:
    def __init__(self, existe=True):
        self.existe = existe
        self.llamadas = []

    def OpenEventW(self, permiso, heredar, nombre):
        self.llamadas.append(("open", nombre))
        return 77 if self.existe else 0

    def SetEvent(self, h):
        self.llamadas.append(("set", h))
        return 1

    def CloseHandle(self, h):
        self.llamadas.append(("close", h))
        return 1


def test_senalar_abre_el_evento_de_la_puerta_y_lo_cierra():
    api = _ApiEventos()
    assert primer_cuadro.senalar(2, api=api) is True
    assert api.llamadas == [("open", "Local\\EspecifikaAutoclavePrimerCuadroP2"), ("set", 77), ("close", 77)]


def test_senalar_sin_cubierta_no_hace_nada():
    api = _ApiEventos(existe=False)
    assert primer_cuadro.senalar(1, api=api) is False
    assert api.llamadas == [("open", "Local\\EspecifikaAutoclavePrimerCuadroP1")]


def test_aviso_primer_cuadro_de_app_avisa_una_sola_vez():
    from autoclave.ui_qml.app import AvisoPrimerCuadro, avisar_primer_cuadro

    class _Senal:
        def __init__(self):
            self.conectados, self.desconectados = [], []

        def connect(self, slot, tipo=None):
            self.conectados.append((slot, tipo))

        def disconnect(self, slot):
            self.desconectados.append(slot)

    ventana = SimpleNamespace(frameSwapped=_Senal())
    avisos = []
    aviso = AvisoPrimerCuadro(ventana, 2, senalar=avisos.append)
    assert len(ventana.frameSwapped.conectados) == 1
    aviso._al_cuadro()
    aviso._al_cuadro()
    assert avisos == [2]
    assert len(ventana.frameSwapped.desconectados) == 1
    # sin frameSwapped (doble mínimo) no rompe la apertura de la pantalla
    assert avisar_primer_cuadro(SimpleNamespace(), 1) is None


def test_app_engancha_el_aviso_en_las_tres_ventanas():
    texto = (RAIZ / "src" / "autoclave" / "ui_qml" / "app.py").read_text(encoding="utf-8")
    assert texto.count("avisar_primer_cuadro(ventana, args.door)") == 3


# ── tarea de arranque sin retraso ───────────────────────────────────────────

@pytest.mark.parametrize("ruta", ["tools/instalador/tarea_arranque.ps1", "tools/estacion/03_tarea_autoclave.ps1"])
def test_tarea_de_arranque_sin_retraso(ruta):
    s = (RAIZ / ruta).read_text(encoding="ascii")
    assert "$disparo.Delay = 'PT0S'" in s
    assert "$disparo.Delay = 'PT10S'" not in s
    assert s.count("$disparo.Delay =") == 1


def test_03_ejecutable_por_defecto_desde_ruta_programa():
    s = (RAIZ / "tools/estacion/03_tarea_autoclave.ps1").read_text(encoding="ascii")
    assert "OpenBaseKey('LocalMachine', 'Registry64')" in s
    assert "OpenSubKey('SOFTWARE\\Especifika\\Autoclave', $false)" in s
    assert "GetValue('RutaPrograma', $null)" in s
    assert "Join-Path $env:ProgramFiles 'Especifika\\Autoclave\\Autoclave.exe'" in s   # respaldo de antes
    assert s.index("if (-not $Ejecutable) { $Ejecutable = Get-EjecutablePorDefecto }") < s.index("== Inicio $Paso")


# ── V17-s2-01: un solo lanzador por sesión (mutex con nombre) ───────────────

from autoclave.estacion import instancia_unica  # noqa: E402


class _ApiMutex:
    """Doble de kernel32: un mutex con nombre que existe mientras haya handles."""

    def __init__(self, abiertos=0, falla=False):
        self.abiertos = abiertos
        self.falla = falla
        self._ultimo = 0
        self.nombres = []
        self.cerrados = 0

    def CreateMutexW(self, atributos, propietario, nombre):
        self.nombres.append(nombre)
        if self.falla:
            self._ultimo = 5
            return 0
        self._ultimo = instancia_unica.ERROR_ALREADY_EXISTS if self.abiertos else 0
        self.abiertos += 1
        return 900 + self.abiertos

    def GetLastError(self):
        return self._ultimo

    def CloseHandle(self, h):
        self.abiertos -= 1
        self.cerrados += 1
        return 1


def test_mutex_primera_instancia_y_segunda():
    api = _ApiMutex()
    primera = instancia_unica.tomar(api=api)
    assert primera.primera and primera.handle and api.nombres == ["Local\\EspecifikaAutoclaveLanzador"]
    segunda = instancia_unica.tomar(api=api)
    assert not segunda.primera and segunda.handle is None
    assert api.abiertos == 1                 # la segunda cerró su handle
    primera.soltar()
    assert api.abiertos == 0


def test_mutex_relanzamiento_espera_a_la_anterior_con_reloj_inyectado():
    api = _ApiMutex(abiertos=1)
    reloj = _Reloj()
    intentos = []

    def dormir(s):
        intentos.append(s)
        reloj.t += s
        if len(intentos) == 3:
            api.abiertos -= 1               # la instancia anterior terminó

    inst = instancia_unica.tomar(esperar_s=60, api=api, reloj=reloj, dormir=dormir)
    assert inst.primera and len(intentos) == 3

    api2 = _ApiMutex(abiertos=1)
    reloj2 = _Reloj()
    inst2 = instancia_unica.tomar(esperar_s=60, api=api2, reloj=reloj2,
                                  dormir=lambda s: setattr(reloj2, "t", reloj2.t + s))
    assert not inst2.primera and 60 <= reloj2.t - 1000 < 61     # tope, sin dormir de verdad


def test_mutex_que_falla_no_impide_arrancar():
    inst = instancia_unica.tomar(api=_ApiMutex(falla=True))
    assert inst.primera and "CreateMutexW" in inst.error


def test_mutex_activo_solo_congelado_o_con_variable():
    assert instancia_unica.activa({}, congelado=True, plataforma="win32") is True
    assert instancia_unica.activa({}, congelado=False, plataforma="win32") is False
    assert instancia_unica.activa({"AUTOCLAVE_INSTANCIA_UNICA": "0"}, congelado=True, plataforma="win32") is False
    assert instancia_unica.activa({}, congelado=True, plataforma="linux") is False


def _con_mutex(lanzador, api):
    lanzador.monkeypatch.setattr(instancia_unica, "activa", lambda *a, **k: True)
    original = instancia_unica.tomar
    lanzador.monkeypatch.setattr(instancia_unica, "tomar", lambda **kw: original(api=api, **kw))


def test_segundo_lanzador_no_abre_cubierta_ni_lanza_nada(lanzador):
    api = _ApiMutex(abiertos=1)              # ya hay un lanzador vivo en la sesión
    _con_mutex(lanzador, api)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    assert not any(e.startswith(("cubierta", "popen", "pantallas", "import:")) for e in lanzador.eventos), \
        lanzador.eventos
    assert api.abiertos == 1                 # no se quedó con ningún handle


def test_primer_lanzador_toma_el_mutex_antes_de_la_cubierta_y_lo_suelta_al_final(lanzador):
    api = _ApiMutex()
    _con_mutex(lanzador, api)
    vivo = []
    original = exe_unico._lanzador_con_cubierta

    def espia(*a, **k):
        vivo.append(api.abiertos)            # el mutex vive mientras corre el lanzador
        return original(*a, **k)

    lanzador.monkeypatch.setattr(exe_unico, "_lanzador_con_cubierta", espia)
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    assert vivo == [1]
    assert lanzador.eventos[0] == "cubierta:1,2" and "popen:backend" in lanzador.eventos
    assert api.abiertos == 0                 # soltado al terminar


def test_mutex_que_falla_el_lanzador_sigue(lanzador):
    _con_mutex(lanzador, _ApiMutex(falla=True))
    assert exe_unico._lanzador(exe_unico._parse_args([])) == 0
    assert "popen:backend" in lanzador.eventos and "pantallas" in lanzador.eventos


def test_relanzado_r11_espera_el_mutex_con_el_tope_de_instancia(lanzador, monkeypatch):
    pedidos = []
    monkeypatch.setattr(instancia_unica, "activa", lambda *a, **k: True)
    monkeypatch.setattr(instancia_unica, "tomar",
                        lambda **kw: pedidos.append(kw) or instancia_unica.Instancia(primera=True))
    monkeypatch.setattr(exe_unico, "esperar_instancia_anterior", lambda *a, **k: True)
    exe_unico._lanzador(exe_unico._parse_args(["--esperar-pid", "123"]))
    exe_unico._lanzador(exe_unico._parse_args([]))
    assert pedidos == [{"esperar_s": exe_unico.TOPE_ESPERA_INSTANCIA_S}, {"esperar_s": 0.0}]


# ── V17-s2-03: 03 reemplaza una tarea con retraso ───────────────────────────

def test_03_reemplaza_la_tarea_si_tiene_retraso():
    s = (RAIZ / "tools/estacion/03_tarea_autoclave.ps1").read_text(encoding="ascii")
    assert "$trigExistente = $existente.Triggers | Select-Object -First 1" in s
    assert "$sinRetraso = ($delayExistente -eq '' -or $delayExistente -eq 'PT0S')" in s
    assert ("if ($acc.Execute -eq $Ejecutable -and $existente.Principal.UserId -like \"*$Usuario\" "
            "-and $sinRetraso) {") in s


@pytest.mark.skipif(__import__("shutil").which("powershell.exe") is None, reason="sin powershell.exe")
def test_parser_de_powershell_03_tarea_arranque_y_06():
    """Solo analiza (Parser::ParseFile): no ejecuta ningún script."""
    import json
    archivos = [str(RAIZ / "tools/estacion/03_tarea_autoclave.ps1"),
                str(RAIZ / "tools/instalador/tarea_arranque.ps1"),
                str(RAIZ / "tools/estacion/06_asociar_tactiles.ps1")]
    lista = ",".join(f"'{a}'" for a in archivos)
    orden = (f"$r=@(); foreach($f in @({lista})){{$t=$null;$e=$null;"
             "[void][System.Management.Automation.Language.Parser]::ParseFile($f,[ref]$t,[ref]$e);"
             "$r+=@{f=$f;n=$e.Count}}; $r | ConvertTo-Json -Compress")
    salida = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", orden],
                            capture_output=True, text=True, timeout=120)
    datos = json.loads(salida.stdout)
    assert [d["n"] for d in datos] == [0, 0, 0], datos
