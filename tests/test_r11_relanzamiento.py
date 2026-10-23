"""R11 (tanda 11, D11-1.2 y D11-1.4): relanzamiento de Autoclave.exe tras
`reiniciar_software`, con una sola instancia.

- El backend termina con CODIGO_REINICIO_SOFTWARE; el lanzador cierra las
  pantallas, detiene su vigilancia y, ya terminado el backend, lanza de nuevo
  el mismo comando con `--esperar-pid` (el suyo y el del backend).
- La instancia nueva espera a que esos procesos terminen Y el puerto del
  backend quede libre antes de arrancar; si no se libera, NO lanza un segundo
  backend (usa el que responde, como siempre).
- En desarrollo (sin exe congelado), el mismo comando con el que arrancó.

Todo con lanzadores simulados: ningún proceso real."""

import threading
from types import SimpleNamespace

import pytest

from autoclave import exe_unico
from autoclave.backend import reinicio
from autoclave.installation import backend_guard
from autoclave.ui_qml import doble_pantalla
from autoclave.ui_qml.bridge import puente_instalacion


# ── backend: código de salida ───────────────────────────────────────────────

def test_solicitar_con_codigo_de_software_lo_deja_como_salida(monkeypatch):
    monkeypatch.setattr(reinicio, "_al_reiniciar", None)
    detenido = threading.Event()
    reinicio.registrar(detenido.set)
    assert reinicio.solicitar("prueba", retraso_s=0, dormir=lambda s: None,
                              codigo=reinicio.CODIGO_REINICIO_SOFTWARE)
    assert detenido.wait(2)
    assert reinicio.solicitado() and reinicio.codigo_salida() == reinicio.CODIGO_REINICIO_SOFTWARE
    reinicio.registrar(lambda: None)                 # deja limpio el estado del módulo
    monkeypatch.setattr(reinicio, "_al_reiniciar", None)


def test_el_reinicio_del_control_conserva_su_codigo(monkeypatch):
    monkeypatch.setattr(reinicio, "_al_reiniciar", None)
    reinicio.registrar(lambda: None)
    assert reinicio.solicitar("r8", retraso_s=0, dormir=lambda s: None)
    assert reinicio.codigo_salida() == reinicio.CODIGO_REINICIO
    assert reinicio.CODIGO_REINICIO_SOFTWARE != reinicio.CODIGO_REINICIO
    monkeypatch.setattr(reinicio, "_al_reiniciar", None)


class _Proc:
    def __init__(self, codigo=None, pid=111):
        self.codigo = codigo
        self.pid = pid
        self.terminado = False

    def poll(self):
        return self.codigo

    def terminate(self):
        self.terminado = True
        self.codigo = 1

    def wait(self, timeout=None):
        return self.codigo

    def kill(self):
        self.codigo = 1


def test_el_lanzador_no_relanza_solo_el_backend_ante_el_codigo_de_software():
    proc = _Proc(codigo=reinicio.CODIGO_REINICIO_SOFTWARE)
    relanzados, avisos = [], []
    reinicio.vigilar_reinicios(lambda: proc, lambda: relanzados.append(1), threading.Event(),
                               pausa_s=0, al_reiniciar_software=lambda: avisos.append(1))
    assert relanzados == [] and avisos == [1]


# ── pantallas: se cierran al pedirlo, sin relanzarse ───────────────────────

def test_vigilar_pantallas_cierra_todas_al_detener_sin_relanzar():
    procs, lanzados = [], []
    detener = threading.Event()

    def lanzar(cmd):
        lanzados.append(cmd)
        p = _Proc()
        procs.append(p)
        return p

    vueltas = {"n": 0}

    def dormir(_s):
        vueltas["n"] += 1
        if vueltas["n"] == 2:
            detener.set()
    doble_pantalla.vigilar_pantallas([["ui", "1"], ["ui", "2"]], lanzar, dormir=dormir,
                                     detener=detener)
    assert all(p.terminado for p in procs) and len(lanzados) == 2


# ── relanzamiento del mismo comando ────────────────────────────────────────

