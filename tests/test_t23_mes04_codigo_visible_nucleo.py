# tests/test_t23_mes04_codigo_visible_nucleo.py
#
# Tanda 23 (MES-04, decisiones_tanda_23.md), parte del núcleo: donde el backend,
# el ticket o el motivo de fallo muestran un código de alarma, TARJETA_<x> se ve
# como MODULO_ES_<x> (codigo_visible()); el código guardado no cambia.
#   - Ticket (motivo_ticket del historial y en tiempo real, format_footer con un
#     motivo guardado de texto libre).
#   - Motivo de fallo (alarmas_i18n.motivo_fallo y CicloState._registrar_fallo).
#   - DTO de alarma de /status (codigo_visible; id/codigo/clave intactos).
#   - El historial de alarmas sigue guardando TARJETA_SIN_ACK.

from types import SimpleNamespace

import pytest

from autoclave.core.runtime import alarmas_i18n
from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import (
    COM_03, TARJETA_SIN_ACK, codigo_visible, texto_con_codigos_visibles)

pytestmark = pytest.mark.req("MES-04")

_VISIBLE = "MODULO_ES_SIN_ACK"


def test_codigo_guardado_no_cambia():
    assert TARJETA_SIN_ACK == "TARJETA_SIN_ACK"
    assert codigo_visible(TARJETA_SIN_ACK) == _VISIBLE


def test_texto_con_codigos_visibles():
    assert (texto_con_codigos_visibles("COM-03 · x: TARJETA_SIN_ACK: sin ack")
            == "COM-03 · x: MODULO_ES_SIN_ACK: sin ack")
    # solo el prefijo de un código; otras palabras y no-textos sin tocar
    assert texto_con_codigos_visibles("SEN-02 · sonda") == "SEN-02 · sonda"
    assert texto_con_codigos_visibles("XTARJETA_A") == "XTARJETA_A"
    assert texto_con_codigos_visibles(None) is None


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_ticket_motivo_con_codigo_visible(idioma):
    p = tf.Presentacion(idioma=idioma)
    linea = tf.motivo_ticket(TARJETA_SIN_ACK, "TARJETA_SIN_ACK · lo que sea", p)
    assert linea.startswith(f"{_VISIBLE} - ")
    assert "TARJETA_" not in linea


def test_ticket_motivo_guardado_de_texto_libre():
    # ciclo viejo sin código del catálogo: el motivo guardado se imprime visible
    assert tf.motivo_ticket(None, "TARJETA_SIN_ACK: sin ack") == f"{_VISIBLE}: sin ack"
    pie = tf.format_footer("FALLO", "2026-10-29 10:05:00", motivo="TARJETA_SIN_ACK · algo")
    assert f"{_VISIBLE} · algo" in pie and "TARJETA_" not in pie


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_motivo_fallo_con_codigo_visible(idioma):
    con_valores = alarmas_i18n.motivo_fallo(TARJETA_SIN_ACK, {"motivo": "sin ack"}, None, idioma)
    assert con_valores.startswith(f"{_VISIBLE} · ") and "TARJETA_" not in con_valores
    sin_valores = alarmas_i18n.motivo_fallo(TARJETA_SIN_ACK, {}, None, idioma)
    assert sin_valores.startswith(f"{_VISIBLE} · ")
    # COM-03 de un ciclo viejo con la causa guardada como código
    com03 = alarmas_i18n.motivo_fallo(COM_03, {"causa": "TARJETA_SIN_ACK", "motivo": "m",
                                               "fase": "Esterilización"}, None, idioma)
    assert _VISIBLE in com03 and "TARJETA_" not in com03
    # motivo registrado (español, sin parámetros) y texto libre sin código
    assert alarmas_i18n.motivo_fallo(TARJETA_SIN_ACK, {}, "TARJETA_SIN_ACK · x", "es") == f"{_VISIBLE} · x"
    assert alarmas_i18n.motivo_fallo(None, None, "TARJETA_SIN_ACK: x", idioma) == f"{_VISIBLE}: x"


def test_registrar_fallo_guarda_motivo_visible_y_codigo_guardado():
    from autoclave.state_machine.states.ciclo import CicloState
    am = AlarmManager()
    estado = SimpleNamespace(motivo_fallo=None, codigo_fallo=None, valores_fallo=None)
    yo = SimpleNamespace(alarm_manager=am, estado=estado)
    CicloState._registrar_fallo(yo, TARJETA_SIN_ACK, origen="operacion", motivo="sin ack")
    assert estado.codigo_fallo == "TARJETA_SIN_ACK"
    assert estado.motivo_fallo.startswith(f"{_VISIBLE} · ")
    assert "TARJETA_" not in estado.motivo_fallo
    # COM-03 con la causa: el origen (clave) sigue siendo el código guardado
    estado2 = SimpleNamespace(motivo_fallo=None, codigo_fallo=None, valores_fallo=None)
    CicloState._registrar_fallo(SimpleNamespace(alarm_manager=am, estado=estado2), COM_03,
                                origen=TARJETA_SIN_ACK, causa=codigo_visible(TARJETA_SIN_ACK),
                                motivo="m", fase="Esterilización")
    assert estado2.codigo_fallo == COM_03 and _VISIBLE in estado2.motivo_fallo
    assert any(i.origen == "TARJETA_SIN_ACK" for i in am.activas())


def test_dto_de_alarma_con_codigo_visible():
    from autoclave.backend import server  # noqa: F401  (carga el backend partido)
    from tests.helpers.backend_doble import modulo_backend
    am = AlarmManager()
    am.activar(TARJETA_SIN_ACK, "operacion", motivo="sin ack")
    dto = modulo_backend("rutas.sistema")._alarma_dto(am.activas()[0])
    assert dto["codigo_visible"] == _VISIBLE
    # lo guardado no cambia: el reconocimiento usa id/clave/codigo
    assert dto["codigo"] == "TARJETA_SIN_ACK"
    assert dto["id"] == dto["clave"] and dto["id"].startswith("TARJETA_SIN_ACK")
    otra = AlarmManager()
    otra.activar(COM_03, "x", causa="c", motivo="m", fase="f")
    assert modulo_backend("rutas.sistema")._alarma_dto(otra.activas()[0])["codigo_visible"] == COM_03


def test_historial_sigue_guardando_tarjeta_sin_ack(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.services.domain.logging.historial_alarmas import HistorialAlarmas
    db, am = DbManager(db_path=tmp_path / "t.db"), AlarmManager()
    h = HistorialAlarmas(db, am, ciclo_actual=lambda: None)
    try:
        am.activar(TARJETA_SIN_ACK, "operacion", motivo="sin ack")
        assert h.vaciar()
        [fila] = db.get_alarmas_historial()
        assert fila["codigo"] == "TARJETA_SIN_ACK"
    finally:
        h.detener()
