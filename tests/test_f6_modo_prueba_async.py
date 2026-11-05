"""FASE 6 (AJUSTES 2026-11-02, paso 2): modo prueba de Entradas / Salidas
asíncrono y SIN OPTIMISMO (OperacionCritica).

- modoPrueba solo cambia con el 200, con modo_prueba_inactivo (salida) o con
  una relectura (/status pedido después de la orden) que lo confirme.
- salidasHabilitadas baja durante la entrada, la salida y mientras alguna
  quede sin confirmar; accionar(True) sin ella no envía nada, el apagado
  sale siempre.
- Salida sin confirmar: un único reintento automático.
- Pantalla destruida: la salida sale igual (nadie la cancela) y luego se
  quita el gancho de cierre de sesión.
- Keepalive: uno a la vez; sin respuesta solo log.
- Adoptar el modo prueba desde /status registra el gancho de cierre.
"""

import os
import sys
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from autoclave.ui_qml import sesion_backend as sb  # noqa: E402
from autoclave.ui_qml.operacion_critica import MSG_CONFIRMADA_TARDE  # noqa: E402

OK = sb.Resultado("ok", {"ok": True}, 200)
NO_RESPONDE = sb.Resultado(sb.BACKEND_NO_RESPONDE)
INACTIVO = sb.Resultado("modo_prueba_inactivo", {"detail": "no activo"}, 409)

_STATUS = {"machine_state": "PREPARADO", "estado_modulo_es": "ok", "card_connected": True,
           "test_mode_active": False,
           "sensors": {"digital_inputs": {}, "digital_outputs": {"vapor_camara": 0},
                       "temperature": {}, "pressure": {"camara": 101.0}}}


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QCoreApplication.instance() or QCoreApplication(sys.argv)


class SesionDoble:
    """enviar_async guarda el callback (la prueba decide qué entregar);
    enviar (salidas, síncronas) responde 200; registra los ganchos."""
    def __init__(self):
        self.generacion = 0
        self.envios = []
        self.sincronos = []
        self.cancelados = []
        self.ganchos = []

    def enviar_async(self, metodo, ruta, cuerpo=None, al_terminar=None, *, dueno=None,
                     al_tardio=None, plazo_s=None):
        self.envios.append({"metodo": metodo, "ruta": ruta, "cuerpo": cuerpo,
                            "al_terminar": al_terminar, "al_tardio": al_tardio,
                            "dueno": dueno, "plazo_s": plazo_s})
        return True

    def enviar(self, metodo, ruta, cuerpo=None):
        self.sincronos.append((metodo, ruta, cuerpo))
        return OK

    def enviar_al_cerrar(self, metodo, ruta, cuerpo=None):
        self.sincronos.append((metodo, ruta, cuerpo))
        return OK

    def cancelar_envios(self, dueno):
        self.cancelados.append(dueno)

    def al_cerrar_sesion(self, aviso):
        if aviso not in self.ganchos:
            self.ganchos.append(aviso)

    def quitar_al_cerrar_sesion(self, aviso):
        if aviso in self.ganchos:
            self.ganchos.remove(aviso)

    # ayudas de la prueba
    def de(self, ruta):
        return [e for e in self.envios if e["ruta"] == ruta]

    def responder(self, ruta, r, i=-1):
        self.de(ruta)[i]["al_terminar"](r)

    def tardio(self, ruta, r, i=-1):
        self.de(ruta)[i]["al_tardio"](r)


class Fuente:
    """Caché de /status. `nuevo()` lo marca pedido después de cualquier orden;
    `viejo()` antes de la última."""
    def __init__(self, ctrl_ref):
        self.status = dict(_STATUS)
        self.t_envio = 0.0
        self.ctrl = ctrl_ref

    def status_vigente(self):
        return self.status, True, 0.1, self.t_envio

    def nuevo(self, activo):
        self.status = {**_STATUS, "test_mode_active": activo}
        self.t_envio = time.monotonic() + 1.0

    def viejo(self, activo):
        self.status = {**_STATUS, "test_mode_active": activo}
        self.t_envio = (self.ctrl[0]._t_orden or 0.0) - 0.5


