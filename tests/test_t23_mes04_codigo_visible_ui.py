# tests/test_t23_mes04_codigo_visible_ui.py
#
# Tanda 23 (MES-04, decisiones_tanda_23.md): en la interfaz un código de
# alarma TARJETA_<x> se muestra MODULO_ES_<x> (codigo_visible()), sin cambiar
# el código guardado ni la clave de reconocimiento (id = CODIGO|origen).
#   - AlarmListModel: roles idVisible y codigoVisible; id y codigo intactos.
#   - fin_de_ciclo.armar: línea meta, títulos de respaldo y motivo.
#   - Ticket de alarmas activas (ui_pyside) y campo Motivo del PDF.

import pytest

from autoclave.ui_qml.domain import fin_de_ciclo

pytestmark = pytest.mark.req("MES-04")

_SIN_ACK = {"id": "TARJETA_SIN_ACK|operacion", "codigo": "TARJETA_SIN_ACK", "level": "FALLA",
            "titulo": "", "description": "", "aparecida": "2026-10-29T10:00:00",
            "estado": "ACTIVA"}


def test_modelo_muestra_modulo_es_sin_tocar_id_ni_codigo():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.bridge.ui_bridge import AlarmListModel
    m = AlarmListModel()
    m.establecer([_SIN_ACK, {"id": "SEN-02|preparado", "codigo": "SEN-02", "level": "FALLA"}])
    f = m.filas()
    assert f[0]["codigoVisible"] == "MODULO_ES_SIN_ACK"
    assert f[0]["idVisible"] == "MODULO_ES_SIN_ACK|operacion"
    # lo guardado no cambia: reconocimiento y comparaciones siguen igual
    assert f[0]["codigo"] == "TARJETA_SIN_ACK" and f[0]["id"] == "TARJETA_SIN_ACK|operacion"
    assert f[1]["codigoVisible"] == "SEN-02" and f[1]["idVisible"] == "SEN-02|preparado"
    roles = {bytes(n).decode() for n in m.roleNames().values()}
    assert {"idVisible", "codigoVisible", "id", "codigo"} <= roles
    d = m.detalle("TARJETA_SIN_ACK|operacion")
    assert d["codigoVisible"] == "MODULO_ES_SIN_ACK"


def test_fin_de_ciclo_meta_y_titulo_con_codigo_visible():
    term = {"tipo": "fallo", "codigo": "TARJETA_SIN_ACK", "valores": {}, "motivo": "",
            "fase": "esterilizacion", "hora_fin": "2026-10-29T10:05:00",
            "cancelado_por": None, "observaciones": []}
    alarmas = [{"codigo": "TARJETA_SIN_ACK", "nivel": "ALARMA", "titulo": "", "descripcion": "",
                "valores": {}, "aparecida": "2026-10-29T10:00:00", "resuelta": None}]
    for idioma in ("es", "en"):
        d = fin_de_ciclo.armar(fin_de_ciclo.normalizar_terminacion(term, "fallo"),
                               fin_de_ciclo.normalizar_alarmas(alarmas), idioma)
        assert "MODULO_ES_SIN_ACK" in d["causa"]["meta"]
        assert "MODULO_ES_SIN_ACK" in d["alarmas"][0]["meta"]
        textos = repr(d)
        assert "TARJETA_" not in textos


def test_fin_de_ciclo_codigo_desconocido_y_motivo_guardado():
    term = {"tipo": "fallo", "codigo": "TARJETA_INVENTADA", "valores": {},
            "motivo": "TARJETA_INVENTADA · algo", "fase": None, "hora_fin": "",
            "cancelado_por": None, "observaciones": []}
    d = fin_de_ciclo.armar(fin_de_ciclo.normalizar_terminacion(term, "fallo"), [], "es")
    assert d["causa"]["descripcion"] == "MODULO_ES_INVENTADA · algo"
    assert "MODULO_ES_INVENTADA" in d["causa"]["meta"]


def test_con_codigo_visible_no_toca_otros_codigos():
    assert fin_de_ciclo.con_codigo_visible("SEN-02 · x", "SEN-02") == "SEN-02 · x"
    assert fin_de_ciclo.con_codigo_visible(None, "TARJETA_SIN_ACK") is None


def test_ticket_de_alarmas_activas_con_codigo_visible():
    pytest.importorskip("PySide6")
    from autoclave.ui_pyside.views.impresion_menu import _build_alarms_ticket_lines
    texto = "\n".join(_build_alarms_ticket_lines([
        {"codigo": "TARJETA_SIN_ACK", "titulo": "El módulo E/S no confirma los comandos",
         "aparecida": "2026-10-29T10:00:00", "origen": "operacion"},
        {"id": "TARJETA_WATCHDOG|operacion", "level": "FALLA"},
    ]))
    assert "MODULO_ES_SIN_ACK - El módulo E/S" in texto
    assert "ID: MODULO_ES_WATCHDOG|operacion" in texto
    assert "TARJETA_" not in texto


def test_motivo_del_pdf_con_codigo_visible():
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    campos = AccionesCiclos._campo_motivo({"codigo_fallo": "TARJETA_SIN_ACK", "valores_fallo": None,
                                           "motivo_fallo": "TARJETA_SIN_ACK · algo"})
    assert campos and "MODULO_ES_SIN_ACK" in campos[0][1] and "TARJETA_" not in campos[0][1]
