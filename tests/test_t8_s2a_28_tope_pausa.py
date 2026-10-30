"""Tanda 8 / S2a / D8-2.8 (tope de pausa; TMG-03 de la revisión Q1): si en una
misma exposición de ESTERILIZACION las pausas por falta de datos del módulo E/S
suman más de `pausa_max_esterilizacion_s` (parámetro del equipo, 30 s por
defecto, rango 5-120), el ciclo falla con un código propio, CIC-11
"Comunicación inestable en esterilización" (es/en)."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.alarms.catalogo import CATALOGO, CIC_11, Nivel
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.states.ciclo import CicloResultado
from tests.test_t2_p3_di_vencida import _ciclo

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"


@pytest.fixture
def reloj(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    return t


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _fase(config=None):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": None}
    estado.sensores_pres = {"pres_camara": None}
    estado.motivo_fallo = ""
    cycle = MagicMock()
    cycle.sensores = None
    cycle.get_param.side_effect = lambda s, p, default=None: (
        1.0 if p == "tiempo_esterilizacion" else default)
    fase = EsterilizacionFase(estado, MagicMock(), cycle, config if config is not None else _Config(),
                              MagicMock(), None)
    fase.reset()
    fase.update()                       # inicia el conteo
    return fase, estado


# ── parámetro del equipo ────────────────────────────────────────────────────

def test_parametro_de_fabrica():
    fabrica = json.loads((RAIZ / "config" / "global_params.json").read_text(encoding="utf-8"))
    e = fabrica["pausa_max_esterilizacion_s"]
    assert (e["value"], e["min"], e["max"], e["type"]) == (30, 5, 120, "int")


@pytest.mark.parametrize("lang", ["es", "en"])
def test_parametro_con_nombre_y_descripcion(lang):
    cat = json.loads((RAIZ / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
    assert cat["parametros_equipo"]["pausa_max_esterilizacion_s"].strip()
    assert cat["parametros_equipo_desc"]["pausa_max_esterilizacion_s"].strip()


# ── EsterilizacionFase ──────────────────────────────────────────────────────

def test_pausas_bajo_el_tope_no_fallan(reloj):
    fase, _ = _fase(_Config(pausa_max_esterilizacion_s=10))
    fase.pausar_exposicion(4.0)
    fase.pausar_exposicion(6.0)                         # suma 10: igual al tope
    assert fase.update() == FaseResult.EN_CURSO
    assert fase.pausa_total_s == pytest.approx(10.0)
    assert fase.alarma_fallo is None


def test_pausas_sobre_el_tope_fallan_con_cic11(reloj):
    fase, estado = _fase(_Config(pausa_max_esterilizacion_s=10))
    for _ in range(3):
        fase.pausar_exposicion(4.0)                     # suma 12 > 10
    assert fase.update() == FaseResult.FALLO
    codigo, valores = fase.alarma_fallo
    assert codigo == CIC_11
    assert valores["segundos"] == pytest.approx(12.0) and valores["maximo"] == 10
    fase.set_do.vapor_camara_off.assert_called()


def test_falla_aunque_no_haya_lectura_de_sensores(reloj):
    # la fase con sensores en None devuelve EN_CURSO: el tope va antes
    fase, _ = _fase(_Config(pausa_max_esterilizacion_s=5))
    fase.pausar_exposicion(6.0)
    assert fase.update() == FaseResult.FALLO


@pytest.mark.parametrize("valor", [None, "x", float("nan"), True])
def test_sin_parametro_valido_usa_30(reloj, valor):
    fase, _ = _fase(_Config(pausa_max_esterilizacion_s=valor))
    fase.pausar_exposicion(29.0)
    assert fase.update() == FaseResult.EN_CURSO
    fase.pausar_exposicion(2.0)
    assert fase.update() == FaseResult.FALLO


@pytest.mark.parametrize("valor, limite", [(1, 5), (500, 120)])
def test_fuera_de_rango_se_recorta(reloj, valor, limite):
    fase, _ = _fase(_Config(pausa_max_esterilizacion_s=valor))
    fase.pausar_exposicion(limite)
    assert fase.update() == FaseResult.EN_CURSO
    fase.pausar_exposicion(1.0)
    assert fase.update() == FaseResult.FALLO


def test_reset_de_la_fase_pone_el_total_en_cero(reloj):
    fase, _ = _fase(_Config(pausa_max_esterilizacion_s=10))
    fase.pausar_exposicion(8.0)
    fase.reset()
    assert fase.pausa_total_s == 0.0 and fase.alarma_fallo is None


# ── CicloState registra el código propio ───────────────────────────────────

def test_ciclo_registra_cic11_y_ejecuta_el_protocolo(reloj):
    ciclo, estado, am = _ciclo({})
    idx = next(i for i, f in enumerate(ciclo._fases) if f.name == "ESTERILIZACION")
    ciclo._fase_idx = idx
    fase = ciclo._fases[idx]
    fase.update = MagicMock(return_value=FaseResult.FALLO)
    fase.alarma_fallo = (CIC_11, {"segundos": 31.0, "maximo": 30})
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "FALLO_ESTERILIZACION"
    assert [i.codigo for i in am.activas()] == [CIC_11]
    assert estado.codigo_fallo == CIC_11
    ciclo._protocolo.ejecutar.assert_called_once_with()


def test_otra_falla_de_la_fase_sigue_con_cic04(reloj):
    ciclo, estado, am = _ciclo({})
    idx = next(i for i, f in enumerate(ciclo._fases) if f.name == "ESTERILIZACION")
    ciclo._fase_idx = idx
    fase = ciclo._fases[idx]
    fase.update = MagicMock(return_value=FaseResult.FALLO)
    estado.motivo_fallo = "Temperatura baja"
    ciclo.run()
    assert [i.codigo for i in am.activas()] == ["CIC-04"]


# ── catálogo ───────────────────────────────────────────────────────────────

def test_catalogo_cic11():
    d = CATALOGO[CIC_11]
    assert d.titulo == "Comunicación inestable en esterilización"
    assert d.nivel is Nivel.ALARMA and d.bloquea_inicio is True
    assert d.campos() == {"segundos", "maximo"}
    assert "NO está estéril" in d.accion


@pytest.mark.parametrize("lang", ["es", "en"])
def test_textos_cic11_en_el_catalogo_i18n(lang):
    cat = json.loads((RAIZ / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
    entrada = cat["alarmas"][CIC_11]
    assert entrada["titulo"].strip() and entrada["accion"].strip()
    texto = entrada["plantilla"].format(segundos=31.0, maximo=30)
    assert "{" not in texto
    if lang == "en":
        assert entrada["titulo"] == "Unstable communication during sterilization"
