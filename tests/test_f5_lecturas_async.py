# tests/test_f5_lecturas_async.py
#
# AJUSTES 2026-11-02, paso 2 fase 5: lecturas GET restantes sin HTTP sincrono
# en la GUI (Bitacora, Fecha y hora, Informacion del sistema, Respaldo y la
# lectura de Reasignacion). Con `cargando`, solo manda la ultima consulta y un
# error conserva el ultimo dato. Doble de sesion con entrega controlada.

import sys

import pytest
from PySide6.QtCore import QCoreApplication

from autoclave.ui_qml import sesion_backend
from autoclave.ui_qml.sesion_backend import Resultado


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class SesionManual:
    """Guarda los envios asincronos; el test decide cuando y en que orden
    se entregan. `enviar` (sincrono) lleva la cuenta para vigilar su uso."""

    def __init__(self):
        self.vuelo = []
        self.sincronos = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.sincronos.append((metodo, ruta))
        return Resultado("ok", {})

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None, al_tardio=None):
        self.vuelo.append((metodo, ruta, cuerpo, al_terminar))
        return True

    def cancelar_envios(self, dueno):
        return 0

    def entregar(self, i, causa="ok", datos=None):
        self.vuelo[i][3](Resultado(causa, datos or {}))


class SoloEnviar:
    def __init__(self, r):
        self.r = r

    def enviar(self, metodo, ruta, cuerpo=None):
        return self.r


def _bit(sesion):
    from autoclave.ui_qml.controllers.bitacora_controller import BitacoraController
    return BitacoraController(sesion=sesion)


def _datos(fila_id, **extra):
    return {"filas": [{"id": fila_id, "ts": "2026-11-02T10:00:00"}], "total": 1, "pagina": 1,
            "paginas": 1, "usuarios": ["ana"], **extra}


# -- Bitacora -----------------------------------------------------------

def test_bitacora_carga_asincrona_con_cargando():
    s = SesionManual()
    c = _bit(s)
    c.cargar()
    assert c.cargando and s.sincronos == []
    s.entregar(0, datos=_datos(7))
    assert not c.cargando and c.filas[0]["id"] == 7


def test_bitacora_filtros_encadenados_solo_manda_la_ultima():
    s = SesionManual()
    c = _bit(s)
    c.fijarUsuario("ana")
    c.fijarCategoria("usuarios_sesion")
    c.fijarUsuario("")
    assert len(s.vuelo) == 3
    s.entregar(2, datos=_datos(3))          # llega primero la ultima
    assert c.filas[0]["id"] == 3 and not c.cargando
    s.entregar(0, datos=_datos(1))          # las viejas ya no pisan
    s.entregar(1, datos=_datos(2))
    assert c.filas[0]["id"] == 3


def test_bitacora_vieja_no_apaga_cargando_de_la_nueva():
    s = SesionManual()
    c = _bit(s)
    c.fijarUsuario("ana")
    c.fijarUsuario("tomas")
    s.entregar(0, datos=_datos(1))
    assert c.cargando and c.filas == []
    s.entregar(1, datos=_datos(2))
    assert not c.cargando and c.filas[0]["id"] == 2


def test_bitacora_error_conserva_ultimo_dato():
    s = SesionManual()
    c = _bit(s)
    c.cargar()
    s.entregar(0, datos=_datos(5))
    c.cargar()
    s.entregar(1, causa=sesion_backend.BACKEND_NO_RESPONDE)
    assert c.filas[0]["id"] == 5 and c.mensaje == "opciones.err_sin_respuesta" and not c.cargando


def test_bitacora_doble_solo_enviar_entrega_en_el_acto():
    c = _bit(SoloEnviar(Resultado("ok", _datos(9))))
    c.cargar()
    assert c.filas[0]["id"] == 9 and not c.cargando


# -- Fecha y hora -------------------------------------------------------

def test_fecha_hora_async_obsoleta_y_error():
    from autoclave.ui_qml.controllers.fecha_hora_controller import FechaHoraController
    s = SesionManual()
    c = FechaHoraController(sesion=s)
    c._timer.stop()
    c.cargar()
    c.cargar()
    assert c.cargando
    s.entregar(1, datos={"instalacion": "2026-10-01T00:00:00", "zona": "UTC-05:00"})
    assert not c.cargando and c.instalacion.startswith("2026-10-01")
    s.entregar(0, datos={"instalacion": "1999-01-01T00:00:00"})
    assert c.instalacion.startswith("2026-10-01")
    c.cargar()
    s.entregar(2, causa=sesion_backend.BACKEND_NO_RESPONDE)
    assert c.instalacion.startswith("2026-10-01") and c.mensaje == "opciones.err_sin_respuesta"


