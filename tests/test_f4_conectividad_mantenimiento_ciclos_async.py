# tests/test_f4_conectividad_mantenimiento_ciclos_async.py
#
# AJUSTES 2026-11-02, paso 2 fase 4: Conectividad, Mantenimiento y Manejo de
# ciclos sin HTTP sincrono en la GUI. Optimista con reversion (correo,
# intervalos, habilitar programa), asincronos con «guardando» (correo de
# prueba, registrar mantenimiento) y GET con `cargando`. Doble de sesion con
# entrega controlada.

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from autoclave.ui_qml.sesion_backend import BACKEND_NO_RESPONDE, Resultado

QML = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "ui_qml" / "qml" / "Pantallas"


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class SesionManual:
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
        self.vuelo[i][3](Resultado(causa, datos if datos is not None else {}))

    def rutas(self):
        return [(m, r) for m, r, _, _ in self.vuelo]

    def ultimo(self, metodo, ruta):
        return max(i for i, (m, r, _, _) in enumerate(self.vuelo) if (m, r) == (metodo, ruta))


class SoloEnviar:
    """Doble antiguo: solo `enviar`; la entrega es en el acto."""

    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.enviados = []

    def enviar(self, metodo, ruta, cuerpo=None):
        self.enviados.append((metodo, ruta, cuerpo))
        return self.respuestas.get((metodo, ruta)) or Resultado("error_generico")


# ── Conectividad ────────────────────────────────────────────────────────────

CORREO = {"envio_activo": True, "destinatarios": [{"nombre": "A", "correo": "a@x.co"},
                                                   {"nombre": "B", "correo": "b@x.co"}],
          "remitente": "e@x.co", "servidor": "smtp.x.co", "puerto": 587,
          "contrasena_configurada": True, "max_destinatarios": 10}


def _conn(sesion):
    from autoclave.ui_qml.controllers.conectividad_controller import ConectividadController
    return ConectividadController(sesion=sesion)


def _conn_cargado(s):
    c = _conn(s)
    c.cargar()
    assert c.cargando and s.rutas() == [("GET", "/network/status"), ("GET", "/email/config")]
    s.entregar(0, datos={"adaptadores": [], "conectado": True})
    assert c.cargando                      # falta el correo
    s.entregar(1, datos=CORREO)
    assert not c.cargando and c.envioActivo and len(c.destinatarios) == 2
    return c


def test_conectividad_quitar_es_optimista_y_se_confirma():
    s = SesionManual()
    c = _conn_cargado(s)
    assert c.quitar(1) is True                                  # en vuelo = aceptado
    assert len(c.destinatarios) == 1 and c.pendientes.get("email") == "enviando"
    i = s.ultimo("PUT", "/email/config")
    assert s.vuelo[i][2] == {"envio_activo": True, "destinatarios": CORREO["destinatarios"][:1]}
    vistos = []
    c.cambioResuelto.connect(lambda *a: vistos.append(a))
    s.entregar(i, datos=dict(CORREO, destinatarios=CORREO["destinatarios"][:1]))
    assert vistos == [("email", True, "")]
    assert len(c.destinatarios) == 1 and "email" not in c.pendientes and c.mensaje == ""
    assert s.sincronos == []


def test_conectividad_rechazo_revierte_con_motivo():
    s = SesionManual()
    c = _conn_cargado(s)
    assert c.fijarEnvio(False) is True
    assert c.envioActivo is False
    vistos = []
    c.cambioResuelto.connect(lambda *a: vistos.append(a))
    s.entregar(s.ultimo("PUT", "/email/config"), causa="rol_sin_permiso")
    assert c.envioActivo is True and len(c.destinatarios) == 2
    assert c.mensaje == "opciones.err_rol" and c.mensajeRevertido is True
    assert vistos == [("email", False, "opciones.err_rol")]


def test_conectividad_agregar_rechazado_vuelve_a_la_lista_confirmada():
    s = SesionManual()
    c = _conn_cargado(s)
    c.agregar("Nuevo", "malo")
    assert len(c.destinatarios) == 3
    s.entregar(s.ultimo("PUT", "/email/config"), causa="correo_invalido")
    assert len(c.destinatarios) == 2 and c.mensaje == "conectividad.err_correo_invalido"
    assert c.mensajeRevertido is True


