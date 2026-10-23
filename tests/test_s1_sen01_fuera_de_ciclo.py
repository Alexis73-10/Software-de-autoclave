"""S1 (tanda 8, D8-1.3 y 1.4): transductor de presión sin lectura FUERA de
ciclo. La alarma es la propia ("Sensor de presión de cámara sin lectura:
llame a servicio", SEN-06; chaqueta SEN-07), el equipo no queda listo, el
inicio se rechaza con ese texto y "NO ABRIR" se mantiene (sin presión no se
confirma la cámara segura). Solo los canales habilitados en io_enabled."""

import math
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import camara_segura
from autoclave.core.runtime import presion_sin_lectura as psl
from autoclave.state_machine.alarms.catalogo import nombre_legible
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from autoclave.ui_qml.domain import pantalla_ciclo
from tests.alarmas_helpers import activaciones, codigos_activados, codigos_resueltos
from tests.test_adenda_estados import _make
from tests.test_t3_endpoints_sensores import entorno  # noqa: F401  (fixture)

_ESTADOS = [preparacion_state, preparado_state]


@pytest.fixture
def io_completo(monkeypatch):
    monkeypatch.setattr(psl, "_ai_habilitadas", lambda: ("pres_camara", "pres_chaqueta"))


@pytest.fixture
def io_sin_chaqueta(monkeypatch):
    monkeypatch.setattr(psl, "_ai_habilitadas", lambda: ("pres_camara",))


# ── Alarma propia en PREPARACION / PREPARADO ───────────────────────────────

@pytest.mark.parametrize("clase", _ESTADOS)
@pytest.mark.parametrize("valor", [None, math.nan])
def test_camara_sin_lectura_activa_sen06_y_no_queda_lista(io_completo, clase, valor):
    obj, am, _ = _make(clase, None, pres_camara=valor)
    assert obj.verificar_sensores() is False
    legible = nombre_legible("pres_camara")
    act = [(c, o) for c, o, _ in activaciones(am)]
    assert ("SEN-06", legible) in act
    # no se duplica con la genérica de lectura inválida para ese canal
    assert ("SEN-01", legible) not in act


@pytest.mark.parametrize("clase", _ESTADOS)
def test_chaqueta_sin_lectura_activa_sen07(io_completo, clase):
    obj, am, _ = _make(clase, None, pres_chaqueta=None)
    assert obj.verificar_sensores() is False
    assert "SEN-07" in codigos_activados(am)


@pytest.mark.parametrize("clase", _ESTADOS)
def test_con_lectura_se_resuelven_sen06_y_sen07(io_completo, clase):
    obj, am, _ = _make(clase, None)
    assert obj.verificar_sensores() is True
    resueltos = codigos_resueltos(am)
    assert "SEN-06" in resueltos and "SEN-07" in resueltos
    assert "SEN-06" not in codigos_activados(am)


@pytest.mark.parametrize("clase", _ESTADOS)
def test_presion_cero_con_lectura_sigue_siendo_sen01(io_completo, clase):
    """0 con lectura no es "sin lectura" (la detección es del convertidor):
    conserva la alarma de lectura inválida de siempre."""
    obj, am, _ = _make(clase, None, pres_camara=0.0)
    assert obj.verificar_sensores() is False
    assert "SEN-01" in codigos_activados(am)
    assert "SEN-06" not in codigos_activados(am)


@pytest.mark.parametrize("clase", _ESTADOS)
def test_chaqueta_no_habilitada_no_usa_sen07(io_sin_chaqueta, clase):
    obj, am, _ = _make(clase, None, pres_chaqueta=None)
    obj.verificar_sensores()
    assert "SEN-07" not in codigos_activados(am)


@pytest.mark.parametrize("clase", _ESTADOS)
def test_camara_sin_lectura_run_no_queda_lista(io_completo, clase):
    obj, am, set_do = _make(clase, None, pres_camara=None)
    assert obj.run() is False
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_catalogo_sen06_bloquea_inicio_con_el_texto_de_servicio():
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    d = CATALOGO["SEN-06"]
    assert d.bloquea_inicio is True
    assert "Sensor de presión de cámara sin lectura: llame a servicio" in d.renderizar({})
    assert CATALOGO["SEN-07"].bloquea_inicio is True


