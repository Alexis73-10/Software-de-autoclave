"""Tanda 26 (ESP): medición de la latencia de una salida en modo prueba con el
simulador M31 (127.0.0.1) y el backend completo (BackendContext, arranque,
ModbusLink, ControlLoop real con su periodo de 0,5 s, rutas), más el caché de
/status de la UI (UIServiceBackend, 0,2 s) y el controlador de Entradas/Salidas.

No es una prueba automática. Uso (desde la raíz, PYTHONPATH=src):
    python tests/banco/t26_esp_latencia_salidas.py [--n 10] [--salida nombre]

Instantes (time.monotonic) por orden ON/OFF de una salida sostenida:
  toque           -> llamada a EntradasSalidasController.alternar()
  resp            -> respuesta del PATCH /io/test/output/{nombre}
  fc05            -> la bobina cambia en el simulador (escritura fc05 hecha)
  estado          -> EstadoAutoclave.salidas_do refleja el cambio (tick del lazo)
  status          -> primer /status del caché (pedido después de la respuesta)
                     que lo refleja
  ui_antes        -> la pantalla de antes lo mostraría (Timer de 1 s, fase al
                     azar, descartando /status pedidos antes de la orden)
  ui_ahora        -> la orden pendiente se resuelve con la relectura de 0,2 s
                     (el botón ya mostraba lo ordenado desde `resp`)
El «repintado» se toma como la emisión de cambioDatos (sin QML: la pantalla
se repinta en el mismo ciclo de eventos)."""

import argparse
import os
import random
import statistics
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("AUTOCLAVE_ESPERA_INTERFAZ", "0")   # ARQ-D7 (fuera del compilado)


def _perfil():
    from autoclave.devices.puertas.door_type import DoorType
    from autoclave.installation.equipment import EquipmentClass
    from autoclave.installation.profile import InstallationProfile, Role
    return InstallationProfile(
        machine_id="TEST-001", model_id="MX-TEST", serial_number="ACV-TEST",
        equipment_class=EquipmentClass.MESA_N, door_count=1, door_type=DoorType.SIMPLE,
        cooling_level=0, door_id=1, role=Role.OPERATOR_FRONT,
        created_at=datetime(2026, 1, 1), locked=False)


