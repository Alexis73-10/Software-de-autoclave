# tests/helpers/reportes_ejemplo.py
#
# Cliente de ejemplo para el dashboard de Reportes (etapa E): un backend REAL
# (las rutas /report/dashboard, /calendar, /day-cycles y /failures) sobre una
# base temporal sembrada con ~124 ciclos de octubre de 2026, parecidos a los del
# mockup, con la misma interfaz get/post de BackendClient. Lo usan el arnés de
# capturas (tests/banco/rep_capturas_reportes.py) y las pruebas QML de la
# pantalla. No son lecturas reales de ningún equipo.
#
# Días notables de octubre (hoy = sábado 31):
#   8   Bowie & Dick con fallo previo (FALLO y luego COMPLETADO)  -> exito_fallo_previo
#   14  sin Bowie & Dick pero con otros ciclos                    -> falto
#   21  Bowie & Dick solo con fallos                              -> sin_exito
#   sábados y domingos sin ciclos                                 -> sin_operacion

import json
import sys
from contextlib import ExitStack
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from autoclave.services.domain.logging.db_manager import DbManager
from tests.helpers.backend_doble import cargar_servidor, parche_en_backend

HOY = date(2026, 10, 31)

# (id de programa, nombre, número)
PROGRAMAS = (("bd", "Bowie & Dick", 1), ("inst", "Instrumental 134", 2),
             ("tex", "Textiles 134", 3), ("liq", "Líquidos 121", 4))
_OPERADORES = ("ana", "luis", "marta", "")
_FALLOS = ("FALLO_ESTERILIZACION", "FALLO_CALENTAMIENTO", "FALLO_SECADO", "FALLO_ESTERILIZACION")


def _nuevo_ciclo(db, programa, inicio: datetime, minutos: int, resultado, operador=""):
    pid, nombre, numero = programa
    cid = db.crear_ciclo(numero=db.siguiente_numero_ciclo(), tipo=pid, nombre=nombre, temp_ester=134,
                         tiempo_ester=4, modelo="SPK-AVH-450", serie="EJEMPLO-001", version_sw="1.0",
                         operador=operador)
    fin = (inicio + timedelta(minutes=minutos)).isoformat() if resultado else None
    with db._lock:
        db._conn.execute("UPDATE ciclos SET fecha_inicio=?, fecha_fin=?, resultado=?, numero_programa=?"
                         " WHERE id=?", (inicio.isoformat(), fin, resultado, numero, cid))
        db._conn.commit()
    return cid


def _alarma(db, codigo, nivel, titulo, aparecida: datetime):
    with db._lock:
        db._conn.execute("INSERT INTO alarmas_historial (codigo, nivel, titulo, descripcion_inicial, aparecida)"
                         " VALUES (?, ?, ?, '', ?)", (codigo, nivel, titulo, aparecida.isoformat()))
        db._conn.commit()


def sembrar(db) -> int:
    """~124 ciclos de octubre de 2026 (más los de septiembre). Devuelve cuántos sembró."""
    n = 0
    k_otros = 0
    bd, otros = PROGRAMAS[0], PROGRAMAS[1:]
    for dia in range(1, 31):
        d = date(2026, 10, dia)
        if d.weekday() >= 5:
            continue
        base = datetime(2026, 10, dia, 6, 30)
        if dia == 8:
            _nuevo_ciclo(db, bd, base, 35, "FALLO_ESTERILIZACION", "ana")
            _nuevo_ciclo(db, bd, base + timedelta(minutes=55), 35, "COMPLETADO", "ana")
            n += 2
        elif dia == 14:
            pass
        elif dia == 21:
            _nuevo_ciclo(db, bd, base, 20, "FALLO_CALENTAMIENTO", "luis")
            _nuevo_ciclo(db, bd, base + timedelta(minutes=45), 35, "FALLO_ESTERILIZACION", "luis")
            n += 2
        else:
            _nuevo_ciclo(db, bd, base, 35, "COMPLETADO", _OPERADORES[dia % 3])
            n += 1
        for i in range(5 if dia % 5 < 3 else 4):
            k_otros += 1
            ini = datetime(2026, 10, dia, 8, 0) + timedelta(minutes=80 * i)
            if k_otros % 11 == 0:
                res, dur = _FALLOS[k_otros % 4], 18
            elif k_otros % 23 == 0:
                res, dur = "CANCELADO", 6
            else:
                res, dur = "COMPLETADO", 40 + 5 * (k_otros % 4)
            _nuevo_ciclo(db, otros[(dia + i) % 3], ini, dur, res, _OPERADORES[(dia + i) % 4])
            n += 1
    # septiembre, para que haya periodo anterior con el que comparar
    for dia in range(1, 31):
        d = date(2026, 9, dia)
        if d.weekday() >= 5:
            continue
        _nuevo_ciclo(db, bd, datetime(2026, 9, dia, 6, 30), 35, "COMPLETADO", _OPERADORES[dia % 3])
        n += 1
        for i in range(3):
            k_otros += 1
            res = _FALLOS[k_otros % 4] if k_otros % 9 == 0 else "COMPLETADO"
            _nuevo_ciclo(db, otros[(dia + i) % 3], datetime(2026, 9, dia, 8, 0) + timedelta(minutes=90 * i),
                         18 if res != "COMPLETADO" else 38, res, _OPERADORES[(dia + i) % 4])
            n += 1
    for dia, codigo, nivel, titulo in ((2, "SIS-01", "FALLO_CRITICO", "x"), (8, "SIS-01", "FALLO_CRITICO", "x"),
                                        (9, "SEN-02", "ALARMA", "x"), (12, "SUM-02", "AVISO", "x"),
                                        (12, "SUM-02", "AVISO", "x"), (15, "SIS-02", "AVISO", "x"),
                                        (21, "SEN-04", "ALARMA", "x"), (21, "XYZ-9", "INFORMATIVO", "Aviso guardado"),
                                        (23, "SEN-05", "ALARMA", "x"), (24, "SEN-06", "ALARMA", "x"),
                                        (26, "SUM-01", "FALLO_CRITICO", "x"), (27, "SEN-07", "AVISO", "x")):
        _alarma(db, codigo, nivel, titulo, datetime(2026, 10, dia, 9, 15))
    return n


