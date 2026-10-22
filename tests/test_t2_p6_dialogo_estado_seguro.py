"""T2 / P-6 (tanda 6): tras un paro con el ciclo terminando, el CONFIRMAR del
ciclo también confirma el estado seguro; la pantalla muestra antes el texto
de §15.2 (verificar que no hay fugas)."""

import json
from pathlib import Path

from autoclave.state_machine.states.ciclo import CicloResultado
from autoclave.ui_qml.bridge.ui_bridge import UiBridge
from tests.test_t5_estado_seguro import _ciclo

_RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"


def test_ciclo_publica_que_el_ack_confirma_el_estado_seguro():
    flags = {}
    ciclo, _ = _ciclo(flags)
    assert ciclo.ack_confirma_estado_seguro is False
    ciclo._resultado_pendiente = CicloResultado.FALLO
    ciclo._paro_en_espera = True
    flags["PARO_EMERGENCIA"] = True
    assert ciclo.ack_confirma_estado_seguro is False      # con el paro activo no se confirma
    flags["PARO_EMERGENCIA"] = False
    assert ciclo.ack_confirma_estado_seguro is True
    ciclo._paro_en_espera = False
    assert ciclo.ack_confirma_estado_seguro is False


def test_puente_expone_la_marca():
    d = UiBridge._seguridad_de({"estado_seguro": {"activo": False,
                                                  "ack_confirma_estado_seguro": True}})
    assert d["es_ack_confirma"] is True
    assert UiBridge._seguridad_de({})["es_ack_confirma"] is False


def test_texto_de_15_2_en_es_y_en():
    for idioma, palabra in (("es", "fuga"), ("en", "leak")):
        datos = json.loads((_RAIZ / "i18n" / f"{idioma}.json").read_text(encoding="utf-8"))
        assert palabra in datos["ciclo"]["confirmar_estado_seguro_texto"].lower()


def test_pantalla_abre_el_dialogo_antes_de_confirmar():
    qml = (_RAIZ / "ui_qml" / "qml" / "Pantallas" / "PantallaCicloEnCurso.qml").read_text(
        encoding="utf-8")
    assert "ackConfirmaEstadoSeguro" in qml and "dialogoEstadoSeguro.abrir()" in qml
    assert 'I18n.t("ciclo.confirmar_estado_seguro_texto"' in qml
