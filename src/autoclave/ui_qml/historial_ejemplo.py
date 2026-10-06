# ui_qml/historial_ejemplo.py
#
# PRUEBA: backend simulado del Historial para el arnés del Menú Principal
# (prueba_menu_principal.py --pantalla, sin --backend). DATOS DE EJEMPLO, no son
# ciclos reales: responde a /cycle/list (por periodo de calendario), a la curva y
# al ticket de cada ciclo, y acepta /cycle/history/print sin imprimir nada (pero
# con el estado real de la impresora, para ver el aviso si no está lista). Con
# él el arnés usa los puentes reales CiclosHistorial y AccionesCiclos.

import logging
import time
from datetime import date, datetime, timedelta

import requests

from autoclave.core.runtime import progreso_ciclo
from autoclave.services.domain.reportes import resumen_periodo
from autoclave.utils import periodos

logger = logging.getLogger(__name__)

_PROGRAMAS = (("instrumental_134", "Instrumental 134", 2), ("bowie_dick", "Bowie & Dick", 1),
              ("instrumental_121", "Instrumental 121", 3))
_RESULTADOS = ("COMPLETADO", "COMPLETADO", "COMPLETADO", "FALLO_SECADO", "CANCELADO")
# tramos (min, temp cámara, temp ref, presión kPa) de un ciclo de 40 min
_TRAMOS = ((0, 44, 40, 30), (5, 85, 70, 45), (9, 117, 105, 120), (15, 134, 133, 304),
           (19, 134, 134, 306), (20, 110, 112, 150), (22, 100, 104, 30), (37, 95, 98, 20),
           (40, 60, 70, 101))
_FASES = ((0, "PRECALENTAMIENTO"), (2, "PRE_VACIO"), (9, "CALENTAMIENTO"),
          (15, "ESTERILIZACION"), (19, "DESCOMPRESION"), (22, "SECADO"))


def _interpolar(t: float, k: int) -> float:
    for a, b in zip(_TRAMOS, _TRAMOS[1:]):
        if t <= b[0]:
            return a[k] + (b[k] - a[k]) * (t - a[0]) / (b[0] - a[0])
    return _TRAMOS[-1][k]


def _fase(t: float) -> str:
    return [f for inicio, f in _FASES if t >= inicio][-1]