def _ctrl():
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        EntradasSalidasController)
    s = SesionDoble()
    ref = [None]
    f = Fuente(ref)
    c = EntradasSalidasController(sesion=s, fuente_estado=f)
    ref[0] = c
    res = []
    c.operacionResuelta.connect(lambda *a: res.append(a))
    return c, s, f, res


def _en_prueba():
    c, s, f, res = _ctrl()
    assert c.entrarModoPrueba() is True
    s.responder("/io/test/enter", OK)
    assert c.modoPrueba is True and c.salidasHabilitadas is True
    res.clear()
    return c, s, f, res


def _procesar(seg=0.5):
    fin = time.monotonic() + seg
    while time.monotonic() < fin:
        QCoreApplication.processEvents()
        time.sleep(0.01)


# ── entrada ─────────────────────────────────────────────────────────────────

def test_modo_prueba_no_cambia_antes_del_200():
    c, s, f, res = _ctrl()
    cambios = []
    c.modoPruebaChanged.connect(lambda: cambios.append(c.modoPrueba))
    assert c.entrarModoPrueba() is True
    assert c.modoPrueba is False and c.salidasHabilitadas is False
    assert c.estadoDe("modo_prueba") == "enviando" and c.operacionEnCurso is True
    # m2: el gancho de cierre de sesión se pone al INICIAR la entrada
    assert s.ganchos == [c._al_cerrar_sesion] and cambios == []
    # un /status nuevo con el modo activo no se adopta con la orden en vuelo
    f.nuevo(True)
    c.actualizar()
    assert c.modoPrueba is False
    s.responder("/io/test/enter", OK)
    assert c.modoPrueba is True and c.salidasHabilitadas is True and cambios == [True]
    assert s.ganchos == [c._al_cerrar_sesion]
    assert res == [("modo_prueba", "confirmada", "")]
    assert c.estadoDe("modo_prueba") == "inactiva" and c.operacionEnCurso is False


def test_entrada_rechazada_no_cambia_nada():
    c, s, f, res = _ctrl()
    c.entrarModoPrueba()
    s.responder("/io/test/enter", sb.Resultado("modo_prueba_rechazado",
                                               {"detail": "Paro"}, 409))
    assert c.modoPrueba is False and c.salidasHabilitadas is False and s.ganchos == []
    assert res[-1][:2] == ("modo_prueba", "rechazada") and c.mensaje == "io.err_rechazado"


def test_entrada_en_vuelo_no_se_duplica():
    c, s, f, res = _ctrl()
    assert c.entrarModoPrueba() is True
    assert c.entrarModoPrueba() is False and c.mensaje == "operacion.procesando"
    assert len(s.de("/io/test/enter")) == 1


def test_entrada_sin_respuesta_relectura_activo_adopta_con_gancho():
    c, s, f, res = _ctrl()
    c.entrarModoPrueba()
    f.viejo(True)                          # pedido antes: no vale como relectura
    s.responder("/io/test/enter", NO_RESPONDE)
    assert c.estadoDe("modo_prueba") == "verificando" and c.modoPrueba is False
    f.nuevo(True)
    _procesar(0.4)                         # sondeo de la relectura (200 ms)
    assert res == [("modo_prueba", "confirmada", "")]
    assert c.modoPrueba is True and c.salidasHabilitadas is True
    assert s.ganchos == [c._al_cerrar_sesion]


def test_entrada_sin_respuesta_relectura_inactivo_queda_sin_confirmar_y_vuelve():
    c, s, f, res = _ctrl()
    c.entrarModoPrueba()
    f.nuevo(False)
    s.responder("/io/test/enter", NO_RESPONDE)
    assert res == [("modo_prueba", "sin_confirmar", "io.prueba_sin_confirmar")]
    assert c.modoPrueba is False and c.salidasHabilitadas is False
    assert c._prueba_sin_confirmar is True and c.mensaje == "io.prueba_sin_confirmar"
    # mientras no se sepa, el cierre de sesión pide la salida
    assert s.ganchos == [c._al_cerrar_sesion]
    # el primer /status nuevo inactivo: vuelve a inactiva
    f.nuevo(False)
    c.actualizar()
    assert c._prueba_sin_confirmar is False and s.ganchos == []


