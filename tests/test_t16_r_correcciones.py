# tests/test_t16_r_correcciones.py
#
# Etapa R (tanda 16): pruebas de las correcciones de los hallazgos de la
# revisión (V16-s1-01, s1-02/s2-01/s3-02, s1-03, s3-01, s3-03/s4-01, s3-07,
# s5-02).

from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.installation.profile import MODO_CHAQUETA
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.precalentamiento import PrecalentamientoFase
from autoclave.state_machine.cycle_phases.secado import SecadoFase
from autoclave.state_machine.states.ciclo import CicloResultado
from tests.helpers import t12_e12_apoyo as ap
from tests.test_t16_integracion import TECHO_EST, _armar, _calentar, _hasta_fase, _tick

pytestmark = pytest.mark.req("T16-R")


# ── V16-s1-02 / s2-01 / s3-02: sin suministro de vapor la fase no abre la chaqueta

@pytest.mark.parametrize("fase", ["CALENTAMIENTO", "ESTERILIZACION"])
def test_sin_suministro_la_fase_no_reabre_la_chaqueta(monkeypatch, fase):
    ciclo, estado, salidas, am, reloj = _armar(monkeypatch)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    if fase == "ESTERILIZACION":
        _calentar(ciclo, estado, salidas, reloj)
        temp, pres = 134.3, p_saturacion_kpa(134.3)
    else:
        temp, pres = 110.0, p_saturacion_kpa(110.0)
    _tick(ciclo, reloj, estado, temp=temp, pres=pres)
    estado.sensores_di["vapor_suministro"] = 0
    salidas.ordenes.clear()
    for _ in range(4):
        _tick(ciclo, reloj, estado, temp=temp, pres=pres)
        assert not salidas.on("vapor_chaqueta")
    assert ("vapor_chaqueta", True) not in salidas.ordenes
    assert any(i.codigo == "SUM-06" for i in am.activas())
    assert estado.inhibir_vapor_chaqueta is True
    estado.sensores_di["vapor_suministro"] = 1
    _tick(ciclo, reloj, estado, temp=temp, pres=pres)
    assert estado.inhibir_vapor_chaqueta is False


# ── V16-s3-01: PRECALENTAMIENTO y SECADO respetan el corte ─────────────────

def _estado(inhibir):
    e = MagicMock()
    e.sensores_pres = {"pres_chaqueta": 100.0, "pres_camara": 100.0}
    e.sensores_temp = {"temp_camara": 100.0}
    e.inhibir_vapor_chaqueta = inhibir
    return e


def _cycle(valores):
    c = MagicMock()
    c.get_param.side_effect = lambda *k, default=None: valores.get(k[-1], default)
    return c


@pytest.mark.parametrize("inhibir,esperado", [(True, "vapor_chaqueta_off"),
                                              (False, "vapor_chaqueta_on")])
def test_precalentamiento_respeta_el_corte(inhibir, esperado):
    set_do = MagicMock()
    f = PrecalentamientoFase(_estado(inhibir), set_do,
                             _cycle({"presion_precalentamiento": 300, "tiempo_precalentamiento": 60,
                                     "timeout_precalentamiento": 30}),
                             MagicMock(), MagicMock(), MagicMock())
    f.reset()
    assert f.update() == FaseResult.EN_CURSO
    ordenes = [c[0] for c in set_do.mock_calls if c[0].startswith("vapor_chaqueta")]
    assert esperado in ordenes
    if inhibir:
        assert "vapor_chaqueta_on" not in ordenes


@pytest.mark.parametrize("inhibir", [True, False])
def test_secado_respeta_el_corte(inhibir):
    set_do = MagicMock()
    f = SecadoFase(_estado(inhibir), set_do,
                   _cycle({"presion_chaqueta_secado": 200, "rango_chaqueta_secado": 30}),
                   MagicMock(), MagicMock(), MagicMock())
    f.reset()
    f._tick_chaqueta()
    ordenes = [c[0] for c in set_do.mock_calls if c[0].startswith("vapor_chaqueta")]
    assert ordenes == (["vapor_chaqueta_off"] if inhibir else ["vapor_chaqueta_on"])


# ── V16-s1-01: excursión cerrada, debounce desde cero ─────────────────────