# -- Informacion del sistema --------------------------------------------

def test_info_sistema_async_conserva_en_error():
    from autoclave.ui_qml.controllers.info_sistema_controller import InfoSistemaController
    s = SesionManual()
    c = InfoSistemaController(sesion=s)
    c.cargar()
    assert c.cargando
    s.entregar(0, datos={"equipo": {"modelo": "AC-1"}})
    assert c.grupos[0]["filas"][0]["valor"] == "AC-1" and not c.cargando
    c.cargar()
    s.entregar(1, causa="error_generico")
    assert c.grupos[0]["filas"][0]["valor"] == "AC-1" and c.mensaje == "opciones.err_generico"


# -- Respaldo -----------------------------------------------------------

def _resp(sesion):
    from autoclave.ui_qml.controllers.respaldo_controller import RespaldoController
    return RespaldoController(sesion=sesion)


_USB = {"unidades": [{"ruta": "E:/", "libre_bytes": 2e9, "respaldos": []}], "serie": "S1"}


def test_respaldo_lectura_async_y_error_conserva():
    s = SesionManual()
    c = _resp(s)
    c.cargar()
    assert c.cargando
    s.entregar(0, datos=_USB)
    assert c.unidad == "E:/" and not c.cargando
    c.cargar()
    s.entregar(1, causa=sesion_backend.BACKEND_NO_RESPONDE)
    assert c.unidad == "E:/" and c.mensaje == "opciones.err_sin_respuesta"


def test_respaldo_lectura_obsoleta_descartada():
    s = SesionManual()
    c = _resp(s)
    c.cargar()
    c.cargar()
    s.entregar(1, datos=_USB)
    s.entregar(0, datos={"unidades": []})
    assert c.unidad == "E:/"


def test_respaldo_exportar_asincrono_guardando():
    s = SesionManual()
    c = _resp(s)
    c.cargar()
    s.entregar(0, datos=_USB)
    assert c.exportar() is True
    assert c.guardando and s.vuelo[-1][1] == "/backup/export"
    assert c.exportar() is False                   # no se apila
    s.entregar(len(s.vuelo) - 1)
    assert not c.guardando and c.mensaje == "respaldo.exportado"
    assert s.vuelo[-1][1] == "/backup/usb"         # relee la lista


def test_respaldo_exportar_error_y_doble_sincrono():
    s = SesionManual()
    c = _resp(s)
    c.cargar()
    s.entregar(0, datos=_USB)
    c.exportar()
    s.entregar(1, causa="usb_no_escribible")
    assert not c.guardando and c.mensaje == "respaldo.err_usb_escritura"
    d = _resp(SoloEnviar(Resultado("usb_no_escribible", {})))
    d._d = _USB
    assert d.exportar() is False


def test_respaldo_restaurar_sigue_sincrono():
    s = SesionManual()
    c = _resp(s)
    c.cargar()
    s.entregar(0, datos={"unidades": [{"ruta": "E:/", "respaldos": [{"archivo": "a", "valido": True}]}]})
    c.seleccionar("a")
    assert c.restaurar() is True
    assert ("POST", "/backup/restore") in s.sincronos


# -- Reasignacion (solo el GET) -----------------------------------------

def test_reasignacion_cargar_async_obsoleta_y_aplicar_sigue_sincrono():
    from autoclave.ui_qml.controllers.reasignacion_controller import ReasignacionController
    s = SesionManual()
    c = ReasignacionController(sesion=s)
    c.cargar()
    c.cargar()
    assert c.cargando
    s.entregar(1, datos={"filas": [], "editable": True})
    assert c.cargado and not c.cargando
    s.entregar(0, causa="error_generico")
    assert c.cargado                               # la vieja no borra lo nuevo
    c._pendientes = {"f": 3}
    c.aplicar("clave")
    assert ("POST", "/io/assignment") in s.sincronos


def test_reasignacion_lectura_previa_a_escritura_no_pisa():
    from autoclave.ui_qml.controllers.reasignacion_controller import ReasignacionController
    s = SesionManual()
    c = ReasignacionController(sesion=s)
    c.cargar()                                     # en vuelo
    c._pendientes = {"f": 3}
    c.aplicar("clave")                             # escritura sincrona
    assert not c.cargando
    s.entregar(0, datos={"filas": [], "editable": True})
    assert not c.cargado                           # la lectura anterior a la escritura se descarta