def test_entrada_sin_confirmar_y_status_activo_despues_adopta():
    c, s, f, res = _ctrl()
    c.entrarModoPrueba()
    f.nuevo(False)
    s.responder("/io/test/enter", NO_RESPONDE)
    f.nuevo(True)
    c.actualizar()
    assert c.modoPrueba is True and c.salidasHabilitadas is True
    assert c._prueba_sin_confirmar is False and s.ganchos == [c._al_cerrar_sesion]


def test_entrada_tardia_no_fija_estado_solo_marca_la_orden():
    c, s, f, res = _ctrl()
    c.entrarModoPrueba()
    f.nuevo(False)
    s.responder("/io/test/enter", NO_RESPONDE)
    t_antes = c._t_orden
    time.sleep(0.01)
    s.tardio("/io/test/enter", OK)
    assert ("modo_prueba", "confirmada", MSG_CONFIRMADA_TARDE) in res
    assert c.modoPrueba is False and c.salidasHabilitadas is False
    assert c._t_orden > t_antes             # un /status anterior ya no se usa
    f.viejo(False)
    c.actualizar()
    assert c._prueba_sin_confirmar is True  # el viejo no decide
    f.nuevo(True)
    c.actualizar()
    assert c.modoPrueba is True and s.ganchos == [c._al_cerrar_sesion]


# ── salida ──────────────────────────────────────────────────────────────────

def test_salida_baja_las_salidas_antes_de_enviar_y_confirma_con_200():
    c, s, f, res = _en_prueba()
    vistos = []
    c.salidasHabilitadasChanged.connect(
        lambda: vistos.append((c.salidasHabilitadas, len(s.de("/io/test/exit")))))
    assert c.salirModoPrueba("salida solicitada") is True
    assert vistos == [(False, 0)]           # deshabilitadas ANTES de lanzar la salida
    assert s.de("/io/test/exit")[0]["cuerpo"] == {"motivo": "salida solicitada"}
    assert c.modoPrueba is True             # sin 200 no se da por salida
    # durante la salida: encender no sale; apagar sí
    assert c.accionar("vapor_camara", True) is False
    assert c.accionar("vapor_camara", False) is True
    assert s.sincronos == [("PATCH", "/io/test/output/vapor_camara", {"value": False})]
    s.responder("/io/test/exit", OK)
    assert c.modoPrueba is False and c.salidasHabilitadas is False and s.ganchos == []
    assert res == [("modo_prueba", "confirmada", "")]


def test_salida_con_modo_prueba_inactivo_cuenta_como_hecha():
    c, s, f, res = _en_prueba()
    c.salirModoPrueba("x")
    s.responder("/io/test/exit", INACTIVO)
    assert res == [("modo_prueba", "confirmada", "")]
    assert c.modoPrueba is False and c.mensaje == "" and s.ganchos == []


def test_salida_sin_confirmar_un_solo_reintento_y_boton_habilitado():
    c, s, f, res = _en_prueba()
    c.salirModoPrueba("salida solicitada")
    f.nuevo(True)                           # el backend sigue en modo prueba
    s.responder("/io/test/exit", NO_RESPONDE)
    assert len(s.de("/io/test/exit")) == 2  # reintento automático
    assert s.de("/io/test/exit")[1]["cuerpo"] == {"motivo": "salida solicitada"}
    assert res[0] == ("modo_prueba", "sin_confirmar", "io.prueba_sin_confirmar")
    f.nuevo(True)
    s.responder("/io/test/exit", NO_RESPONDE)
    assert len(s.de("/io/test/exit")) == 2  # no hay un segundo reintento
    assert c.modoPrueba is True and c.salidasHabilitadas is False
    assert c.mensaje == "io.prueba_sin_confirmar"
    assert s.ganchos == [c._al_cerrar_sesion]       # el gancho se mantiene
    assert c.estadoDe("modo_prueba") == "inactiva"  # botón Salir habilitado
    # keepalive detenido; un /status nuevo activo no rehabilita las salidas
    c.keepalive()
    assert s.de("/io/test/keepalive") == []
    f.nuevo(True)
    c.actualizar()
    assert c.salidasHabilitadas is False
    # Salir de nuevo (a mano): sale otra salida
    assert c.salirModoPrueba("salida solicitada") is True
    assert len(s.de("/io/test/exit")) == 3
    s.responder("/io/test/exit", INACTIVO)
    assert c.modoPrueba is False and s.ganchos == []


