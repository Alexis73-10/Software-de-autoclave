"""T2 / P-2 (tanda 6): sonda Principal perdida en ciclo. NO se sigue con la
Referencia: el ciclo falla, se ventea solo por la LENTA (sin escalar ni
contrapresión), el operador reconoce y FALLA pasa a PREPARACION sin técnico,
y mientras la Principal no lea, el inicio queda bloqueado con "Sonda
principal sin lectura: llame a servicio". El estado seguro se libera por los
caminos de CIC-10 (la sonda vuelve a leer o se reasigna)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.state_machine import StateMachine
from tests.test_t3_sensores_ciclo import _ASIG_REF, _ciclo
from tests.test_t3_endpoints_sensores import entorno  # noqa: F401  (fixture)

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


# ── CicloState: la causa decide el protocolo ──────────────────────────────

def test_principal_perdido_ejecuta_el_protocolo_solo_lenta():
    ciclo, estado, _ = _ciclo(_ASIG_REF, {"temp_camara": None, "temp_ref": 120.0})
    ciclo._fases[0].update = MagicMock()
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    ciclo._protocolo.ejecutar.assert_called_once_with(solo_lenta=True)


def test_referencia_perdida_usa_el_protocolo_normal():
    ciclo, estado, _ = _ciclo(_ASIG_REF, {"temp_camara": 120.0, "temp_ref": None})
    ciclo._fases[0].update = MagicMock()
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    ciclo._protocolo.ejecutar.assert_called_once_with()


# ── ProtocoloFallo con solo_lenta ──────────────────────────────────────────

def _protocolo(modo, pres, liquido=False, temp=None):
    estado = SimpleNamespace(sensores_pres={"pres_camara": pres},
                             sensores_temp={"temp_camara": temp})
    params = {("descompresion", "modo"): modo,
              ("globals", "tipo_carga"): "liquido" if liquido else "solido"}
    cycle = SimpleNamespace(sensores=None,
                            get_param=lambda *a, default=None: params.get(a[:2], default))
    set_do = MagicMock()
    return ProtocoloFallo(estado, set_do, cycle, _Config(_CFG)), estado, set_do


@pytest.mark.parametrize("modo", [0, 1, 2, 3, 4, 5])
def test_solo_lenta_en_todos_los_modos_presurizada(modo):
    prot, estado, set_do = _protocolo(modo, pres=250.0)
    prot.ejecutar(solo_lenta=True)
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_not_called()
    set_do.descompresion_chaqueta_on.assert_not_called()
    for _ in range(5):
        prot.update()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_not_called()
    set_do.descompresion_chaqueta_on.assert_not_called()


def test_solo_lenta_no_escala_tras_el_timeout(monkeypatch):
    import time
    reloj = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    prot, estado, set_do = _protocolo(1, pres=250.0)
    prot.ejecutar(solo_lenta=True)
    reloj[0] += 10 * 3600
    prot.update()
    set_do.descompresion_rapida_on.assert_not_called()
    assert prot.solo_lenta is True


def test_solo_lenta_en_vacio_abre_aire_atmosferico():
    prot, estado, set_do = _protocolo(1, pres=40.0)
    prot.ejecutar(solo_lenta=True)
    prot.update()
    set_do.aire_admosferico_camara_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()


def test_bloqueado_motivo_mientras_el_principal_no_lee():
    prot, estado, _ = _protocolo(1, pres=250.0)
    prot.ejecutar(solo_lenta=True)
    assert "Principal" in prot.bloqueado_motivo
    estado.sensores_temp["temp_camara"] = 90.0
    assert prot.bloqueado_motivo is None


def test_reset_quita_solo_lenta():
    prot, _, _ = _protocolo(1, pres=250.0)
    prot.ejecutar(solo_lenta=True)
    prot.reset()
    assert prot.solo_lenta is False


# ── Estado seguro y FALLA ─────────────────────────────────────────────────

def test_estado_seguro_permite_salir_de_falla_solo_con_el_principal_perdido():
    estado = SimpleNamespace(sensores_pres={"pres_camara": 250.0}, sensores_temp={},
                             get_flag=lambda f: False)
    es = ProtocoloEstadoSeguro(estado, _Config(_CFG))
    prot = MagicMock(ejecutado=True, solo_lenta=True)
    es.iniciar(prot)
    assert es.permite_salir_de_falla is True
    es.requiere_confirmacion = True                    # tras un paro: no
    assert es.permite_salir_de_falla is False
    es2 = ProtocoloEstadoSeguro(estado, _Config(_CFG))
    es2.iniciar(MagicMock(ejecutado=True, solo_lenta=False))
    assert es2.permite_salir_de_falla is False
    assert ProtocoloEstadoSeguro(estado, _Config(_CFG)).permite_salir_de_falla is False


def _sm():
    estado = EstadoAutoclave()
    es = MagicMock()
    cycle = MagicMock(); cycle.copia.return_value = cycle; cycle.get_param.return_value = None
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=MagicMock(), cycle=cycle,
                      config=MagicMock(), estado_seguro=es)
    estado.set_machine_state(GlobalState.FALLA)
    estado.set_flag("RESET_FALLA", True)
    return sm, estado, es


def test_falla_pasa_a_preparacion_con_el_protocolo_del_principal_perdido():
    sm, estado, es = _sm()
    es.activo = True
    es.permite_salir_de_falla = True
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARACION


def test_falla_sigue_esperando_el_estado_seguro_en_los_demas_casos():
    sm, estado, es = _sm()
    es.activo = True
    es.permite_salir_de_falla = MagicMock()            # no es True: no cuenta
    sm.update()
    assert estado.get_machine_state() == GlobalState.FALLA


# ── /cycle/start ───────────────────────────────────────────────────────────

def test_start_principal_sin_lectura_rechaza_con_el_mensaje(entorno):  # noqa: F811
    client, ctx, srv, prog, _ = entorno
    ctx.estado.sensores_temp["temp_camara"] = None
    ctx.estado.get_flag.side_effect = lambda f: False      # tampoco listo: el motivo es la sonda
    r = client.post("/cycle/start")
    assert r.status_code == 409
    assert r.json()["codigo"] == "PRINCIPAL_SIN_LECTURA"
    assert "Sonda principal sin lectura: llame a servicio" in r.text


def test_start_principal_con_lectura_no_cambia(entorno):  # noqa: F811
    client, ctx, srv, prog, _ = entorno
    ctx.estado.get_flag.side_effect = lambda f: False
    r = client.post("/cycle/start")
    assert r.status_code == 409 and "PRINCIPAL_SIN_LECTURA" not in r.text


def test_principal_en_cero_cuenta_como_perdido():
    # SEN-01 de la revisión de T2
    ciclo, estado, _ = _ciclo(_ASIG_REF, {"temp_camara": 0, "temp_ref": 120.0})
    ciclo._fases[0].update = MagicMock()
    ciclo.run()
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    ciclo._protocolo.ejecutar.assert_called_once_with(solo_lenta=True)