class BackendEjemplo:
    """Misma interfaz get/post que BackendClient."""

    def __init__(self, sin_conexion: bool = False, hoy=date.today):
        self.sin_conexion = sin_conexion
        self._hoy = hoy

    def _ciclos_del_dia(self, d: date) -> list[dict]:
        n = d.toordinal()
        ciclos = []
        for i in range(n % 4):                       # 0 a 3 ciclos por día
            numero = (n - 739000) * 3 + i
            programa = _PROGRAMAS[(n + i) % 3]
            inicio = datetime.combine(d, datetime.min.time()) + timedelta(hours=7 + 3 * i, minutes=5 * i)
            resultado = _RESULTADOS[(n + i) % len(_RESULTADOS)]
            ciclos.append({"id": numero, "numero_ciclo": numero,
                           "fecha_inicio": inicio.isoformat(),
                           "fecha_fin": (inicio + timedelta(minutes=40)).isoformat(),
                           "programa_id": programa[0], "programa_nombre": programa[1],
                           "programa_numero": programa[2], "resultado": resultado, "operador": None})
        return ciclos

    def _ciclo(self, ciclo_id: int) -> dict:
        d = date.fromordinal(739000 + ciclo_id // 3)
        return next(c for c in self._ciclos_del_dia(d) if c["id"] == ciclo_id)

    def get(self, ruta: str, params=None, **_):
        if self.sin_conexion:
            raise requests.ConnectionError("backend de ejemplo sin conexión")
        if ruta == "/cycle/list":
            fecha = date.fromisoformat(params["fecha"]) if params.get("fecha") else self._hoy()
            inicio, fin = periodos.rango(params["periodo"], fecha)
            ciclos, d = [], inicio
            while d < fin and d <= self._hoy():
                ciclos.extend(self._ciclos_del_dia(d))
                d += timedelta(days=1)
            return {"periodo": params["periodo"], "ciclos": ciclos[::-1], "truncado": False}
        if ruta == "/report/summary":
            return self._resumen(params)
        ciclo_id = int(ruta.split("/")[3])
        if ruta.endswith("/graph"):
            return {"ciclo_db_id": ciclo_id, "lecturas": [
                {"id": s, "t_s": float(s * 6), "fase": _fase(s / 10),
                 "fase_ui": progreso_ciclo.fase_ui(_fase(s / 10)), "temp_camara": _interpolar(s / 10, 1),
                 "temp_ref": _interpolar(s / 10, 2), "pres_camara": _interpolar(s / 10, 3)}
                for s in range(401)]}
        if ruta.endswith("/ticket"):
            c = self._ciclo(ciclo_id)
            ciclo = {"id": ciclo_id, "numero_ciclo": c["numero_ciclo"], "serie": "EJEMPLO-001",
                     "modelo": "SPK-AVH-450", "version_sw": "1.0", "nombre_ciclo": c["programa_nombre"],
                     "tipo_ciclo": c["programa_id"], "temp_esterilizacion": 134,
                     "tiempo_esterilizacion": 4, "fecha_inicio": c["fecha_inicio"],
                     "fecha_fin": c["fecha_fin"], "resultado": c["resultado"], "motivo_fallo": None}
            lecturas = [{"fase_codigo": _fase(m)[0], "timestamp_rel": f"00:{m:02d}:00",
                         "temp_camara": _interpolar(m, 1), "pres_camara": _interpolar(m, 3)}
                        for m in range(0, 41, 2)]
            return {"ciclo": ciclo, "lecturas": lecturas}
        raise requests.HTTPError(response=type("R", (), {"status_code": 404})())

    def _resumen(self, params) -> dict:
        """Resumen calculado sobre los mismos ciclos de ejemplo del listado."""
        fecha = date.fromisoformat(params["fecha"]) if params.get("fecha") else self._hoy()
        inicio, fin = periodos.rango(params["periodo"], fecha)
        filas, d = [], inicio
        while d < fin and d <= self._hoy():
            filas += [{"tipo_ciclo": c["programa_id"], "nombre_ciclo": c["programa_nombre"],
                       "resultado": c["resultado"], "cantidad": 1} for c in self._ciclos_del_dia(d)]
            d += timedelta(days=1)
        numeros = {p[0]: p[2] for p in _PROGRAMAS}
        return {"periodo": params["periodo"], "desde": inicio.isoformat(),
                "hasta": (fin - timedelta(days=1)).isoformat(), "serie": "EJEMPLO-001",
                "modelo": "SPK-AVH-450", **resumen_periodo.resumir(filas, numeros)}

    def post(self, ruta: str, body=None, **_):
        if self.sin_conexion:
            raise requests.ConnectionError("backend de ejemplo sin conexión")
        if ruta in ("/cycle/history/print", "/report/summary/print"):
            time.sleep(0.8)
            # estado REAL de la impresora (como el backend), aunque no se imprime nada
            from autoclave.devices.printer.win32_printer import estado_impresora
            estado = estado_impresora()
            if estado != "lista":
                respuesta = type("R", (), {"status_code": 503,
                                           "json": lambda self: {"detail": {"impresora": estado}}})()
                raise requests.HTTPError(response=respuesta)
            logger.info("EJEMPLO: se imprimiría %s %s", ruta, body)
            return {"ok": True, "impresos": len(body.get("ids", []))}
        raise requests.HTTPError(response=type("R", (), {"status_code": 404})())


def config_correo_ejemplo():
    """Destinos de config/correo.json con un remitente ficticio, para ver el
    flujo de envío completo en el arnés sin configurar el correo real."""
    from autoclave.ui_qml.exportacion import config_correo
    config = config_correo.cargar(contrasena=lambda remitente: None)
    config.remitente = config.remitente or "equipo.ejemplo@example.com"
    config.contrasena = "ejemplo"
    return config


def enviar_ejemplo(config, mensaje) -> None:
    """No envía nada: deja el correo armado en el registro (arnés sin --backend)."""
    time.sleep(1.5)
    adjuntos = [a.get_filename() for a in mensaje.iter_attachments()]
    logger.info("EJEMPLO: correo a %s con %s (no se envió)", mensaje["To"], adjuntos)
