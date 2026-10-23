# tests/test_u10b_alarmas_idioma.py
#
# U10b (tanda 10, D10-1.4): las filas de alarma de Preciclo y del panel de la
# campana salían en español con la interfaz en inglés (hallazgo 1 de CAP9):
# AlarmListModel solo daba `description`, la descripción registrada en español.
# El DTO de /status ya trae `textos` por idioma (alarmas_i18n.por_idioma); el
# modelo expone ahora el rol `descripciones` ({idioma: descripción}) y la
# pantalla elige la del idioma vigente, con `description` de respaldo.

import pytest

pytest.importorskip("PySide6")

from autoclave.ui_qml.bridge.ui_bridge import AlarmListModel  # noqa: E402


def _fila(modelo, rol):
    roles = {bytes(n).decode(): r for r, n in modelo.roleNames().items()}
    return modelo.data(modelo.index(0, 0), roles[rol])


def test_rol_descripciones_toma_los_textos_por_idioma_del_dto():
    modelo = AlarmListModel()
    modelo.establecer([{"id": "SEN-06", "level": "FALLA", "description": "Sensor sin lectura",
                        "textos": {"es": {"titulo": "T", "descripcion": "Sensor sin lectura"},
                                   "en": {"titulo": "T", "descripcion": "Sensor without reading"}}}])
    assert _fila(modelo, "descripciones") == {"es": "Sensor sin lectura",
                                              "en": "Sensor without reading"}
    assert _fila(modelo, "description") == "Sensor sin lectura"


@pytest.mark.parametrize("textos", [None, "x", [], {"en": "no es dict"}, {"en": {"descripcion": 3}},
                                    {"en": {"titulo": "sin descripción"}}, {"en": {"descripcion": ""}}])
def test_textos_mal_formados_no_dan_descripcion(textos):
    modelo = AlarmListModel()
    modelo.establecer([{"id": "X", "description": "d", "textos": textos}])
    assert _fila(modelo, "descripciones") == {}
    assert _fila(modelo, "description") == "d"


def test_sin_textos_el_rol_queda_vacio():
    modelo = AlarmListModel()
    modelo.establecer([{"id": "X"}])
    assert _fila(modelo, "descripciones") == {}
