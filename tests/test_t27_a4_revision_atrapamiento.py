# Tanda 27 (A4, revisión; DECISIÓN SIN CONFIRMAR, HAZ-IO-07): con las salidas
# de puerta como interruptor sin tope,
# (1) el lazo apaga cerrar_puerta_N en el mismo tick si aparece el
#     atrapamiento o si las DI dejan de estar vigentes (solo apaga; la
#     inversión a abrir no se enciende sola);
# (2) el enclavamiento abrir/cerrar no enciende un sentido si el enlace no
#     acepta el apagado del contrario (409 salida_prueba_opuesta_sin_apagar);
# (3) el sentido contrario se toma de door.do.
from unittest.mock import MagicMock

import pytest

from autoclave import i18n
from autoclave.core.runtime import salidas_prueba_seguridad as sps
from autoclave.ui_qml import sesion_backend
from tests.test_io_endpoints import (entorno, _puerta_avanzada, _canal, _llamadas,  # noqa: F401
                                     _DI_ATRAP, _DI_CERRADA, _DI_ABIERTA)
from tests.test_t17_s3_esg import _loop_vivo, _en_prueba, _apagadas

_ATRAP = "atrapamiento_puerta_1"


def _puerta_lazo():
    d = MagicMock()
    d.name = "Puerta 1"
    d.di = {"cerrada": "puerta_1_cerrada", "atrapamiento": _ATRAP}
    d.do = {"abrir": _canal("abrir_puerta_1"), "cerrar": _canal("cerrar_puerta_1")}
    return d


def _lazo_con_cierre():
    loop = _loop_vivo()
    loop.doors = [_puerta_lazo()]
    loop.estado.sensores_di[_ATRAP] = 1                    # NC: 1 = libre
    _en_prueba(loop)
    loop.estado.salidas_do["cerrar_puerta_1"] = 1           # cerrando (interruptor)
    return loop


# ── (1) vigilancia por tick ────────────────────────────────────────────────

@pytest.mark.req("HAZ-IO-07")
def test_sin_atrapamiento_el_cierre_no_se_toca():
    loop = _lazo_con_cierre()
    loop._tick()
    assert _canal("cerrar_puerta_1") not in _apagadas(loop)
    assert loop.avisos_corte_prueba == []


@pytest.mark.req("HAZ-IO-07")
def test_atrapamiento_durante_el_cierre_lo_apaga_en_el_tick():
    loop = _lazo_con_cierre()
    loop._tick()
    loop.estado.sensores_di[_ATRAP] = 0                     # atrapada
    loop.set_do.reset_mock()
    loop._tick()
    assert _canal("cerrar_puerta_1") in _apagadas(loop)
    # la inversión no se enciende sola
    encendidas = {c.args[0] for c in loop.set_do.set_output.call_args_list if c.args[1] is True}
    assert _canal("abrir_puerta_1") not in encendidas
    [aviso] = loop.avisos_corte_prueba
    assert aviso["salida"] == "cerrar_puerta_1" and aviso["codigo"] == sps.CIERRE_ATRAPAMIENTO
    assert aviso["aviso"] == "io.ui.aviso_cierre_cortado_atrapamiento"
    loop._tick()                                            # una sola vez por corte
    assert len(loop.avisos_corte_prueba) == 1


@pytest.mark.req("HAZ-IO-07")
def test_atrapamiento_sin_lectura_falla_cerrada():
    loop = _lazo_con_cierre()
    del loop.estado.sensores_di[_ATRAP]
    loop._tick()
    assert _canal("cerrar_puerta_1") in _apagadas(loop)


@pytest.mark.req("HAZ-IO-07")
def test_di_no_vigentes_apagan_el_cierre(monkeypatch):
    """Sin datos vigentes (p. ej. dentro de la tolerancia de desconexión, antes
    de que el paro cancele el modo prueba) el cierre se apaga igual."""
    from autoclave.services.domain.loop.control_loop import ControlLoop
    loop = _lazo_con_cierre()
    monkeypatch.setattr(ControlLoop, "datos_vigentes", property(lambda self: False))
    loop._vigilar_salidas_prueba_seguridad()
    assert _canal("cerrar_puerta_1") in _apagadas(loop)
    assert any(a["codigo"] == sps.CIERRE_SIN_DATOS and a["salida"] == "cerrar_puerta_1"
               for a in loop.avisos_corte_prueba)