def _esperar(cond, timeout=10.0, paso=0.002):
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        if cond():
            return time.monotonic()
        time.sleep(paso)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10, help="órdenes ON/OFF (pares)")
    ap.add_argument("--salida", default="", help="salida sostenida (por defecto la primera libre)")
    args = ap.parse_args()

    from fastapi.testclient import TestClient
    from PySide6.QtCore import QCoreApplication

    from autoclave.backend import context as ctx_mod
    from autoclave.backend.arranque.secuencia import ejecutar_arranque
    from autoclave.backend.context import BackendContext
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    from autoclave.core.runtime import io_names
    from autoclave.core.runtime.status import EstadoAutoclave
    from autoclave.protocols import modbus_link
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.services.domain.logging.sensor_calibration_audit import (
        SensorCalibrationAuditDB)
    from autoclave.ui_qml.controllers import entradas_salidas_controller as m
    from autoclave.ui_qml.sesion_backend import Resultado
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    from tests.helpers.m31_simulado import M31Simulado, config_para

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp(prefix="t26_esp_"))
    sim = M31Simulado()
    sim.iniciar()
    sim.di[EstadoAutoclave.map_di["paro_emergencia"]] = True
    sim.temperaturas[0] = 250
    sim.corrientes[0] = 8000 + 1880        # ≈ 101 kPa abs
    # periodo de sondeo de producción (config/modbus_link.json: 0,1 s)
    modbus_link.cargar_config = lambda *a, **k: config_para(sim, periodo_sondeo_s=0.1)
    ctx_mod.get_installation_profile = _perfil
    ctx_mod.DbManager = lambda: DbManager(tmp / "autoclave.db")
    ctx_mod.SensorCalibrationAuditDB = lambda: SensorCalibrationAuditDB(tmp / "cal.db")
    ctx_mod.RealtimePrinter = MagicMock

    ctx = BackendContext()
    srv, _ = cargar_servidor(ctx)
    srv.preparar_arranque()
    threading.Thread(target=ejecutar_arranque, args=(ctx, srv.registro_arranque),
                     kwargs={"al_cancelar_prueba": srv._prueba_cancelada_por_paro,
                             "al_operable": srv._contexto_operable.set,
                             "detener": srv._detener_arranque,
                             "plazo_es_s": 10.0, "pausa_es_s": 0.05},
                     daemon=True).start()
    client = TestClient(srv.app)
    # Por si el arranque espera a la interfaz (ARQ, tanda 26): se avisa
    for ruta in ("/arranque/iniciar",):
        try:
            client.post(ruta)
        except Exception:
            pass
    if _esperar(lambda: client.get("/status").json().get("card_connected") is True, 30) is None:
        print("El módulo simulado no quedó conectado"); return 2
    try:
        client.post("/arranque/interfaz-lista")
    except Exception:
        pass
    _esperar(lambda: client.get("/status").json().get("machine_state") in
             ("PREPARACION", "PREPARADO", "FALLA"), 20)
    print("Estado:", client.get("/status").json().get("machine_state"),
          "| periodo del lazo", ctx.control_loop.interval, "s",
          "| sondeo Modbus", ctx.serial.config.periodo_sondeo_s, "s",
          "| caché UI", UIServiceBackend._STATUS_INTERVAL, "s")

    cab = cabecera(srv, "tecnico")
    r = None
    for _ in range(60):          # tras un reinicio del módulo (ADB-04) los datos tardan
        r = client.post("/io/test/enter", headers=cab)
        if r.status_code == 200:
            break
        time.sleep(0.5)
    if r.status_code != 200:
        print("No entra al modo prueba:", r.status_code, r.text); return 2

    class _Back:
        def get_status(self):
            return client.get("/status").json()

        def get_config(self):
            return {}

        def get_cycle(self):
            return {}

    class _Sesion:
        generacion = 1

        def enviar(self, metodo, ruta, cuerpo=None):
            resp = client.request(metodo, ruta, json=cuerpo, headers=cab)
            datos = resp.json() if resp.content else {}
            if resp.status_code == 200:
                return Resultado("ok", datos, 200)
            causa = datos.get("codigo") if isinstance(datos, dict) else None
            return Resultado(causa or "error_generico", datos, resp.status_code)

        def al_cerrar_sesion(self, *_a):
            pass

        quitar_al_cerrar_sesion = al_cerrar_sesion

    cache = UIServiceBackend(_Back())
    ctrl = m.EntradasSalidasController(sesion=_Sesion(), fuente_estado=cache)
    canales = client.get("/io/channels", headers=cab).json()
    ctrl._al_canales(Resultado("ok", canales, 200))
    _esperar(lambda: (ctrl.actualizar(), ctrl.modoPrueba)[1], 5)
    candidatas = [c for c in canales["DO"] if not c.get("momentanea") and not c.get("bloqueada")]
    nombre = args.salida or next(
        (c["name"] for c in candidatas if c["name"] not in
         ("vapor_camara", "vapor_chaqueta", "aire_atmosferico_camara", "aire_admosferico_camara")
         and "puerta" not in c["name"]), candidatas[0]["name"])
    clave = io_names.clave_estado(nombre)
    canal = EstadoAutoclave.map_do[clave]
    print("Salida medida:", nombre, "DO", canal + 1)

    filas = []
    for i in range(args.n):
        valor = i % 2 == 0
        fase = random.uniform(0.0, 1.0)            # fase del Timer de 1 s de la pantalla
        t_toque = time.monotonic()
        ctrl.alternar(nombre)
        t_resp = ctrl._t_orden
        boton_ok = next(s for s in ctrl.salidas if s["name"] == nombre)["apagar"] is valor
        t_fc05 = _esperar(lambda: bool(sim.bobinas[canal]) is valor, 5)
        t_est = _esperar(lambda: ctx.estado.salidas_do.get(clave)
                         in ((1, True) if valor else (0, False)), 5)

        def reflejado():
            st, _c, _e, t_env = cache.status_vigente()
            v = ((st.get("sensors") or {}).get("digital_outputs") or {}).get(
                next(c["estado_key"] for c in canales["DO"] if c["name"] == nombre))
            return t_env is not None and t_env > t_resp and v in ((1, True) if valor else (0, False))
        t_status = _esperar(reflejado, 5)
        # pantalla de antes: Timer de 1 s con fase al azar; la primera vez que
        # un tick encuentra el /status ya reflejado
        tick = t_toque + fase
        while tick < t_status:
            tick += 1.0
        t_ui_antes = tick
        # ahora: relectura de 0,2 s mientras hay orden pendiente
        t_ui_ahora = None
        fin = time.monotonic() + 5
        while time.monotonic() < fin:
            app.processEvents()
            if not ctrl._pendientes:
                t_ui_ahora = time.monotonic(); break
            time.sleep(0.005)
        filas.append({"valor": valor, "boton": boton_ok,
                      "resp": t_resp - t_toque, "fc05": (t_fc05 or t_toque) - t_toque,
                      "estado": (t_est or t_toque) - t_toque,
                      "status": (t_status or t_toque) - t_toque,
                      "ui_antes": t_ui_antes - t_toque,
                      "ui_ahora": (t_ui_ahora or t_toque) - t_toque})
        time.sleep(random.uniform(0.3, 0.7))

    claves = ("resp", "fc05", "estado", "status", "ui_antes", "ui_ahora")
    print("\n n  orden  botón  " + "  ".join(f"{k:>8}" for k in claves) + "   (s desde el toque)")
    for i, f in enumerate(filas):
        print(f"{i:2d}  {'ON ' if f['valor'] else 'OFF'}    {'sí' if f['boton'] else 'no'}    "
              + "  ".join(f"{f[k]:8.3f}" for k in claves))
    print("\nmediana " + "  ".join(f"{k}={statistics.median(f[k] for f in filas):.3f}" for k in claves))
    print("máximo  " + "  ".join(f"{k}={max(f[k] for f in filas):.3f}" for k in claves))

    client.post("/io/test/exit", headers=cab, json={"motivo": "fin de la medición"})
    cache.stop()
    srv._detener_arranque.set()
    if ctx.control_loop is not None:
        ctx.control_loop.stop()
    if ctx.serial is not None:
        ctx.serial.stop()
    sim.detener()
    return 0


if __name__ == "__main__":
    sys.exit(main())