def test_lectura_suelta_tras_cerrar_una_excursion_no_se_confirma(monkeypatch):
    f, estado, _, reloj = ap.fase(monkeypatch, sensores=ap.ASIG_REF, refs={"temp_ref": 134.2})
    f.update()
    for _ in range(14):                         # excursión real de 7 s: se confirma
        ap.poner(estado, temp_ref=133.0)
        reloj.avanzar(0.5)
        f.update()
    assert f.exposicion_detenida
    ap.poner(estado, temp_ref=134.2)            # vuelve: reinicio 1
    reloj.avanzar(0.5)
    f.update()
    assert not f.exposicion_detenida and f.reinicios_exposicion == 1
    for _ in range(6):                          # parpadeo en el borde 3 s
        ap.poner(estado, temp_ref=133.0)
        reloj.avanzar(0.5)
        assert f.update() == FaseResult.EN_CURSO
        ap.poner(estado, temp_ref=134.2)
        reloj.avanzar(0.5)
        assert f.update() == FaseResult.EN_CURSO
    assert f.reinicios_exposicion == 1          # antes: cada lectura suelta sumaba un reinicio


# ── V16-s1-03: sin Principal pero con presión, el aislamiento entra ───────

def test_sin_principal_con_presion_alta_aisla(monkeypatch):
    f, estado, set_do, reloj = ap.fase(monkeypatch)
    estado.modo_vapor = MODO_CHAQUETA
    estado.inhibir_vapor_chaqueta = False
    f.update()
    ap.poner(estado, pres=TECHO_EST + 1.0)
    estado.sensores_temp["temp_camara"] = None
    set_do.reset_mock()
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO
    ordenes = [c[0] for c in set_do.mock_calls if c[0].startswith("vapor_")]
    assert "vapor_camara_off" in ordenes and "vapor_camara_on" not in ordenes
    assert estado.aislamiento_camara.aislado


# ── V16-s3-07: CICLO no confirma un NO CONFORME sin reconocimiento ─────────

def test_ciclo_ignora_la_confirmacion_sin_reconocimiento(monkeypatch):
    ciclo, estado, _salidas, _am, reloj = _armar(monkeypatch)
    ciclo._no_conforme = True
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    estado.set_flag("CICLO_CONFIRMADO", True)
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.get_flag("CICLO_CONFIRMADO") is False
    estado.no_conforme_reconocido = True
    estado.set_flag("CICLO_CONFIRMADO", True)
    assert ciclo.run() == CicloResultado.COMPLETADO


# ── V16-s3-03 / s4-01: bajar un alivio en caliente revalida los programas ──

@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.core.runtime.config_idioma import ConfigIdioma
    from autoclave.core.runtime.unidades import ConfigUnidades
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    c = ConfigManager(); c.load_config(); c.vincular_bd(ctx.db)
    ctx.config_manager = c
    ctx.config_idioma = ConfigIdioma(tmp_path / "idioma.json")
    ctx.config_unidades = ConfigUnidades(tmp_path / "unidades.json")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    yield TestClient(srv.app), srv, ctx, cabecera
    ctx.db.close()


def test_cambiar_un_limite_revalida_los_programas(api):
    client, srv, ctx, cab = api
    ctx.cycle_manager.revalidar_programas.reset_mock()
    r = client.patch("/global_params/presion_alivio_camara", json={"valor": 380},
                     headers=cab(srv, "ingeniero"))
    assert r.status_code == 200, r.text
    ctx.cycle_manager.revalidar_programas.assert_called_once()
    ctx.cycle_manager.revalidar_programas.reset_mock()
    r = client.patch("/global_params/timeout_puerta", json={"valor": 90},
                     headers=cab(srv, "ingeniero"))
    assert r.status_code == 200
    ctx.cycle_manager.revalidar_programas.assert_not_called()


# ── V16-s5-02: la reimpresión de la app de ajustes lleva NO CONFORME ──────

def test_reimpresion_pyside_lleva_no_conforme():
    pytest.importorskip("PySide6")
    import json
    from autoclave.ui_pyside.views.ciclos import _build_cycle_lines
    ciclo = {"numero_ciclo": 7, "resultado": "COMPLETADO", "fecha_fin": "2026-10-26 10:00:00",
             "fecha_inicio": "2026-10-26 09:00:00",
             "avisos_ticket": json.dumps({"avisos": [{"clave": "ticket_ciclo.no_conforme_referencia",
                                                     "sensor": "Referencia"}]})}
    texto = "\n".join(_build_cycle_lines(ciclo, []))
    assert "NO CONFORME" in texto
    ciclo["avisos_ticket"] = None
    assert "NO CONFORME" not in "\n".join(_build_cycle_lines(ciclo, []))
