"""FASE 6 (P1): Parámetros del equipo.

- Impresora con reinicio (`PUT /printer/config`): operación crítica sin
  optimismo; `reiniciando` solo con el 200 que lo dice; sin respuesta queda
  «sin confirmar» (sin relectura ni reintento: el backend se cierra).
- Tema (`PUT /theme`): OPTIMISTA con reversión (decisión del usuario); el
  cambio global solo al confirmar.
"""
from types import SimpleNamespace

import pytest

from tests.helpers.sesion_f6_controladores import (
    NO_RESPONDE, Resueltas, SesionManual, app, conservar, r)

from autoclave.ui_qml import operacion_critica as oc
from autoclave.ui_qml.bridge import apariencia_qml
from autoclave.ui_qml.controllers.parametros_equipo_controller import ParametrosEquipoController

IMP = "/printer/config"
REINICIA = {"ok": True, "habilitada": False, "reiniciando": True}


@pytest.fixture(scope="module", autouse=True)
def _app():
    return app()


def _ctrl():
    s = SesionManual()
    c = conservar(ParametrosEquipoController(sesion=s, perfil=lambda: None))
    return c, s, Resueltas(c)


# ── impresora con reinicio ──────────────────────────────────────────────────

def test_impresora_envia_con_plazo_10_y_muestra_procesando_sin_reiniciando():
    c, s, res = _ctrl()
    assert c.fijarImpresoraYReiniciar(False) is True
    e = s.envios[s.ultimo("PUT", IMP)]
    assert e["cuerpo"] == {"habilitada": False, "reiniciar": True} and e["plazo_s"] == 10.0
    assert c.operacionEnCurso and c.estadoDe("impresora_reinicio") == "enviando"
    assert c._op.bloquea() and oc.registro.bloqueaNavegacion
    assert c.reiniciando is False and c.impresoraHabilitada is False and res.lista == []


def test_impresora_200_con_reiniciando_activa_el_aviso():
    c, s, res = _ctrl()
    c.fijarImpresoraYReiniciar(False)
    n = len(s.envios)
    s.responder_ultimo("PUT", IMP, r(datos=REINICIA))
    assert c.reiniciando is True and c.impresoraConocida and c.impresoraHabilitada is False
    assert c.mensaje == "" and res.lista == [("impresora_reinicio", "confirmada", "")]
    assert len(s.envios) == n                          # sin relectura: el backend se cierra
    assert not c.operacionEnCurso


def test_impresora_200_sin_reiniciando_no_activa_el_aviso_y_relee():
    c, s, res = _ctrl()
    c.fijarImpresoraYReiniciar(True)
    s.responder_ultimo("PUT", IMP, r(datos={"ok": True, "reiniciando": False}))
    assert c.reiniciando is False and res.lista[-1][1] == "confirmada"
    assert s.cuenta("GET", IMP) == 1


@pytest.mark.parametrize("causa,clave", [
    ("estado_no_permitido", "opciones.equipo_err_ciclo"),
    ("reinicio_no_disponible", "opciones.equipo_err_reinicio_no_disponible"),
    ("estado_seguro_activo", "opciones.equipo_err_reinicio_estado_seguro"),
    ("modo_prueba_activo", "opciones.equipo_err_reinicio_modo_prueba"),
])
def test_impresora_rechazo_muestra_el_motivo_y_relee(causa, clave):
    c, s, res = _ctrl()
    c.fijarImpresoraYReiniciar(False)
    s.responder_ultimo("PUT", IMP, r(causa, {}, 409))
    assert c.reiniciando is False and c.mensaje == clave
    assert res.lista == [("impresora_reinicio", "rechazada", clave)]
    assert s.cuenta("GET", IMP) == 1                   # se relee el estado real


def test_impresora_sin_respuesta_sin_confirmar_sin_relectura_ni_reintento():
    c, s, res = _ctrl()
    c.fijarImpresoraYReiniciar(False)
    n = len(s.envios)
    s.responder_ultimo("PUT", IMP, r(NO_RESPONDE, None, 0))
    assert res.lista == [("impresora_reinicio", "sin_confirmar",
                          "opciones.equipo_reinicio_sin_confirmar")]
    assert c.mensaje == "opciones.equipo_reinicio_sin_confirmar"
    assert c.reiniciando is False and not c.operacionEnCurso
    assert len(s.envios) == n and s.cuenta("PUT", IMP) == 1


def test_impresora_doble_toque_un_solo_envio():
    c, s, _ = _ctrl()
    assert c.fijarImpresoraYReiniciar(False) is True
    assert c.fijarImpresoraYReiniciar(True) is False
    assert s.cuenta("PUT", IMP) == 1


def test_impresora_tardia_con_reiniciando_activa_el_aviso_con_su_texto():
    c, s, res = _ctrl()
    c.fijarImpresoraYReiniciar(False)
    i = s.ultimo("PUT", IMP)
    s.responder(i, r(NO_RESPONDE, None, 0))
    assert c.reiniciando is False
    s.tardio(i, r(datos=REINICIA))
    assert c.reiniciando is True
    assert res.lista[-1] == ("impresora_reinicio", "confirmada", "operacion.confirmada_tarde")


