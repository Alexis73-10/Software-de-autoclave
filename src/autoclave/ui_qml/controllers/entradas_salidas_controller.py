# ui_qml/controllers/entradas_salidas_controller.py
#
# OPCIONES > Entradas / Salidas (planeacion_opciones_entradas_salidas.md): una
# sola consulta a GET /status por tick (D-ES-12) compartida por los cuatro
# segmentos, modo prueba de salidas y calibracion de un sensor. No decide nada
# de seguridad: el backend es la autoridad (D-ES-07, D-ES-15, D-ES-16) y la UI
# solo refleja y muestra el motivo de un rechazo.

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.cliente.session_manager import SessionManager
from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.domain import entradas_salidas as dominio
from autoclave.ui_qml.domain import permisos_opciones as permisos

logger = logging.getLogger(__name__)

_CLAVE_CORTA_TEMP = {"temp_camara": "camara", "temp_2_camara": "camara_2",
                     "temp_ref": "ref", "temp_drenaje": "drenaje"}
_CLAVE_CORTA_PRES = {"pres_camara": "camara", "pres_chaqueta": "chaqueta",
                     "pres_empaque_1": "empaque_1", "pres_empaque_2": "empaque_2"}
_TIPO_API = {"temperatura": "temperature", "presion": "pressure"}
_SEGMENTO_DE = {v: k for k, v in _TIPO_API.items()}

_CAUSAS_SOLO_CATALOGO = frozenset({"aire_atmosferico_con_presion",
                                   "aire_atmosferico_sin_presion",
                                   "aire_atmosferico_sin_referencia",
                                   # S9 (revisión ★ SAF-01)
                                   "salida_prueba_camara_no_segura",
                                   "salida_prueba_estado_seguro"})

# D-ES-08: sin actividad del usuario en la seccion el modo prueba se cierra
INACTIVIDAD_UI_S = 5 * 60


def mensaje_de(causa: str) -> str:
    return sesion_backend.clave_mensaje(causa)


