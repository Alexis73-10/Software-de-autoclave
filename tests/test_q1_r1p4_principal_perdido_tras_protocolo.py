"""Q1 / R1-P4 (tanda 7, decisión 1.3 de Cristian; SAF-05 de T2): si el
protocolo de fallo ya corrió por otra causa y después se pierde el Principal
(None o 0), se pasa igual a `solo_lenta`: criterio de P-2 sin importar el
orden. Vale con el resultado pendiente (CICLO) y en el estado seguro."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _protocolo(modo, pres=250.0, temp=130.0, liquido=False):
    estado = SimpleNamespace(sensores_pres={"pres_camara": pres},
                             sensores_temp={"temp_camara": temp})
    params = {("descompresion", "modo"): modo,
              ("globals", "tipo_carga"): "liquido" if liquido else "solido"}
    cycle = SimpleNamespace(sensores=None,
                            get_param=lambda *a, default=None: params.get(a[:2], default))
    set_do = MagicMock()
    return ProtocoloFallo(estado, set_do, cycle, _Config(_CFG)), estado, set_do


@pytest.mark.parametrize("perdido", [None, 0, float("nan")])
def test_modo_4_en_enfriamiento_pasa_a_solo_lenta(perdido):
    prot, estado, set_do = _protocolo(4, pres=150.0)   # bajo presion_camara_enfriamiento (200)
    prot.ejecutar()                       # otra causa (fallo de fase): modo 4
    prot.update()
    set_do.aire_comprimido_camara_on.assert_called()     # contrapresión en marcha
    assert prot.solo_lenta is False

    estado.sensores_temp["temp_camara"] = perdido
    set_do.reset_mock()
    prot.update()

    assert prot.solo_lenta is True
    set_do.aire_comprimido_camara_off.assert_called()
    set_do.agua_chaqueta_off.assert_called()
    set_do.descompresion_chaqueta_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_lenta_on.assert_called()
    for _ in range(5):
        prot.update()
    set_do.aire_comprimido_camara_on.assert_not_called()
    set_do.descompresion_chaqueta_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()


def test_modo_1_con_la_rapida_abierta_pasa_a_la_lenta():
    prot, estado, set_do = _protocolo(1)
    prot.ejecutar()
    set_do.descompresion_rapida_on.assert_called()

    estado.sensores_temp["temp_camara"] = None
    set_do.reset_mock()
    prot.update()

    assert prot.solo_lenta is True
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()


def test_escalado_por_timeout_se_deshace(monkeypatch):
    import time
    reloj = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    prot, estado, set_do = _protocolo(2)
    prot.ejecutar()
    reloj[0] += 10 * 3600
    prot.update()                         # escala a chaqueta + rápida
    set_do.descompresion_rapida_on.assert_called()

    estado.sensores_temp["temp_camara"] = 0
    set_do.reset_mock()
    prot.update()
    reloj[0] += 10 * 3600
    prot.update()

    assert prot.solo_lenta is True
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_chaqueta_on.assert_not_called()


def test_es_un_enclavamiento_aunque_vuelva_la_lectura():
    prot, estado, set_do = _protocolo(1)
    prot.ejecutar()
    estado.sensores_temp["temp_camara"] = None
    prot.update()
    estado.sensores_temp["temp_camara"] = 130.0
    set_do.reset_mock()
    prot.update()
    assert prot.solo_lenta is True
    set_do.descompresion_rapida_on.assert_not_called()


def test_con_principal_leyendo_no_cambia_nada():
    prot, _, set_do = _protocolo(1)
    prot.ejecutar()
    for _ in range(3):
        prot.update()
    assert prot.solo_lenta is False


def test_sin_presion_igual_pasa_a_solo_lenta():
    # update() retorna temprano sin presión; el cambio de modo va antes
    prot, estado, set_do = _protocolo(4)
    prot.ejecutar()
    estado.sensores_pres["pres_camara"] = None
    estado.sensores_temp["temp_camara"] = None
    prot.update()
    assert prot.solo_lenta is True
    set_do.aire_comprimido_camara_off.assert_called()


# ── estado seguro (fuera de CICLO, tras el reconocimiento) ─────────────────

def _estado_seguro(prot, estado):
    estado.get_flag = lambda f: False
    eventos = []
    es = ProtocoloEstadoSeguro(estado, _Config(_CFG),
                               al_evento=lambda e, d: eventos.append((e, d)))
    es.iniciar(prot)
    return es, eventos


def test_estado_seguro_pasa_a_solo_lenta_y_lo_registra():
    prot, estado, set_do = _protocolo(4)
    prot.ejecutar()                       # cancelación / fallo de fase
    es, eventos = _estado_seguro(prot, estado)
    es.update()
    assert es.permite_salir_de_falla is False

    estado.sensores_temp["temp_camara"] = None
    es.update()

    assert prot.solo_lenta is True
    assert ("estado_seguro_solo_lenta", {"motivo": "sensor Principal sin lectura"}) in eventos
    # criterio de P-2: FALLA puede pasar a PREPARACION sin técnico
    assert es.permite_salir_de_falla is True
    assert es.bloqueado_motivo is not None          # CIC-10 mientras no lea
    es.update()
    assert [e for e, _ in eventos].count("estado_seguro_solo_lenta") == 1


# ── CicloState con el resultado pendiente ─────────────────────────────────

def test_ciclo_con_fallo_pendiente_pasa_a_solo_lenta():
    from tests.test_t3_sensores_ciclo import _ASIG_REF, _ciclo
    ciclo, estado, _ = _ciclo(_ASIG_REF, {"temp_camara": 130.0, "temp_ref": 120.0})
    ciclo._protocolo = ProtocoloFallo(estado, MagicMock(), ciclo.cycle, ciclo.config)
    estado.sensores_pres["pres_camara"] = 250.0
    ciclo._protocolo.ejecutar()                  # p. ej. una puerta
    ciclo._resultado_pendiente = "FALLO"
    ciclo.run()
    assert ciclo._protocolo.solo_lenta is False

    estado.sensores_temp["temp_camara"] = None
    ciclo.run()
    assert ciclo._protocolo.solo_lenta is True