def test_impresora_optimista_y_con_reinicio_se_excluyen():
    """MENOR-6: «impresora» (optimista) no se lanza con «impresora_reinicio»
    en vuelo, ni al revés."""
    c, s, _ = _ctrl()
    assert c.fijarImpresoraYReiniciar(False) is True
    n = s.cuenta("PUT", IMP)
    assert c.fijarImpresora(True) is False and s.cuenta("PUT", IMP) == n
    c2, s2, _ = _ctrl()
    c2.fijarImpresora(True)
    assert "impresora" in c2.pendientes
    n2 = s2.cuenta("PUT", IMP)
    assert c2.fijarImpresoraYReiniciar(False) is False and s2.cuenta("PUT", IMP) == n2
    assert not c2.operacionEnCurso


# ── tema optimista ──────────────────────────────────────────────────────────

@pytest.fixture
def globales(monkeypatch):
    llamadas = []
    monkeypatch.setattr(apariencia_qml, "instancia",
                        SimpleNamespace(fijar=lambda t: llamadas.append(t)))
    return llamadas


def _con_tema(tema="claro"):
    c, s, res = _ctrl()
    c._tema = tema
    return c, s, res


def test_tema_es_optimista_y_el_cambio_global_espera_al_200(globales):
    c, s, res = _con_tema("claro")
    resueltos = []
    c.cambioResuelto.connect(lambda *a: resueltos.append(a))
    assert c.fijarTema("oscuro") is True
    assert c.tema == "oscuro"                              # el selector ya lo muestra
    assert s.envios[s.ultimo("PUT", "/theme")]["cuerpo"] == {"tema": "oscuro"}
    assert c.pendientes.get("tema") == "enviando" and globales == []
    s.responder_ultimo("PUT", "/theme", r(datos={"tema": "oscuro"}))
    assert globales == ["oscuro"] and c.tema == "oscuro"
    assert resueltos == [("tema", True, "")] and "tema" not in c.pendientes


@pytest.mark.parametrize("causa,clave", [
    ("ARCHIVO_NO_ESCRIBIBLE", "opciones.equipo_err_guardar"),
    ("rol_sin_permiso", "opciones.err_rol"),
])
def test_tema_rechazado_revierte_sin_tocar_el_tema_global(globales, causa, clave):
    c, s, _ = _con_tema("claro")
    resueltos = []
    c.cambioResuelto.connect(lambda *a: resueltos.append(a))
    c.fijarTema("oscuro")
    s.responder_ultimo("PUT", "/theme", r(causa, {}, 409))
    assert c.tema == "claro" and globales == []
    assert c.mensaje == clave and c.mensajeRevertido is True
    assert resueltos == [("tema", False, clave)]
    assert s.cuenta("GET", "/theme") == 1                   # se relee el estado real


def test_tema_sin_respuesta_relee_y_si_coincide_confirma(globales):
    c, s, _ = _con_tema("claro")
    c.fijarTema("oscuro")
    s.responder_ultimo("PUT", "/theme", r(NO_RESPONDE, None, 0))
    assert c.pendientes.get("tema") == "verificando" and globales == []
    s.responder_ultimo("GET", "/theme", r(datos={"tema": "oscuro"}))
    assert c.tema == "oscuro" and globales == ["oscuro"] and c.mensaje == ""


def test_tema_sin_respuesta_relee_y_si_no_coincide_revierte(globales):
    c, s, _ = _con_tema("claro")
    c.fijarTema("oscuro")
    s.responder_ultimo("PUT", "/theme", r(NO_RESPONDE, None, 0))
    s.responder_ultimo("GET", "/theme", r(datos={"tema": "claro"}))
    assert c.tema == "claro" and globales == []
    assert c.mensaje == "opciones.err_sin_respuesta" and c.mensajeRevertido is True


def test_tema_sin_respuesta_y_sin_relectura_queda_sin_confirmar(globales):
    c, s, _ = _con_tema("claro")
    c.fijarTema("oscuro")
    s.responder_ultimo("PUT", "/theme", r(NO_RESPONDE, None, 0))
    s.responder_ultimo("GET", "/theme", r(NO_RESPONDE, None, 0))
    assert c.tema == "claro" and globales == []
    assert c.mensaje == "opciones.cambio_sin_confirmar"


def test_tema_invalido_no_envia(globales):
    c, s, _ = _con_tema("claro")
    assert c.fijarTema("rosa") is False
    assert s.cuenta("PUT", "/theme") == 0 and c.tema == "claro"


def test_cargar_lee_el_tema_por_la_ruta_optimista(globales):
    c, s, _ = _ctrl()
    c.cargar()
    s.responder_ultimo("GET", "/theme", r(datos={"tema": "oscuro"}))
    assert c.tema == "oscuro"
    c.cargar()
    s.responder_ultimo("GET", "/theme", r(datos={"tema": "violeta"}))   # inválido: conserva
    assert c.tema == "oscuro"