def test_relanzar_usa_el_mismo_comando_en_desarrollo(monkeypatch):
    monkeypatch.setattr(exe_unico.sys, "frozen", False, raising=False)
    llamadas = []
    ok = exe_unico.relanzar_software(["--una-pantalla", "--esperar-pid", "5"], [10, 20],
                                     popen=lambda cmd, **k: llamadas.append((cmd, k)))
    assert ok
    [(cmd, k)] = llamadas
    assert cmd == [exe_unico.sys.executable, "-m", "autoclave.exe_unico", "--una-pantalla",
                   "--esperar-pid", "10", "--esperar-pid", "20"]
    assert "_MEIPASS2" not in k["env"] and k["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def test_relanzar_en_el_exe_congelado_usa_el_exe(monkeypatch):
    monkeypatch.setattr(exe_unico.sys, "frozen", True, raising=False)
    llamadas = []
    exe_unico.relanzar_software([], [10], popen=lambda cmd, **k: llamadas.append(cmd))
    assert llamadas == [[exe_unico.sys.executable, "--esperar-pid", "10"]]


def test_si_el_relanzamiento_falla_queda_en_el_log(caplog):
    def falla(cmd, **k):
        raise OSError("sin permiso")
    with caplog.at_level("ERROR"):
        assert exe_unico.relanzar_software([], [10], popen=falla) is False
    assert any("apague y encienda" in r.getMessage() for r in caplog.records)


# ── la instancia nueva espera a la anterior ────────────────────────────────

def test_espera_a_que_terminen_los_procesos_y_se_libere_el_puerto():
    vivos = {10: 3, 20: 1}            # vueltas que sigue vivo cada PID
    puerto = {"ocupado": 4}
    eventos = []

    def pid_vivo(pid):
        vivos[pid] -= 1
        return vivos[pid] >= 0

    def ocupado():
        puerto["ocupado"] -= 1
        eventos.append("puerto")
        return puerto["ocupado"] >= 0
    ok = exe_unico.esperar_instancia_anterior([10, 20], tope_s=60, pid_vivo=pid_vivo,
                                              puerto_ocupado=ocupado, dormir=lambda s: None,
                                              reloj=iter(range(1000)).__next__)
    assert ok and puerto["ocupado"] < 0


def test_si_no_se_libera_a_tiempo_lo_registra_y_sigue(caplog):
    reloj = iter(range(0, 1000, 10)).__next__
    with caplog.at_level("ERROR"):
        ok = exe_unico.esperar_instancia_anterior([10], tope_s=30, pid_vivo=lambda p: True,
                                                  puerto_ocupado=lambda: True,
                                                  dormir=lambda s: None, reloj=reloj)
    assert ok is False and caplog.records


# ── el lanzador completo con procesos simulados ────────────────────────────

@pytest.fixture
def lanzador(monkeypatch):
    lanzados, orden = [], []
    monkeypatch.setattr(exe_unico, "_log_a_archivo", lambda nombre: None)
    monkeypatch.setattr(backend_guard, "cleanup_stale_backend", lambda: None)
    monkeypatch.setattr(backend_guard, "write_backend_pid", lambda pid: None)
    monkeypatch.setattr(puente_instalacion, "requiere_instalacion", lambda: False)
    return SimpleNamespace(lanzados=lanzados, orden=orden, monkeypatch=monkeypatch)


def test_reinicio_completo_cierra_pantallas_y_relanza_despues_del_backend(lanzador):
    """El backend termina con el código de software: las pantallas se cierran,
    el backend ya terminó y recién entonces se relanza el mismo comando con
    los PID a esperar. Ningún proceso real."""
    lz = lanzador
    backend = _Proc(pid=777)

    def popen(cmd, cwd=None, env=None, **k):
        lz.lanzados.append(cmd)
        return backend
    lz.monkeypatch.setattr(exe_unico.subprocess, "Popen", popen)
    lz.monkeypatch.setattr(exe_unico, "_backend_responde", lambda url: False)
    lz.monkeypatch.setattr(exe_unico, "_apagar_backend",
                           lambda url, proc, log: lz.orden.append(("apagar_backend", proc.poll())))
    relanzados = []
    lz.monkeypatch.setattr(exe_unico, "relanzar_software",
                           lambda argv, pids, **k: (lz.orden.append(("relanzar", backend.poll())),
                                                    relanzados.append((argv, pids)), True)[-1])

    def vigilar(cmds, lanzar, barra=None, detener=None):
        lz.orden.append("pantallas")
        backend.codigo = reinicio.CODIGO_REINICIO_SOFTWARE       # el backend pide reiniciar
        assert detener.wait(5)                                    # el lanzador cierra las pantallas
        lz.orden.append("pantallas_cerradas")
    lz.monkeypatch.setattr(doble_pantalla, "vigilar_pantallas", vigilar)

    args = exe_unico._parse_args(["--una-pantalla"])
    args.argv_original = ["--una-pantalla"]
    assert exe_unico._lanzador(args) == 0
    assert [o if isinstance(o, str) else o[0] for o in lz.orden] == [
        "pantallas", "pantallas_cerradas", "apagar_backend", "relanzar"]
    assert lz.orden[-1][1] == reinicio.CODIGO_REINICIO_SOFTWARE   # backend ya terminado
    [(argv, pids)] = relanzados
    assert argv == ["--una-pantalla"]
    assert backend.pid in pids and exe_unico.os.getpid() in pids


def test_saf04_pantallas_cerradas_a_la_vez_que_el_backend_pide_reiniciar(lanzador):
    """SAF-04: vigilar_pantallas termina por su cuenta justo cuando el backend
    sale con el código de software (antes de que el vigilante lo vea): se
    relanza igual."""
    lz = lanzador
    backend = _Proc(pid=777)
    lz.monkeypatch.setattr(exe_unico.subprocess, "Popen", lambda cmd, **k: backend)
    lz.monkeypatch.setattr(exe_unico, "_backend_responde", lambda url: False)
    lz.monkeypatch.setattr(exe_unico, "_apagar_backend", lambda *a: None)
    # el vigilante no llega a ver el código
    lz.monkeypatch.setattr(reinicio, "vigilar_reinicios", lambda *a, **k: None)
    relanzados = []
    lz.monkeypatch.setattr(exe_unico, "relanzar_software",
                           lambda argv, pids, **k: relanzados.append(pids) or True)

    def vigilar(cmds, lanzar, **k):
        backend.codigo = reinicio.CODIGO_REINICIO_SOFTWARE
    lz.monkeypatch.setattr(doble_pantalla, "vigilar_pantallas", vigilar)
    assert exe_unico._lanzador(exe_unico._parse_args(["--una-pantalla"])) == 0
    assert len(relanzados) == 1 and backend.pid in relanzados[0]


def test_sin_reinicio_no_se_relanza(lanzador):
    lz = lanzador
    backend = _Proc(pid=777)
    lz.monkeypatch.setattr(exe_unico.subprocess, "Popen", lambda cmd, **k: backend)
    lz.monkeypatch.setattr(exe_unico, "_backend_responde", lambda url: False)
    lz.monkeypatch.setattr(exe_unico, "_apagar_backend", lambda *a: None)
    relanzados = []
    lz.monkeypatch.setattr(exe_unico, "relanzar_software", lambda *a, **k: relanzados.append(1))
    lz.monkeypatch.setattr(doble_pantalla, "vigilar_pantallas", lambda cmds, lanzar, **k: None)
    assert exe_unico._lanzador(exe_unico._parse_args(["--una-pantalla"])) == 0
    assert relanzados == []


def test_la_instancia_nueva_no_lanza_backend_hasta_que_el_puerto_se_libere(lanzador):
    lz = lanzador
    estado = {"puerto": 3}

    def ocupado():
        estado["puerto"] -= 1
        lz.orden.append("consulta_puerto")
        return estado["puerto"] > 0
    lz.monkeypatch.setattr(exe_unico, "_pid_vivo", lambda pid: False)
    lz.monkeypatch.setattr(exe_unico, "_puerto_backend_ocupado", ocupado)
    lz.monkeypatch.setattr(exe_unico.time, "sleep", lambda s: None)
    lz.monkeypatch.setattr(exe_unico, "_backend_responde", lambda url: estado["puerto"] > 0)
    lz.monkeypatch.setattr(exe_unico, "_apagar_backend", lambda *a: None)

    def popen(cmd, **k):
        lz.orden.append("lanzar_" + cmd[cmd.index("--rol") + 1])
        return _Proc()
    lz.monkeypatch.setattr(exe_unico.subprocess, "Popen", popen)
    lz.monkeypatch.setattr(doble_pantalla, "vigilar_pantallas", lambda cmds, lanzar, **k: None)
    assert exe_unico._lanzador(exe_unico._parse_args(["--una-pantalla", "--esperar-pid", "10"])) == 0
    assert lz.orden == ["consulta_puerto"] * 3 + ["lanzar_backend"]


def test_si_el_puerto_sigue_ocupado_no_queda_un_segundo_backend(lanzador):
    """Tope vencido con el backend anterior escuchando: se usa ese, no se lanza otro."""
    lz = lanzador
    lz.monkeypatch.setattr(exe_unico, "esperar_instancia_anterior", lambda pids, **k: False)
    lz.monkeypatch.setattr(exe_unico, "_backend_responde", lambda url: True)
    lanzados = []
    lz.monkeypatch.setattr(exe_unico.subprocess, "Popen",
                           lambda cmd, **k: lanzados.append(cmd) or _Proc())
    lz.monkeypatch.setattr(doble_pantalla, "vigilar_pantallas", lambda cmds, lanzar, **k: None)
    assert exe_unico._lanzador(exe_unico._parse_args(["--esperar-pid", "10"])) == 0
    assert not any("backend" in c for c in lanzados)


def test_parse_args_acepta_varios_pid_a_esperar():
    args = exe_unico._parse_args(["--esperar-pid", "1", "--esperar-pid", "2"])
    assert args.esperar_pid == [1, 2]
    assert exe_unico._parse_args([]).esperar_pid == []