def test_salida_sin_respuesta_relectura_inactivo_confirma_sin_reintento():
    c, s, f, res = _en_prueba()
    c.salirModoPrueba("x")
    f.nuevo(False)
    s.responder("/io/test/exit", NO_RESPONDE)
    assert len(s.de("/io/test/exit")) == 1
    assert res == [("modo_prueba", "confirmada", "")] and c.modoPrueba is False


def test_salida_sin_confirmar_y_status_inactivo_despues_limpia():
    c, s, f, res = _en_prueba()
    c.salirModoPrueba("x")
    f.nuevo(True)
    s.responder("/io/test/exit", NO_RESPONDE)
    f.nuevo(True)
    s.responder("/io/test/exit", NO_RESPONDE)
    f.nuevo(False)                          # el backend salió solo (inactividad)
    c.actualizar()
    assert c.modoPrueba is False and c._salida_sin_confirmar is False and s.ganchos == []


def test_salir_con_la_entrada_en_vuelo_sale_al_resolverse():
    c, s, f, res = _ctrl()
    c.entrarModoPrueba()
    assert c.salirModoPrueba("abandono de la sección") is True
    assert s.de("/io/test/exit") == []      # misma clave: espera a la entrada
    s.responder("/io/test/enter", OK)
    assert len(s.de("/io/test/exit")) == 1 and c.salidasHabilitadas is False
    s.responder("/io/test/exit", OK)
    assert c.modoPrueba is False and s.ganchos == []


def test_salir_sin_modo_prueba_no_envia():
    c, s, f, res = _ctrl()
    assert c.salirModoPrueba("x") is True and s.envios == []


# ── salidas ─────────────────────────────────────────────────────────────────

def test_accionar_encender_exige_habilitacion_y_apagar_sale_siempre():
    c, s, f, res = _ctrl()
    assert c.accionar("vapor_camara", True) is False
    assert c.accionar("bomba_vacio", True) is False
    assert s.sincronos == []
    assert c.accionar("bomba_vacio", False) is True
    assert s.sincronos == [("PATCH", "/io/test/output/bomba_vacio", {"value": False})]
    # durante la entrada tampoco se enciende
    c.entrarModoPrueba()
    assert c.accionar("vapor_camara", True) is False
    s.responder("/io/test/enter", OK)
    assert c.accionar("vapor_camara", True) is True


def test_apagar_con_modo_prueba_inactivo_no_es_error():
    c, s, f, res = _ctrl()
    s.enviar = lambda m, r, cu=None: (s.sincronos.append((m, r, cu)), INACTIVO)[1]
    assert c.accionar("bomba_vacio", False) is True and c.mensaje == ""


# ── pantalla destruida ──────────────────────────────────────────────────────

def test_pantalla_destruida_la_salida_sale_y_luego_se_quita_el_gancho():
    c, s, f, res = _en_prueba()
    orden = []
    s.quitar_al_cerrar_sesion = lambda aviso: orden.append(("quitar", len(s.de("/io/test/exit"))))
    c.abandonar("abandono de la sección")
    salidas = s.de("/io/test/exit")
    assert len(salidas) == 1 and salidas[0]["cuerpo"] == {"motivo": "abandono de la sección"}
    assert orden[-1] == ("quitar", 1)       # el gancho se quita DESPUÉS de lanzarla
    assert s.cancelados == []               # nadie cancela la salida
    # el dueño del envío es la operación del controlador, no la pantalla
    assert salidas[0]["dueno"] is c._op
    c.deleteLater()
    _procesar(0.1)
    assert s.cancelados == []


