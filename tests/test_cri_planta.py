"""Tanda 35, CRI (docs/mis_plans/planeacion_cascada_integral.md §1.4 y §6.3):
criterio de liberación con la planta simulada (valores PROVISIONALES,
tests/helpers/planta_vapor.py). Tabla antes/después en
docs/informes/tanda35/planta_despues.md.

(a) Escenario de §1.4: esterilización de Líquidos 121 °C desde el inicio de la
    fase, modo chaqueta, 16 combinaciones de paso chaqueta → cámara, pérdida
    fija de cámara y llenado de chaqueta; mismos supuestos que el barrido
    tests/banco/cri_barrido_planta.py (se reutiliza su `correr`). La alpha.26
    queda fija como referencia (REFERENCIA_ALPHA26, de
    docs/informes/tanda35/base_planta.md).
(b) Ciclos completos: tests/test_t33_cas04_planta.py y tests/test_pam_planta.py
    (no se duplican aquí). Aquí solo: 134 °C sin CIC-16 en ciclo completo y la
    herencia de dp CALENTAMIENTO → ESTERILIZACION con el reset que hace
    CicloState al avanzar de fase (planta_vapor.simular no lo hace).

Criterios (§6.3): todo caso que completaba con la alpha.26 sigue completando;
ningún caso con aislamientos VCH-AIS que no tuviera; 134 °C sin CIC-16. Sin
xfail: cada caso tiene su resultado esperado explícito (ESPERADO_CRI) para que
cualquier cambio, en cualquier sentido, se vea. Los que siguen fallando son
límite físico de la planta: con vapor_chaqueta y vapor_camara abiertas desde el
primer instante (cota de lazo abierto, ningún control puede dar más) la cámara
también cae bajo CIC-04 o la Principal bajo la falla de temperatura.
"""
import logging

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.cycle_phases import corte_chaqueta_consigna as ccc
from autoclave.state_machine.cycle_phases.cascada_chaqueta import CascadaChaqueta
from tests.banco import cri_barrido_planta as cb
from tests.helpers import planta_vapor as pv

pytestmark = pytest.mark.req("CRI-01")

COMPLETADO = "COMPLETADO"
P_BAJA = "FALLO CIC-04 (P baja)"
T_BAJA = "FALLO CIC-04 (T baja)"

# (paso 1/s, pérdida kPa/s, llenado kPa/s): (resultado, P mín cámara, aisl., chaqueta máx)
REFERENCIA_ALPHA26 = {
    (0.1, 0.4, 4.0): (COMPLETADO, 209.9, 0, 217.6),
    (0.1, 0.4, 1.5): (COMPLETADO, 209.5, 0, 216.4),
    (0.1, 0.8, 4.0): (COMPLETADO, 209.4, 0, 223.2),
    (0.1, 0.8, 1.5): (T_BAJA, 205.8, 0, 215.7),
    (0.03, 0.4, 4.0): (COMPLETADO, 209.3, 0, 237.9),
    (0.03, 0.4, 1.5): (COMPLETADO, 207.7, 0, 233.1),
    (0.03, 0.8, 4.0): (COMPLETADO, 207.3, 0, 256.8),
    (0.03, 0.8, 1.5): (P_BAJA, 202.0, 0, 225.9),
    (0.015, 0.4, 4.0): (COMPLETADO, 208.2, 0, 268.9),
    (0.015, 0.4, 1.5): (COMPLETADO, 204.7, 0, 256.7),
    (0.015, 0.8, 4.0): (COMPLETADO, 203.8, 0, 305.5),
    (0.015, 0.8, 1.5): (P_BAJA, 200.5, 0, 228.2),
    (0.008, 0.4, 4.0): (COMPLETADO, 206.2, 0, 322.6),
    (0.008, 0.4, 1.5): (P_BAJA, 202.0, 0, 240.5),
    (0.008, 0.8, 4.0): (P_BAJA, 200.8, 0, 264.0),
    (0.008, 0.8, 1.5): (P_BAJA, 199.5, 0, 229.7),
}

# Resultado con CRI (commit 536f0b56), fijado por caso.
ESPERADO_CRI = {
    (0.1, 0.4, 4.0): COMPLETADO,
    (0.1, 0.4, 1.5): COMPLETADO,
    (0.1, 0.8, 4.0): COMPLETADO,
    (0.1, 0.8, 1.5): T_BAJA,      # límite físico
    (0.03, 0.4, 4.0): COMPLETADO,
    (0.03, 0.4, 1.5): COMPLETADO,
    (0.03, 0.8, 4.0): COMPLETADO,
    (0.03, 0.8, 1.5): P_BAJA,     # límite físico
    (0.015, 0.4, 4.0): COMPLETADO,
    (0.015, 0.4, 1.5): COMPLETADO,
    (0.015, 0.8, 4.0): COMPLETADO,
    (0.015, 0.8, 1.5): P_BAJA,    # límite físico
    (0.008, 0.4, 4.0): COMPLETADO,
    (0.008, 0.4, 1.5): P_BAJA,    # límite físico (transitorio)
    (0.008, 0.8, 4.0): P_BAJA,    # límite físico (transitorio)
    (0.008, 0.8, 1.5): P_BAJA,    # límite físico
}