# ── "NO ABRIR" se mantiene ──────────────────────────────────────────────────

class _Cfg(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def test_sin_presion_de_camara_no_es_segura_no_abrir():
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": None}
    estado.sensores_temp = {"temp_camara": 25.0}
    cfg = _Cfg(presion_admosferica=101.3, rango_presion_atm=10.0, temp_max_apertura=80.0)
    segura, motivo = camara_segura.evaluar(estado, cfg, None)
    assert segura is False
    assert getattr(motivo, "codigo", None) == "sin_presion_camara"


# ── /cycle/start ───────────────────────────────────────────────────────────

def test_start_camara_sin_lectura_rechaza_con_el_mensaje(entorno, io_completo):  # noqa: F811
    client, ctx, srv, prog, _ = entorno
    ctx.estado.sensores_pres = {"pres_camara": None, "pres_chaqueta": 300.0}
    r = client.post("/cycle/start")
    assert r.status_code == 409
    assert r.json()["codigo"] == "PRESION_CAMARA_SIN_LECTURA"
    assert "Sensor de presión de cámara sin lectura: llame a servicio" in r.text
    ctx.estado.set_flag.assert_not_called()


def test_start_chaqueta_sin_lectura_rechaza(entorno, io_completo):  # noqa: F811
    client, ctx, srv, prog, _ = entorno
    ctx.estado.sensores_pres = {"pres_camara": 101.0, "pres_chaqueta": None}
    r = client.post("/cycle/start")
    assert r.status_code == 409
    assert r.json()["codigo"] == "PRESION_CHAQUETA_SIN_LECTURA"


def test_start_chaqueta_no_habilitada_no_rechaza_por_ella(entorno, io_sin_chaqueta):  # noqa: F811
    client, ctx, srv, prog, _ = entorno
    ctx.estado.sensores_pres = {"pres_camara": 101.0, "pres_chaqueta": None}
    r = client.post("/cycle/start")
    assert "PRESION_CHAQUETA_SIN_LECTURA" not in r.text


def test_start_sin_lectura_tiene_prioridad_sobre_no_listo(entorno, io_completo):  # noqa: F811
    client, ctx, srv, prog, _ = entorno
    ctx.estado.sensores_pres = {"pres_camara": None, "pres_chaqueta": 300.0}
    ctx.estado.get_flag.side_effect = lambda f: False
    r = client.post("/cycle/start")
    assert r.status_code == 409
    assert r.json()["codigo"] == "PRESION_CAMARA_SIN_LECTURA"


def test_start_con_presiones_validas_inicia(entorno, io_completo):  # noqa: F811
    client, ctx, srv, prog, _ = entorno
    ctx.estado.sensores_pres = {"pres_camara": 101.0, "pres_chaqueta": 300.0}
    r = client.post("/cycle/start")
    assert r.status_code == 200, r.text


# ── UI: sin lectura nunca se pinta un número ───────────────────────────────

def test_ui_presion_sin_lectura_no_muestra_numero():
    assert pantalla_ciclo.formatear_presion(None) == pantalla_ciclo.SIN_DATO
    assert not any(ch.isdigit() for ch in pantalla_ciclo.formatear_presion(None))


def test_start_error_al_evaluar_la_presion_no_inicia(entorno, monkeypatch):  # noqa: F811
    client, ctx, srv, prog, _ = entorno

    def _explota(*a, **k):
        raise RuntimeError("io")
    monkeypatch.setattr(psl, "rechazo_inicio", _explota)
    r = client.post("/cycle/start")
    assert r.status_code == 409
    assert r.json()["codigo"] == "PRESION_NO_VERIFICABLE"
    ctx.estado.set_flag.assert_not_called()