def test_puertas_sin_mapa_no_se_evaluan():
    assert sps.cierres_a_cortar([MagicMock()], {}, False) == {}
    d = _puerta_lazo()
    d.di = {"cerrada": "puerta_1_cerrada"}                  # sin sensor de atrapamiento
    assert sps.cierres_a_cortar([d], {}, True) == {}
    assert sps.cierres_a_cortar([d], {}, False) == {_canal("cerrar_puerta_1"): sps.CIERRE_SIN_DATOS}


def test_cierres_no_entran_en_salidas_prueba_bloqueadas():
    """La ruta conserva la inversión de D-ES-16: el corte vive solo en el lazo."""
    loop = _lazo_con_cierre()
    loop.estado.sensores_di[_ATRAP] = 0
    assert "cerrar_puerta_1" not in loop.salidas_prueba_bloqueadas()


@pytest.mark.req("ESG-02")
def test_esg02_sigue_igual_con_la_vigilancia_nueva():
    loop = _lazo_con_cierre()
    loop.estado.salidas_do["vapor_camara"] = 1
    loop.estado.sensores_di["puerta_1_cerrada"] = 0
    loop._tick()
    assert _canal("vapor_camara") in _apagadas(loop)
    assert _canal("cerrar_puerta_1") not in _apagadas(loop)


def test_avisos_con_texto_es_en():
    for codigo in (sps.CIERRE_ATRAPAMIENTO, sps.CIERRE_SIN_DATOS):
        clave = sps.AVISOS_CORTE[codigo]
        assert i18n.existe(clave, "es") and i18n.existe(clave, "en"), clave


# ── (2) apagado del sentido contrario sin confirmar ────────────────────────

def _falla_off_de(ctx, canal):
    ctx.setdo.set_output.side_effect = lambda c, v: not (c == canal and v is False)


@pytest.mark.parametrize("orden,opuesta", [("abrir_puerta_1", "cerrar_puerta_1"),
                                           ("cerrar_puerta_1", "abrir_puerta_1")])
def test_off_de_la_opuesta_no_confirmado_409_y_no_enciende(entorno, orden, opuesta):
    client, ctx, _ = entorno
    _falla_off_de(ctx, _canal(opuesta))
    r = client.patch(f"/io/test/output/{orden}", json={"value": True})
    assert r.status_code == 409
    assert sps_codigo(r) == "salida_prueba_opuesta_sin_apagar"
    assert (_canal(orden), True) not in _llamadas(ctx)


def test_inversion_con_off_del_cierre_no_confirmado_no_abre(entorno):
    client, ctx, _ = entorno
    ctx.doors = [_puerta_avanzada()]
    ctx.estado.sensores_di = {_DI_CERRADA: 1, _DI_ABIERTA: 0, _DI_ATRAP: 0}
    _falla_off_de(ctx, _canal("cerrar_puerta_1"))
    r = client.patch("/io/test/output/cerrar_puerta_1", json={"value": True})
    assert r.status_code == 409
    assert sps_codigo(r) == "salida_prueba_opuesta_sin_apagar"
    assert (_canal("abrir_puerta_1"), True) not in _llamadas(ctx)


def test_codigo_con_texto_es_en():
    clave = sesion_backend.clave_mensaje("salida_prueba_opuesta_sin_apagar")
    assert clave == "io.err_opuesta_sin_apagar"
    assert i18n.existe(clave, "es") and i18n.existe(clave, "en")


def sps_codigo(r):
    cuerpo = r.json()
    detalle = cuerpo.get("detail")
    if isinstance(detalle, dict):
        return detalle.get("codigo")
    return cuerpo.get("codigo")


# ── (3) sentido contrario desde door.do ────────────────────────────────────

def test_opuesta_tomada_de_door_do(entorno):
    """Una puerta cuyo cierre está en otro canal (p. ej. reasignado): se apaga
    ese canal, no el del nombre."""
    client, ctx, _ = entorno
    d = _puerta_avanzada()
    d.do = {"abrir": _canal("abrir_puerta_1"), "cerrar": _canal("bomba_vacio")}
    ctx.doors = [d]
    r = client.patch("/io/test/output/abrir_puerta_1", json={"value": True})
    assert r.status_code == 200, r.text
    assert r.json()["apagada_por_enclavamiento"] == "bomba_vacio"
    assert _llamadas(ctx) == [(_canal("bomba_vacio"), False), (_canal("abrir_puerta_1"), True)]