LIMITE_FISICO = [c for c, r in ESPERADO_CRI.items() if r != COMPLETADO]
CASOS = list(REFERENCIA_ALPHA26)


def _id(caso):
    return "paso={}|perdida={}|llenado={}".format(*caso)


@pytest.fixture(autouse=True)
def _sin_log():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


def test_referencia_y_esperado_cubren_las_16_combinaciones():
    assert set(REFERENCIA_ALPHA26) == set(cb.combinaciones()) == set(ESPERADO_CRI)
    assert sum(1 for r in REFERENCIA_ALPHA26.values() if r[0] != COMPLETADO) == 6


# ── (a) Escenario de §1.4 ─────────────────────────────────────────────────

@pytest.mark.parametrize("caso", CASOS, ids=_id)
def test_barrido_cri_contra_alpha26(caso):
    r = cb.correr(pv, *caso)
    ref_res, _ref_pmin, ref_aisl, _ref_chq = REFERENCIA_ALPHA26[caso]
    # resultado fijado por caso (detecta un cambio en cualquier sentido)
    assert r["resultado"] == ESPERADO_CRI[caso], r["motivo"]
    # criterio 1: lo que completaba sigue completando
    if ref_res == COMPLETADO:
        assert r["completado"], r["motivo"]
        assert r["p_min_ester"] > r["p_cic04"]
    # criterio 2: ningún aislamiento VCH-AIS que no tuviera
    assert r["aislamientos"] <= ref_aisl
    # la chaqueta real nunca llega al corte D-CHQ (375)
    assert r["p_chq_max"] < 375.0


def _cota_lazo_abierto(paso, perdida, llenado, duracion_s=900.0):
    """Planta del barrido con vapor_chaqueta, vapor_camara y escape lento
    abiertos desde el primer instante (lo máximo que cualquier control puede
    entregar). Devuelve (P mínima de cámara, Principal mínima)."""
    estado = EstadoAutoclave()
    modulo = pv.ModuloEsDoble(estado)
    ajustes = dict(pv.AJUSTES_LIQUIDOS)
    ajustes.update(PASO_CAMARA=paso, PERDIDA_CAMARA=perdida, LLENADO_CHAQUETA=llenado)
    planta = pv.PlantaVapor(modulo, 75.0, True, ajustes=ajustes,
                            t_inicial=cb.T_CARGA_DEFECTO, t_sonda_inicial=cb.T_CARGA_DEFECTO,
                            p_camara_inicial=cb.P_CAMARA_INICIAL - 0.1,
                            p_chaqueta_inicial=cb.P_CHAQUETA_INICIAL)
    for salida in ("vapor_chaqueta", "vapor_camara", "descompresion_lenta"):
        modulo.do[EstadoAutoclave.map_do[salida] + 1] = True
    p_min, t_min = planta.p, planta.t_sonda - cb.DESFASE_SONDA_K
    for _ in range(int(duracion_s / pv.DT)):
        planta.paso()
        p_min = min(p_min, planta.p)
        t_min = min(t_min, planta.t_sonda - cb.DESFASE_SONDA_K)
    return p_min, t_min


@pytest.mark.parametrize("caso", LIMITE_FISICO, ids=_id)
def test_casos_que_fallan_son_limite_fisico(caso):
    """Ni con todo abierto desde el primer instante se sostiene: la cámara cae
    bajo CIC-04 (203,0) o la Principal bajo T_est − brecha_error (120,9)."""
    p_min, t_min = _cota_lazo_abierto(*caso)
    assert p_min < 203.0 or t_min < 120.9, (p_min, t_min)


# ── (b) 134 °C sin CIC-16 y herencia de dp en ciclo completo ─────────────

@pytest.mark.parametrize("caudal", [None, "abierto", "restrictivo"])
def test_134_sin_cic16(caudal):
    programa, planta_kw, limite = pv.escenario_t33("134", caudal, 1.0)
    r = pv.simular("chaqueta", programa, limite_s=limite, planta_kw=planta_kw)
    assert r.alarma is None or "CIC-16" not in r.alarma, r.motivo
    assert r.aislamientos <= 1
    if r.inicio_ester_s is not None:
        assert r.resultado == COMPLETADO, r.motivo


@pytest.mark.parametrize("carga,caudal", [("liquidos", "abierto"), ("liquidos", "restrictivo"),
                                          ("134", "abierto")])