def test_conectividad_sin_respuesta_relee_y_concilia():
    s = SesionManual()
    c = _conn_cargado(s)
    c.fijarEnvio(False)
    s.entregar(s.ultimo("PUT", "/email/config"), causa=BACKEND_NO_RESPONDE)
    assert c.pendientes.get("email") == "verificando"
    n = len(s.vuelo)
    assert s.vuelo[n - 1][:2] == ("GET", "/email/config")
    s.entregar(n - 1, datos=dict(CORREO, envio_activo=False))   # el backend si lo aplico
    assert c.envioActivo is False and "email" not in c.pendientes and c.mensaje == ""


def test_conectividad_sin_respuesta_y_sin_lectura_avisa_y_recarga():
    s = SesionManual()
    c = _conn_cargado(s)
    c.fijarEnvio(False)
    s.entregar(s.ultimo("PUT", "/email/config"), causa=BACKEND_NO_RESPONDE)
    n = len(s.vuelo)
    s.entregar(n - 1, causa=BACKEND_NO_RESPONDE)                 # tampoco responde la relectura
    assert c.envioActivo is True
    assert c.mensaje == "opciones.cambio_sin_confirmar"
    assert s.vuelo[-1][:2] == ("GET", "/network/status") or s.rutas()[-2:] == [
        ("GET", "/network/status"), ("GET", "/email/config")]    # recarga


def test_conectividad_lectura_durante_pendiente_no_pisa_lo_mostrado():
    s = SesionManual()
    c = _conn_cargado(s)
    c.cargar()                                                   # lectura lanzada antes del cambio
    n = len(s.vuelo)
    c.fijarEnvio(False)
    s.entregar(n - 1, datos=CORREO)                              # llega con el valor viejo
    assert c.envioActivo is False                                # sigue lo pendiente


def test_conectividad_prueba_asincrona_con_pendiente():
    s = SesionManual()
    c = _conn_cargado(s)
    assert c.enviarPrueba() is True
    assert c.pendientes.get("prueba") == "enviando" and c.mensaje == ""
    assert c.enviarPrueba() is False                             # ya hay una en vuelo
    s.entregar(s.ultimo("POST", "/email/test"), datos={"ok": True, "enviados": 2})
    assert "prueba" not in c.pendientes and c.mensaje == "conectividad.prueba_enviada"


def test_conectividad_prueba_fallida_no_queda_vigente():
    s = SesionManual()
    c = _conn_cargado(s)
    c.enviarPrueba()
    s.entregar(s.ultimo("POST", "/email/test"), causa="envio_fallido")
    assert c.mensaje == "conectividad.err_envio" and c.mensajeRevertido is False


def test_conectividad_doble_solo_enviar_devuelve_el_resultado_real():
    d = SoloEnviar({("GET", "/network/status"): Resultado("ok", {"conectado": True}),
                    ("GET", "/email/config"): Resultado("ok", CORREO),
                    ("PUT", "/email/config"): Resultado("duplicado", {}),
                    ("POST", "/email/test"): Resultado("ok", {"enviados": 1})})
    c = _conn(d)
    c.cargar()
    assert c.agregar("A", "a@x.co") is False and len(c.destinatarios) == 2
    assert c.mensaje == "conectividad.err_duplicado"
    assert c.enviarPrueba() is True and c.mensaje == "conectividad.prueba_enviada"


# ── Mantenimiento ───────────────────────────────────────────────────────────

_MANT = {"estado": "ok", "proximo": None, "ultimo": None, "ciclos_restantes": 1000,
         "configuracion": {"intervalo_dias": 365, "intervalo_ciclos": 1000}}


def _mant(sesion):
    from autoclave.ui_qml.controllers.mantenimiento_controller import MantenimientoController
    return MantenimientoController(sesion=sesion)


def _mant_cargado(s):
    c = _mant(s)
    c.cargar()
    assert c.cargando and s.rutas() == [("GET", "/maintenance")]
    s.entregar(0, datos=_MANT)
    assert not c.cargando and (c.intervaloDias, c.intervaloCiclos) == (365, 1000)
    return c


