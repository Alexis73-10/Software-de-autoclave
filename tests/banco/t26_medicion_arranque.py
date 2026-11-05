"""Tanda 26 (ARQ): medición de tiempos del arranque retenido con el simulador M31.

No es una prueba automática. Arma el backend real (BackendContext, secuencia,
ModbusLink, ControlLoop, rutas) contra el simulador M31 de tests/helpers (solo
127.0.0.1) y hace de UI de la puerta 1 con el mismo protocolo que
ProgresoArranqueBackend: «UI visible» (primer cuadro), POST /arranque/iniciar,
sondeo de GET /arranque cada 0,3 s, fin de la intro (3,5 s + 1 s de salida,
y al menos la repetición de etapas a 0,35 s por etapa) y
POST /arranque/interfaz-lista. Mide: UI visible, iniciar, fin de cada etapa,
interfaz-lista, liberación y entrada a PREPARACION (primer tick de la máquina
de estados), y comprueba que ninguna bobina se escribió en ON antes de la
liberación.

Uso (desde la raíz del repo):
    python tests/banco/t26_medicion_arranque.py [--repeticiones N] [--salida ARCHIVO]
"""

import argparse
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))

PERMANENCIA_S = 0.35       # repetición visible por etapa (ProgresoArranqueBackend)
SONDEO_S = 0.3


def medir(tmp: Path) -> dict:
    from fastapi.testclient import TestClient

    from autoclave.backend import context as ctx_mod
    from autoclave.backend.arranque.secuencia import ejecutar_arranque
    from autoclave.backend.context import BackendContext
    from autoclave.core.runtime.status import EstadoAutoclave
    from autoclave.protocols import modbus_link
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB
    from tests.helpers.backend_doble import cargar_servidor
    from tests.helpers.m31_simulado import M31Simulado, config_para
    from tests.test_t20_integracion import MAC_BANCO, _perfil

    sim = M31Simulado()
    sim.fijar_mac(MAC_BANCO)
    sim.precargar_configuracion()
    sim.iniciar()
    sim.di[EstadoAutoclave.map_di["paro_emergencia"]] = True
    sim.temperaturas[0] = 250
    sim.corrientes[0] = 8000           # ~100 kPa abs en la cámara
    sim.corrientes[1] = 15000          # chaqueta
    parches = [
        patch.object(modbus_link, "cargar_config", lambda *a, **k: config_para(sim)),
        patch.object(ctx_mod, "get_installation_profile", _perfil),
        patch.object(ctx_mod, "DbManager", lambda: DbManager(tmp / "autoclave.db")),
        patch.object(ctx_mod, "SensorCalibrationAuditDB",
                     lambda: SensorCalibrationAuditDB(tmp / "calibracion.db")),
        patch.object(ctx_mod, "RealtimePrinter", MagicMock),
    ]
    for p in parches:
        p.start()
    ctx = srv = None
    try:
        ctx = BackendContext()
        srv, _ = cargar_servidor(ctx)
        srv.preparar_arranque()
        srv.ejecutar_arranque = lambda *a, **k: ejecutar_arranque(*a, **k, esperar_interfaz=True)
        cliente = TestClient(srv.app)
        reg = srv.registro_arranque

        t0 = time.monotonic()          # «UI visible»: primer cuadro de la intro
        marcas = {"ui_visible": 0.0}
        assert cliente.post("/arranque/iniciar").status_code == 200
        marcas["iniciar"] = time.monotonic() - t0
        n_bobinas_al_liberar = None
        t_terminado = None
        while True:
            a = cliente.get("/arranque").json()
            ahora = time.monotonic() - t0
            if a["terminado"] and t_terminado is None:
                t_terminado = ahora
            if t_terminado is not None:
                etapas = sum(1 for e in a["etapas"] if e["clave"] != "preparando_interfaz")
                # la repetición empieza a los 3,5 s (0,35 s por etapa) y la
                # salida (1 s) solo con todo cumplido y mostrado
                fin_intro = max(3.5 + PERMANENCIA_S * etapas, t_terminado) + 1.0
                if ahora >= fin_intro:
                    break
            if ahora > 60:
                raise RuntimeError("el backend no terminó sus etapas en 60 s")
            time.sleep(SONDEO_S)
        retenido_on = [w for w in sim.escrituras_bobinas() if any(bool(v) for v in w[2])]
        marcas["etapas_terminadas"] = t_terminado
        assert cliente.post("/arranque/interfaz-lista").status_code == 200
        marcas["interfaz_lista"] = time.monotonic() - t0
        while not ctx.arranque_liberado.is_set():
            time.sleep(0.005)
        marcas["liberado"] = time.monotonic() - t0
        n_bobinas_al_liberar = len(sim.escrituras_bobinas())
        while ctx.control_loop.state_machine.prev_state is None:
            if time.monotonic() - t0 > 90:
                raise RuntimeError("la máquina de estados no corrió")
            time.sleep(0.005)
        marcas["preparacion"] = time.monotonic() - t0
        marcas["estado_maquina"] = ctx.estado.get_machine_state().name
        etapas = {}
        t_ini = None
        with reg._lock:
            for e in reg._etapas:
                if e.t_inicio is not None and (t_ini is None or e.t_inicio < t_ini):
                    t_ini = e.t_inicio
            for e in reg._etapas:
                if e.t_fin is not None:
                    etapas[e.clave] = (e.estado.value, e.codigo,
                                       round(e.t_fin - e.t_inicio, 3) if e.t_inicio else None)
        marcas["etapas"] = etapas
        marcas["bobinas_on_antes_de_liberar"] = len(retenido_on)
        marcas["escrituras_bobinas_antes_de_liberar"] = n_bobinas_al_liberar
        return marcas
    finally:
        if srv is not None:
            srv._detener_arranque.set()
            if srv._hilo_arranque is not None:
                srv._hilo_arranque.join(3)
        if ctx is not None and ctx.control_loop is not None:
            ctx.control_loop.stop()
        if ctx is not None and ctx.serial is not None:
            ctx.serial.stop()
        sim.detener()
        for p in parches:
            p.stop()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--salida", type=Path)
    args = ap.parse_args()
    filas = []
    for i in range(args.repeticiones):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            m = medir(Path(d))
        filas.append(m)
        print(f"corrida {i + 1}: {m}", flush=True)
    claves = ("iniciar", "etapas_terminadas", "interfaz_lista", "liberado", "preparacion")
    lineas = ["| corrida | " + " | ".join(claves) + " | bobinas ON antes de liberar | estado |",
              "|---|" + "---|" * (len(claves) + 2)]
    for i, m in enumerate(filas, 1):
        lineas.append(f"| {i} | " + " | ".join(f"{m[k]:.2f}" for k in claves)
                      + f" | {m['bobinas_on_antes_de_liberar']} | {m['estado_maquina']} |")
    lineas.append("")
    lineas.append("Duración de cada etapa (s), corrida 1:")
    for clave, (estado, codigo, dur) in filas[0]["etapas"].items():
        lineas.append(f"- {clave}: {estado}{' [' + codigo + ']' if codigo else ''} {dur}")
    texto = "\n".join(lineas)
    print(texto)
    if args.salida:
        args.salida.write_text(texto + "\n", encoding="utf-8")
    return 0 if all(m["bobinas_on_antes_de_liberar"] == 0 for m in filas) else 1


if __name__ == "__main__":
    sys.exit(main())