def test_herencia_dp_en_ciclo_completo(monkeypatch, carga, caudal):
    """Con el reset de CicloState al avanzar de fase, ESTERILIZACION parte de
    max(dp que CALENTAMIENTO publicó, margen_chaqueta_est) (CRI-01 y corrección
    MEDIA-2) y el ciclo completa sin aislamientos. En Líquidos abierto
    CALENTAMIENTO deja ≈4 kPa (cerca de DP_MIN_KPA, por la bajada a
    saturación): ESTERILIZACION parte del margen."""
    reg = {}
    base = pv.EsterilizacionFase

    class _Ester(base):
        def update(self):
            if not self._inicializado and "dp_her" not in reg:
                previo = getattr(self.estado, "cascada_chaqueta", None)
                reg["dp_her"] = previo.get("dp") if isinstance(previo, dict) else None
                reg["margen"] = ccc.margen_kpa(self.cycle)
                self.reset()          # como CicloState al avanzar de fase
            r = super().update()
            if "dp0" not in reg and isinstance(self.estado.cascada_chaqueta, dict):
                reg["dp0"] = self.estado.cascada_chaqueta["dp"]
            return r

    monkeypatch.setattr(pv, "EsterilizacionFase", _Ester)
    programa, planta_kw, limite = pv.escenario_t33(carga, caudal, 1.0)
    r = pv.simular("chaqueta", programa, limite_s=limite, planta_kw=planta_kw)
    assert r.resultado == COMPLETADO, r.motivo
    assert r.aislamientos == 0
    assert reg["dp_her"] is not None
    # corrección MEDIA-2: nunca bajo margen_chaqueta_est
    assert reg["dp0"] == pytest.approx(max(reg["dp_her"], reg["margen"]), abs=0.1)


# ── Sensibilidad: dp heredado pequeño en el escenario de §1.4 ────────────
# HALLAZGO (no criterio de §6.3, que parte sin herencia: dp inicial =
# margen_chaqueta_est 20): con CRI (536f0b56), si ESTERILIZACION heredaba dp =
# 4 kPa (lo que CALENTAMIENTO publica en Líquidos abierto), los casos 10 y 11,
# que completaban con la alpha.26, fallaban. Con la corrección MEDIA-2
# (dp inicial = max(heredado, margen) = max(4, 20) = 20) el resultado es el de
# ESPERADO_CRI.
ESPERADO_DP_HEREDADO_4 = dict(ESPERADO_CRI)


@pytest.mark.parametrize("caso", CASOS, ids=_id)
def test_sensibilidad_dp_heredado_4(monkeypatch, caso):
    base = pv.EsterilizacionFase

    class _Heredado(base):
        def update(self):
            if not self._inicializado:
                self.estado.cascada_chaqueta = {"nivel": None, "consigna": None,
                                                "valvula": False, "dp": 4.0}
                self._cascada = CascadaChaqueta(dp_inicial=self._dp_inicial())
            return super().update()

    monkeypatch.setattr(pv, "EsterilizacionFase", _Heredado)
    r = cb.correr(pv, *caso)
    assert r["resultado"] == ESPERADO_DP_HEREDADO_4[caso], r["motivo"]
    assert r["aislamientos"] == 0


# ── MEDIA-A (segunda revisión): pérdida de suministro de vapor ───────────
# Envoltura propia (sin tocar planta_vapor.py): durante [INICIO, INICIO +
# DURACION) el llenado de chaqueta baja a LLENADO_PERDIDA y luego vuelve al
# del caso. Con llenado 0 la cámara cae a CIC-04 en todos los casos (sin
# suministro no hay forma de sostenerla: límite físico); con 0,8 kPa/s (20 %
# del normal) la cámara queda en «banda» bajo P_sp con la válvula ON y la
# chaqueta sin llegar: sin la corrección dp subía a 90 kPa y el caso 0,015
# terminaba en CIC-16 (6 aislamientos) y el 0,008 con 4 aislamientos.
INICIO_PERDIDA_S = 300.0
DURACION_PERDIDA_S = 150.0


def _correr_con_perdida(monkeypatch, caso, llenado_perdida):
    paso, perdida, llenado = caso
    base = pv.PlantaVapor

    class _ConPerdida(base):
        _pasos = 0

        def paso(self):
            t = self._pasos * pv.DT
            en_perdida = INICIO_PERDIDA_S <= t < INICIO_PERDIDA_S + DURACION_PERDIDA_S
            self.LLENADO_CHAQUETA = llenado_perdida if en_perdida else llenado
            self._pasos += 1
            super().paso()

    monkeypatch.setattr(pv, "PlantaVapor", _ConPerdida)
    return cb.correr(pv, paso, perdida, llenado)


CASOS_PERDIDA = [(0.03, 0.4, 4.0), (0.015, 0.4, 4.0), (0.008, 0.4, 4.0)]


@pytest.mark.parametrize("caso", CASOS_PERDIDA, ids=_id)
def test_media_a_perdida_de_suministro_degradado(monkeypatch, caso):
    r = _correr_con_perdida(monkeypatch, caso, 0.8)
    assert r["aislamientos"] == 0
    assert "CIC-15" not in r["resultado"] and "CIC-16" not in r["resultado"]
    assert r["resultado"] == COMPLETADO, r["motivo"]
    assert r["p_chq_max"] < 375.0


@pytest.mark.parametrize("caso", CASOS_PERDIDA, ids=_id)
def test_media_a_perdida_de_suministro_total(monkeypatch, caso):
    """Sin suministro 150 s la cámara cae a CIC-04 (límite físico); nunca
    aislamientos ni CIC-15/16."""
    r = _correr_con_perdida(monkeypatch, caso, 0.0)
    assert r["aislamientos"] == 0
    assert r["resultado"] == P_BAJA, r["motivo"]