class ClienteReportes:
    """Con `with ClienteReportes(tmp) as c:` hay un cliente con get/post como BackendClient."""

    def __init__(self, carpeta, hoy: date = HOY, sin_conexion: bool = False):
        self._carpeta = carpeta
        self.hoy = hoy
        self.sin_conexion = sin_conexion
        self.llamadas: list = []
        self.escrituras: list = []
        self.ciclos_sembrados = 0

    def __enter__(self):
        self._pila = ExitStack()
        self.db = DbManager(self._carpeta / "reportes_ejemplo.db")
        self._pila.callback(self.db.close)
        self.ciclos_sembrados = sembrar(self.db)
        ctx = MagicMock()
        ctx.db = self.db
        ctx.cycle_manager.cycles = {pid: SimpleNamespace(number=num, name=nombre)
                                    for pid, nombre, num in PROGRAMAS}
        srv, _ = cargar_servidor(ctx)
        from fastapi.testclient import TestClient
        self._pila.enter_context(parche_en_backend(
            "_inicio_del_dia", MagicMock(return_value=datetime.combine(self.hoy, datetime.min.time()).isoformat())))
        self._pila.enter_context(parche_en_backend("_ciclo_de_pantalla", lambda: None))
        self._http = TestClient(srv.app)
        return self

    def __exit__(self, *exc):
        self._pila.close()

    # ── interfaz de BackendClient ────────────────────────────────────────
    def get(self, ruta, params=None, **_):
        self.llamadas.append(("GET", ruta, dict(params or {})))
        if self.sin_conexion:
            raise requests.ConnectionError("backend de ejemplo sin conexión")
        if ruta == "/maintenance":
            return {"estado": "proximo", "ciclos_restantes": 24, "ultimo_fecha": "2026-06-15",
                    "ultimo_tipo": "preventivo", "configuracion": {"intervalo_dias": 180, "intervalo_ciclos": 600}}
        if ruta == "/maintenance/records":
            return {"registros": [
                {"fecha": "2026-10-09", "usuario": "tecnico1", "tipo": "correctivo", "observaciones": "Cambio de empaque"},
                {"fecha": "2026-10-20", "usuario": "tecnico1", "tipo": "correctivo",
                 "observaciones": "Se anota repuesto: sello de puerta"},
                {"fecha": "2026-06-15", "usuario": "tecnico1", "tipo": "preventivo", "observaciones": ""}]}
        if ruta.startswith("/cycle/history/") and ruta.endswith("/graph"):
            from autoclave.ui_qml.historial_ejemplo import BackendEjemplo
            return BackendEjemplo(hoy=lambda: self.hoy).get(ruta, params)
        r = self._http.get(ruta, params=params)
        if r.status_code != 200:
            raise requests.HTTPError(response=r)
        return r.json()

    def post(self, ruta, body=None, **_):
        """Escribir no está permitido en el arnés: se registra para que la prueba lo vea."""
        self.escrituras.append((ruta, body))
        if ruta in ("/cycle/history/print", "/report/summary/print"):
            return {"ok": True, "impresos": len((body or {}).get("ids", []))}
        raise requests.HTTPError(response=type("R", (), {"status_code": 404})())
