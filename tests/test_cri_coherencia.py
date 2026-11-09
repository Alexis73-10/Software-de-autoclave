"""CRI-03 (tanda 35): COHERENCIA_BRECHA_RECUPERACION (reemplaza a PAM-06):
brecha_segura_presion < presion_add_esterilizacion - 3."""
import logging
import types

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from tests.helpers import planta_vapor as pv


def _programa(**valores):
    return pv.programa_liquidos(**valores)      # add 15, brecha 1,5


def test_pam06_retirada():
    assert not hasattr(cp, "errores_brecha_presion")
    assert not hasattr(cp, "CODIGO_COHERENCIA_BRECHA_PRESION")


def test_regla_de_fabrica_cumple_y_limite():
    assert cp.errores_brecha_recuperacion(_programa().parameters) == []
    # add 11 -> límite 8: 7,9 cumple, 8 (igual) incumple
    assert cp.errores_brecha_recuperacion(
        _programa(esterilizacion__brecha_segura_presion=11.9).parameters) == []
    errores = cp.errores_brecha_recuperacion(
        _programa(esterilizacion__brecha_segura_presion=12.0).parameters)
    assert errores and cp.codigo_coherencia(errores) == cp.CODIGO_COHERENCIA_BRECHA_RECUPERACION


@pytest.mark.parametrize("malo", [float("nan"), float("inf"), None, "x", True])
def test_valores_no_evaluables_no_lanzan(malo):
    p = _programa().parameters
    p["esterilizacion"]["brecha_segura_presion"]["value"] = malo
    assert cp.errores_brecha_recuperacion(p) == []     # los marca el catálogo


def test_al_guardar_se_rechaza_brecha_o_add():
    prog = _programa()
    with pytest.raises(cp.ErrorCoherencia) as e:
        prog.set_param("esterilizacion", ["brecha_segura_presion"], 13.0)
    assert e.value.codigo == "COHERENCIA_BRECHA_RECUPERACION"
    assert prog.get_param("esterilizacion", "brecha_segura_presion") == 1.5
    # bajar la presión adicional deja la brecha sobre el límite
    with pytest.raises(cp.ErrorCoherencia):
        prog.set_param("esterilizacion", ["presion_add_esterilizacion"], 4.0)


def test_programa_ya_incoherente_no_bloquea_otros_y_se_corrige():
    prog = _programa(esterilizacion__brecha_segura_presion=13.0)
    prog.set_param("esterilizacion", ["tiempo_esterilizacion"], 20)
    with pytest.raises(cp.ErrorCoherencia):
        prog.set_param("esterilizacion", ["brecha_segura_presion"], 13.5)
    prog.set_param("esterilizacion", ["brecha_segura_presion"], 1.5)
    assert cp.errores_brecha_recuperacion(prog.parameters) == []


def test_al_cargar_no_rechaza_ni_migra():
    p = _programa(esterilizacion__brecha_segura_presion=13.0).parameters
    assert not any(e.startswith("Coherencia de brecha") for e in cp.errores_programa(p))
    assert not any(e.startswith("Coherencia de brecha") for e in cp.errores_coherencia(p))


def test_al_cargar_aviso_sis06_y_log_sin_migrar(caplog):
    from unittest.mock import MagicMock
    from autoclave.backend.context import BackendContext
    from autoclave.core.managers.cycle_manager import CycleManager
    caplog.set_level(logging.WARNING)
    prog = _programa(esterilizacion__brecha_segura_presion=13.0)
    cm = CycleManager.__new__(CycleManager)
    cm.cycles = {prog.id: prog}
    assert [c for c, _ in cm.incoherencias_brecha_recuperacion()] == [prog]
    CycleManager._registrar_advertencias(prog)
    assert "CRI-03" in caplog.text
    cm.migraciones_correctivas = lambda: []
    alarmas = MagicMock()
    BackendContext._avisar_migraciones_correctivas(
        types.SimpleNamespace(cycle_manager=cm, alarm_manager=alarmas))
    llamadas = [c for c in alarmas.activar.call_args_list if c.args[0] == "SIS-06"]
    assert len(llamadas) == 1
    assert llamadas[0].kwargs["parametro"] == "brecha_segura_presion"
    assert llamadas[0].kwargs["anterior"] == llamadas[0].kwargs["nuevo"] == "13"
    assert prog.get_param("esterilizacion", "brecha_segura_presion") == 13.0


def test_textos_y_mapeo_de_pantalla():
    from autoclave import i18n
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.controllers import parametros_ciclo_controller as pcc
    clave = "opciones.err_coherencia_brecha_recuperacion"
    for idioma in ("es", "en"):
        assert i18n.existe(clave, idioma)
        assert not i18n.existe("opciones.err_coherencia_brecha_presion", idioma)
    assert pcc.mensaje_de("COHERENCIA_BRECHA_RECUPERACION") == clave
    assert sesion_backend._CLAVES["COHERENCIA_BRECHA_RECUPERACION"] == clave
    assert "COHERENCIA_BRECHA_PRESION" not in sesion_backend._CLAVES


def test_programas_de_fabrica_cumplen():
    for ruta in sorted((pv.RAIZ / "src" / "autoclave" / "cycles").glob("*/*.json")):
        prog = pv._programa(ruta)
        assert cp.errores_brecha_recuperacion(prog.parameters) == [], ruta.name