def test_pantalla_destruida_con_la_entrada_en_vuelo_envia_salida_sin_dueno():
    c, s, f, res = _ctrl()
    c.entrarModoPrueba()
    c.abandonar("abandono de la sección")
    salidas = s.de("/io/test/exit")
    assert len(salidas) == 1 and salidas[0]["dueno"] is None
    assert s.ganchos == [] and s.cancelados == []


def test_qml_liga_salidas_a_salidas_habilitadas():
    from pathlib import Path
    texto = (Path(__file__).resolve().parents[1] / "src/autoclave/ui_qml/qml/Pantallas"
             / "OpcionesEntradasSalidas.qml").read_text(encoding="utf-8")
    assert "readonly property bool libre: control.salidasHabilitadas" in texto
    assert "running: raiz.visible && control.salidasHabilitadas" in texto
    # Tanda 27 (A4): sin renovación de 500 ms de salidas momentáneas
    assert "id: renovacion" not in texto and "momentanea" not in texto
    assert 'Component.onDestruction: cerrarModoPrueba("abandono de la sección", true)' in texto
    assert "control.abandonar(causa)" in texto


# ── keepalive ───────────────────────────────────────────────────────────────

def test_keepalive_no_se_duplica_y_sin_respuesta_solo_log():
    c, s, f, res = _en_prueba()
    c.keepalive()
    c.keepalive()
    assert len(s.de("/io/test/keepalive")) == 1
    assert s.de("/io/test/keepalive")[0]["plazo_s"] == 5.0
    assert c.operacionEnCurso is False      # no bloquea los botones
    s.responder("/io/test/keepalive", NO_RESPONDE)
    assert c.mensaje == "" and c.modoPrueba is True and c.salidasHabilitadas is True
    c.keepalive()
    assert len(s.de("/io/test/keepalive")) == 2
    s.responder("/io/test/keepalive", OK)


def test_keepalive_no_agota_los_envios_en_vuelo():
    c, s, f, res = _en_prueba()
    for _ in range(sb.MAX_ENVIOS_EN_VUELO * 2):
        c.keepalive()
    assert len(s.de("/io/test/keepalive")) == 1


def test_keepalive_sin_modo_prueba_no_envia():
    c, s, f, res = _ctrl()
    c.keepalive()
    assert s.envios == []


# ── adopción desde /status ──────────────────────────────────────────────────

def test_adopcion_desde_status_registra_y_quita_el_gancho():
    c, s, f, res = _ctrl()
    f.nuevo(True)
    c.actualizar()
    assert c.modoPrueba is True and c.salidasHabilitadas is True
    assert s.ganchos == [c._al_cerrar_sesion]
    f.nuevo(False)
    c.actualizar()
    assert c.modoPrueba is False and s.ganchos == []


def test_cierre_de_sesion_sale_y_limpia():
    c, s, f, res = _en_prueba()
    c._al_cerrar_sesion()
    assert ("POST", "/io/test/exit", {"motivo": "cierre de sesión"}) in s.sincronos
    assert c.modoPrueba is False and s.ganchos == []


# ── corrección tras revisión (M1, m2, m3) ──────────────────────────────────

def test_m1_salida_sin_confirmar_permite_apagar_una_sostenida_y_no_encender():
    c, s, f, res = _en_prueba()
    assert c.pruebaSinConfirmar is False
    avisos = []
    c.pruebaSinConfirmarChanged.connect(lambda: avisos.append(c.pruebaSinConfirmar))
    c.salirModoPrueba("salida solicitada")
    f.nuevo(True)
    s.responder("/io/test/exit", NO_RESPONDE)
    f.nuevo(True)
    s.responder("/io/test/exit", NO_RESPONDE)            # también el reintento
    assert c.salidasHabilitadas is False and c.pruebaSinConfirmar is True
    assert avisos == [True]                              # con notify
    assert c.accionar("vapor_camara", True) is False
    assert c.accionar("vapor_camara", False) is True
    assert s.sincronos == [("PATCH", "/io/test/output/vapor_camara", {"value": False})]
    # entrada sin confirmar: también hay dudas
    c2, s2, f2, _ = _ctrl()
    c2.entrarModoPrueba()
    f2.nuevo(False)
    s2.responder("/io/test/enter", NO_RESPONDE)
    assert c2.modoPrueba is False and c2.pruebaSinConfirmar is True
    f2.nuevo(False)
    c2.actualizar()
    assert c2.pruebaSinConfirmar is False