def test_mantenimiento_intervalos_optimista_y_confirma_con_recarga():
    s = SesionManual()
    c = _mant_cargado(s)
    assert c.guardarIntervalos(200, 0) is True
    assert (c.intervaloDias, c.intervaloCiclos) == (200, 0) and c.pendientes.get("intervalos") == "enviando"
    vistos = []
    c.cambioResuelto.connect(lambda *a: vistos.append(a))
    i = s.ultimo("PUT", "/maintenance/config")
    assert s.vuelo[i][2] == {"intervalo_dias": 200, "intervalo_ciclos": 0}
    s.entregar(i, datos={"ok": True})
    assert vistos == [("intervalos", True, "")] and "intervalos" not in c.pendientes
    assert s.vuelo[-1][:2] == ("GET", "/maintenance")            # recarga: vencimientos
    assert s.sincronos == []


def test_mantenimiento_intervalos_rechazados_vuelven_a_lo_confirmado():
    s = SesionManual()
    c = _mant_cargado(s)
    c.guardarIntervalos(200, 0)
    vistos = []
    c.cambioResuelto.connect(lambda *a: vistos.append(a))
    s.entregar(s.ultimo("PUT", "/maintenance/config"), causa="estado_no_permitido")
    assert (c.intervaloDias, c.intervaloCiclos) == (365, 1000)
    assert c.mensaje == "opciones.err_bloqueada" and c.mensajeRevertido is True
    assert vistos == [("intervalos", False, "opciones.err_bloqueada")]


def test_mantenimiento_lectura_en_vuelo_no_pisa_el_intervalo_pendiente():
    s = SesionManual()
    c = _mant_cargado(s)
    c.cargar()
    n = len(s.vuelo)
    c.guardarIntervalos(10, 5)
    s.entregar(n - 1, datos=_MANT)
    assert (c.intervaloDias, c.intervaloCiclos) == (10, 5)


def test_mantenimiento_intervalos_sin_respuesta_concilia_con_la_relectura():
    s = SesionManual()
    c = _mant_cargado(s)
    c.guardarIntervalos(200, 0)
    s.entregar(s.ultimo("PUT", "/maintenance/config"), causa=BACKEND_NO_RESPONDE)
    assert c.pendientes.get("intervalos") == "verificando"
    # la relectura muestra otro valor: se muestra ese y se avisa
    s.entregar(len(s.vuelo) - 1, datos=_MANT)
    assert (c.intervaloDias, c.intervaloCiclos) == (365, 1000)
    assert c.mensaje == "opciones.err_sin_respuesta" and "intervalos" not in c.pendientes


def test_mantenimiento_registrar_asincrono_no_vigente_hasta_el_200():
    s = SesionManual()
    c = _mant_cargado(s)
    vistos = []
    c.cambioResuelto.connect(lambda *a: vistos.append(a))
    assert c.registrar("preventivo") is True
    assert c.pendientes.get("registro") == "enviando"
    assert c.registrar("preventivo") is False                   # ya hay uno en vuelo
    assert not any(r == ("GET", "/maintenance") for r in s.rutas()[1:])   # nada se relee aun
    i = s.ultimo("POST", "/maintenance/records")
    assert s.vuelo[i][2] == {"tipo": "preventivo", "observaciones": ""}
    s.entregar(i, datos={"ok": True})
    assert "registro" not in c.pendientes and vistos == [("registro", True, "")]
    assert s.vuelo[-1][:2] == ("GET", "/maintenance") and c.mensaje == ""


def test_mantenimiento_registrar_rechazado_informa_y_relee():
    s = SesionManual()
    c = _mant_cargado(s)
    c.registrar("correctivo")
    s.entregar(s.ultimo("POST", "/maintenance/records"), causa="reloj_adelantado")
    assert c.mensaje == "opciones.mant_err_reloj_adelantado" and c.mensajeRevertido is False
    assert s.vuelo[-1][:2] == ("GET", "/maintenance")


def test_mantenimiento_tipo_invalido_y_limites_no_salen():
    s = SesionManual()
    c = _mant(s)
    assert c.registrar("inventado") is False and c.guardarIntervalos(-1, 0) is False
    assert s.vuelo == [] and c.mensaje == "opciones.mant_err_validacion"


# ── Manejo de ciclos ────────────────────────────────────────────────────────

_PROGS = {"programas": [
    {"numero": 1, "nombre": "Uno", "origen": "user", "habilitado": True, "personalizado": False},
    {"numero": 5, "nombre": "Copia", "origen": "user", "habilitado": True, "personalizado": True},
    {"numero": 9, "nombre": "Fabrica", "origen": "factory", "habilitado": True}]}