class EntradasSalidasController(QObject):
    cambioDatos = Signal()
    modoPruebaChanged = Signal()
    mensajeChanged = Signal()
    calibracionChanged = Signal()

    def __init__(self, parent=None, sesion=None):
        super().__init__(parent)
        self._sesion = sesion
        self._canales = {"DI": [], "DO": [], "temperature": [], "pressure": []}
        self._status = None
        self._entradas, self._salidas = [], []
        self._temperatura, self._presion = [], []
        self._modo_prueba = False
        self._estado_maquina = ""
        self._mensaje = ""           # clave i18n
        self._detalle = ""           # texto del backend, si lo hay
        self._calibracion = {}

    def _s(self):
        return self._sesion or sesion_backend.ventana()

    @staticmethod
    def _rol() -> str:
        return (SessionManager.current_user() or {}).get("rol") or ""

    # -- mensajes -------------------------------------------------------

    def _fallo(self, r) -> None:
        self._mensaje = mensaje_de(r.causa)
        d = r.datos if isinstance(r.datos, dict) else {}
        # D8-3.19: estos motivos ya tienen su texto completo en el catálogo; el
        # del backend (en español) no se agrega
        self._detalle = ("" if r.causa in _CAUSAS_SOLO_CATALOGO
                         else str(d.get("detail") or ""))
        self.mensajeChanged.emit()

    def _limpiar_mensaje(self) -> None:
        if self._mensaje or self._detalle:
            self._mensaje, self._detalle = "", ""
            self.mensajeChanged.emit()

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    @Property(str, notify=mensajeChanged)
    def detalle(self) -> str:
        return self._detalle

    @Slot()
    def limpiarMensaje(self) -> None:
        self._limpiar_mensaje()

    # -- lectura en vivo ------------------------------------------------

    @Slot()
    def cargarCanales(self) -> None:
        r = self._s().enviar("GET", "/io/channels")
        if r.ok:
            self._canales = {k: list(r.datos.get(k) or []) for k in self._canales}
            self._limpiar_mensaje()
        else:
            self._fallo(r)
        self._reconstruir()

    @Slot()
    def actualizar(self) -> None:
        """Un tick de 1 s. Sin respuesta, todo pasa a "Sin datos"."""
        r = self._s().enviar("GET", "/status")
        self._status = r.datos if r.ok else None
        if self._status is not None:
            self._estado_maquina = str(self._status.get("machine_state") or "")
            activo = bool(self._status.get("test_mode_active"))
            if activo != self._modo_prueba:
                self._modo_prueba = activo
                self.modoPruebaChanged.emit()
        self._reconstruir()

    def _reconstruir(self) -> None:
        c, st = self._canales, self._status
        self._entradas = dominio.presentar_entradas(c["DI"], st)
        self._salidas = dominio.presentar_salidas(c["DO"], st)
        self._temperatura = dominio.presentar_sensores(c["temperature"], "temperature", st,
                                                       _CLAVE_CORTA_TEMP)
        self._presion = dominio.presentar_sensores(c["pressure"], "pressure", st,
                                                   _CLAVE_CORTA_PRES)
        self.cambioDatos.emit()

    @Property("QVariantList", notify=cambioDatos)
    def entradas(self) -> list:
        return self._entradas

    @Property("QVariantList", notify=cambioDatos)
    def salidas(self) -> list:
        return self._salidas

    @Property("QVariantList", notify=cambioDatos)
    def temperatura(self) -> list:
        return self._temperatura

    @Property("QVariantList", notify=cambioDatos)
    def presion(self) -> list:
        return self._presion

    @Property(bool, notify=cambioDatos)
    def enlace(self) -> bool:
        return dominio.enlace_ok(self._status)

    @Property(str, notify=cambioDatos)
    def estadoMaquina(self) -> str:
        return self._estado_maquina

    # -- permisos (reflejan al backend) ---------------------------------

    @Property(bool, notify=cambioDatos)
    def puedeProbar(self) -> bool:
        return permisos.puede_modo_prueba(self._rol(), self._estado_maquina)

    @Property(bool, notify=cambioDatos)
    def puedeCalibrar(self) -> bool:
        return permisos.puede_calibrar(self._rol(), self._estado_maquina)

    # -- modo prueba ----------------------------------------------------

    @Property(bool, notify=modoPruebaChanged)
    def modoPrueba(self) -> bool:
        return self._modo_prueba

    @Slot(result=bool)
    def entrarModoPrueba(self) -> bool:
        r = self._s().enviar("POST", "/io/test/enter")
        if not r.ok:
            self._fallo(r)
            return False
        self._limpiar_mensaje()
        self._modo_prueba = True
        self._avisar_cierre(True)
        self.modoPruebaChanged.emit()
        return True

    def _al_cerrar_sesion(self) -> None:
        """Corre antes del logout. Sea cual sea la respuesta, la sesión muere:
        el estado local queda limpio y, si la salida no se confirmó, la cierra
        el backend al invalidarse la sesión dueña (SAF-01)."""
        s = self._s()
        enviar = getattr(s, "enviar_al_cerrar", s.enviar)
        if self._modo_prueba:
            r = enviar("POST", "/io/test/exit", {"motivo": "cierre de sesión"})
            if not (r.ok or r.causa == "modo_prueba_inactivo"):
                logger.warning("Salida del modo prueba al cerrar sesión sin confirmar (%s)", r.causa)
        self._modo_prueba = False
        self._avisar_cierre(False)
        self.modoPruebaChanged.emit()

    def _avisar_cierre(self, activo: bool) -> None:
        """P1: con el modo prueba activo, el cierre de sesión sale primero."""
        s = self._s()
        metodo = getattr(s, "al_cerrar_sesion" if activo else "quitar_al_cerrar_sesion", None)
        if metodo is not None:
            metodo(self._al_cerrar_sesion)

    @Slot(str, result=bool)
    def salirModoPrueba(self, causa: str = "salida solicitada") -> bool:
        if not self._modo_prueba:
            return True
        r = self._s().enviar("POST", "/io/test/exit", {"motivo": causa})
        # sesion_invalida: el backend ya lo cierra por la sesión dueña (SAF-01)
        if r.ok or r.causa in ("modo_prueba_inactivo", "sesion_invalida"):
            self._modo_prueba = False
            self._avisar_cierre(False)
            self.modoPruebaChanged.emit()
            self._limpiar_mensaje()
            return True
        self._fallo(r)
        return False

    @Slot()
    def keepalive(self) -> None:
        if self._modo_prueba:
            r = self._s().enviar("POST", "/io/test/keepalive")
            if not r.ok:
                self._fallo(r)

    @Slot(str, bool, bool, result=bool)
    def accionar(self, nombre: str, encender: bool, momentanea: bool) -> bool:
        """Enciende o apaga una salida. Si el backend rechaza, se muestra su
        motivo; el estado real lo corrige el siguiente tick."""
        cuerpo = {"value": bool(encender)}
        if momentanea and encender:
            cuerpo["momentanea"] = True
        r = self._s().enviar("PATCH", f"/io/test/output/{nombre}", cuerpo)
        if not r.ok:
            self._fallo(r)
            return False
        self._limpiar_mensaje()
        return True

    # -- calibracion de un sensor ---------------------------------------

    @Slot(str, str, result=bool)
    def cargarCalibracion(self, segmento: str, sensor: str) -> bool:
        tipo = _TIPO_API.get(segmento)
        if tipo is None:
            return False
        r = self._s().enviar("GET", f"/calibration/{tipo}/{sensor}")
        if not r.ok:
            self._fallo(r)
            return False
        d = r.datos
        self._calibracion = {"tipo": tipo, "sensor": sensor, "gain": d.get("gain"),
                             "offset": d.get("offset"), "poly": bool(d.get("is_poly")),
                             "ultimo": d.get("last_change")}
        self.calibracionChanged.emit()
        return True

    @Property("QVariantMap", notify=calibracionChanged)
    def calibracion(self) -> dict:
        return self._calibracion

    @Slot(float, float, float, float, result="QVariantMap")
    def calcular(self, lectura_baja: float, real_bajo: float,
                 lectura_alta: float, real_alto: float) -> dict:
        """Ganancia y offset resultantes, con la misma formula del backend."""
        c = self._calibracion
        try:
            g, o = dominio.calcular_calibracion(
                lectura_baja, real_bajo, lectura_alta, real_alto,
                c.get("gain", 1.0), c.get("offset", 0.0))
        except (ValueError, TypeError):
            return {"valido": False}
        return {"valido": True, "gain": g, "offset": o}

    @Slot(float, float, float, float, str, str, bool, result=bool)
    def aplicarPuntos(self, lectura_baja: float, real_bajo: float,
                      lectura_alta: float, real_alto: float,
                      origen_bajo: str, origen_alto: str, confirmar: bool) -> bool:
        c = self._calibracion
        cuerpo = {"shown_low": lectura_baja, "real_low": real_bajo,
                  "shown_high": lectura_alta, "real_high": real_alto,
                  "origen_lectura": {"bajo": origen_bajo, "alto": origen_alto}}
        if confirmar:
            cuerpo["confirmar_fuera_de_rango"] = True
        r = self._s().enviar("PATCH", f"/calibration/{c.get('tipo')}/{c.get('sensor')}", cuerpo)
        return self._resultado_calibracion(r)

    @Slot(str, result=bool)
    def restaurar(self, destino: str) -> bool:
        c = self._calibracion
        r = self._s().enviar("POST", f"/calibration/{c.get('tipo')}/{c.get('sensor')}/restaurar",
                             {"destino": destino})
        return self._resultado_calibracion(r)

    def _resultado_calibracion(self, r) -> bool:
        if r.ok:
            self._limpiar_mensaje()
            self.cargarCalibracion(_SEGMENTO_DE.get(self._calibracion.get("tipo"), ""),
                                   self._calibracion.get("sensor", ""))
            return True
        self._fallo(r)
        return False

    @Property(bool, notify=mensajeChanged)
    def requiereConfirmacion(self) -> bool:
        return self._mensaje == "io.err_confirmacion"


qmlRegisterType(EntradasSalidasController, "Autoclave.Controllers", 1, 0,
                "EntradasSalidasController")