def test_m1_qml_ofrece_el_apagado_de_una_sostenida_encendida():
    from pathlib import Path
    texto = (Path(__file__).resolve().parents[1] / "src/autoclave/ui_qml/qml/Pantallas"
             / "OpcionesEntradasSalidas.qml").read_text(encoding="utf-8")
    assert "habilitado: tarjetaSalida.libre || tarjetaSalida.puedeApagar" in texto
    i = texto.index("readonly property bool puedeApagar:")
    regla = " ".join(texto[i:i + 400].split())
    # Tanda 26 (SMP): `apagar` lo arma el controlador; sin orden pendiente es
    # `encendida === true` (presentar_con_pendientes) y con una orden ON
    # pendiente también ofrece el apagado
    # Tanda 27 (A4): sin la condición de momentánea
    assert regla.startswith("readonly property bool puedeApagar: modelData.apagar === true "
                            "&& (control.modoPrueba || control.pruebaSinConfirmar)")
    from autoclave.ui_qml.controllers.entradas_salidas_controller import (
        presentar_con_pendientes)
    base = [{"name": "x", "encendida": v} for v in (True, False, None)]
    assert [s["apagar"] for s in presentar_con_pendientes(base, {})] == [True, False, False]


def test_m2_gancho_al_iniciar_y_se_quita_con_rechazo_o_inactivo():
    c, s, f, res = _ctrl()
    c.entrarModoPrueba()
    assert s.ganchos == [c._al_cerrar_sesion]
    s.responder("/io/test/enter", sb.Resultado("modo_prueba_rechazado", {}, 409))
    assert s.ganchos == [] and c.modoPrueba is False
    # sin respuesta y relectura inactiva -> sin confirmar (gancho), luego /status inactivo
    c.entrarModoPrueba()
    f.nuevo(False)
    s.responder("/io/test/enter", NO_RESPONDE)
    assert s.ganchos == [c._al_cerrar_sesion]
    f.nuevo(False)
    c.actualizar()
    assert s.ganchos == []


@pytest.mark.parametrize("respuesta", [NO_RESPONDE, OK])
def test_m2_cambio_de_sesion_con_la_entrada_en_vuelo_no_deja_gancho(respuesta):
    c, s, f, res = _ctrl()
    c.entrarModoPrueba()
    c._al_cerrar_sesion()                    # logout: pide la salida y limpia
    assert ("POST", "/io/test/exit", {"motivo": "cierre de sesión"}) in s.sincronos
    s.generacion += 1                        # sesión de otro usuario
    s.responder("/io/test/enter", respuesta)
    assert s.ganchos == [] and c.modoPrueba is False
    assert c.pruebaSinConfirmar is False and c.salidasHabilitadas is False


def test_m3_salida_que_no_salio_con_sesion_invalida_cuenta_como_hecha():
    c, s, f, res = _en_prueba()
    original = s.enviar_async

    def no_sale(*a, **kw):
        original(*a, **kw)
        return False
    s.enviar_async = no_sale
    c.salirModoPrueba("x")
    s.responder("/io/test/exit", sb.Resultado("sesion_invalida"))
    assert res == [("modo_prueba", "confirmada", "")]
    assert c.modoPrueba is False and s.ganchos == []


def test_canales_asincronos_y_uno_a_la_vez():
    c, s, f, res = _ctrl()
    c.cargarCanales()
    c.cargarCanales()
    assert len(s.de("/io/channels")) == 1 and s.sincronos == []
    s.responder("/io/channels", sb.Resultado("ok", {"DI": [], "DO": [{"name": "vapor_camara",
        "estado_key": "vapor_camara", "i18n": "io.do.vapor_camara", "id": "DO 04",
        "bloqueada": False}], "temperature": [], "pressure": []}, 200))
    assert [x["name"] for x in c.salidas] == ["vapor_camara"]
    c.cargarCanales()
    assert len(s.de("/io/channels")) == 2