def _mc(sesion):
    from autoclave.ui_qml.controllers.manejo_ciclos_controller import ManejoCiclosController
    return ManejoCiclosController(sesion=sesion)


def _mc_cargado(s):
    c = _mc(s)
    c.cargar()
    assert c.cargando
    s.entregar(0, datos=_PROGS)
    assert not c.cargando and [p["numero"] for p in c.programas] == [1, 5]
    return c


def _habilitado(c, n):
    return next(p["habilitado"] for p in c.programas if p["numero"] == n)


def test_manejo_ciclos_deshabilitar_optimista_y_confirma():
    s = SesionManual()
    c = _mc_cargado(s)
    assert c.fijarHabilitado(5, False) is True
    assert _habilitado(c, 5) is False and c.pendientes.get("habilitado:5") == "enviando"
    i = s.ultimo("PUT", "/programas/5/habilitado")
    assert s.vuelo[i][2] == {"habilitado": False}
    s.entregar(i, datos={"ok": True})
    assert c.mensaje == "manejo_ciclos.ok_deshabilitado" and c.exito is True
    assert c.detalleMensaje["nombre"] == "Copia" and not c.pendientes
    assert s.vuelo[-1][:2] == ("GET", "/programas")


def test_manejo_ciclos_rechazo_revierte_y_marca_el_mensaje():
    s = SesionManual()
    c = _mc_cargado(s)
    c.fijarHabilitado(5, False)
    vistos = []
    c.cambioResuelto.connect(lambda *a: vistos.append(a))
    s.entregar(s.ultimo("PUT", "/programas/5/habilitado"), causa="programa_activo")
    assert _habilitado(c, 5) is True
    assert c.mensaje == "manejo_ciclos.err_programa_activo" and c.mensajeRevertido is True
    assert c.exito is False and vistos == [("habilitado:5", False, "manejo_ciclos.err_programa_activo")]


def test_manejo_ciclos_sin_respuesta_relee_y_concilia():
    s = SesionManual()
    c = _mc_cargado(s)
    c.fijarHabilitado(5, False)
    s.entregar(s.ultimo("PUT", "/programas/5/habilitado"), causa=BACKEND_NO_RESPONDE)
    assert c.pendientes.get("habilitado:5") == "verificando"
    lista = {"programas": [dict(_PROGS["programas"][0]),
                           dict(_PROGS["programas"][1], habilitado=False)]}
    s.entregar(len(s.vuelo) - 1, datos=lista)                   # si se aplico
    assert _habilitado(c, 5) is False and not c.pendientes
    assert c.mensaje == "manejo_ciclos.ok_deshabilitado"


def test_manejo_ciclos_lectura_anterior_no_pisa_el_cambio_pendiente():
    s = SesionManual()
    c = _mc_cargado(s)
    c.cargar()
    n = len(s.vuelo)
    c.fijarHabilitado(1, False)
    s.entregar(n - 1, datos=_PROGS)
    assert _habilitado(c, 1) is False


def test_manejo_ciclos_crear_y_borrar_siguen_sincronos():
    s = SesionManual()
    c = _mc_cargado(s)
    assert c.borrar(5) is True                                   # enviar sincrono del doble
    assert ("DELETE", "/programas/5") in s.sincronos


def test_manejo_ciclos_doble_solo_enviar_devuelve_el_resultado_real():
    d = SoloEnviar({("GET", "/programas"): Resultado("ok", _PROGS),
                    ("PUT", "/programas/5/habilitado"): Resultado("programa_activo", {})})
    c = _mc(d)
    c.cargar()
    assert c.fijarHabilitado(5, False) is False
    assert _habilitado(c, 5) is True and c.mensajeRevertido is True


# ── QML ─────────────────────────────────────────────────────────────────────

def test_qml_usa_el_desenlace_y_los_estados_nuevos():
    mant = (QML / "OpcionesMantenimiento.qml").read_text(encoding="utf-8")
    assert "onCambioResuelto" in mant and "if (control.guardarIntervalos(" not in mant
    assert "opciones.cambio_revertido" in mant and "opciones.guardando" in mant
    con = (QML / "OpcionesConectividad.qml").read_text(encoding="utf-8")
    assert "opciones.cambio_revertido" in con and "control.pendientes.prueba" in con
    man = (QML / "OpcionesManejoCiclos.qml").read_text(encoding="utf-8")
    assert "opciones.cambio_revertido" in man and "control.cargando" in man
