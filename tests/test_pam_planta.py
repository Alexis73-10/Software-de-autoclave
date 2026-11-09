"""PAM (9-nov, planeacion_presion_add_margen.md §6.5): planta simulada
(tests/helpers/planta_vapor.py, valores PROVISIONALES) con la Principal
leyendo 0,6 K bajo la temperatura real de la sonda (PAM-H1: ciclos 26 y 27 de
SN260001), Líquidos e Instrumental 121, caudal chaqueta → cámara abierto y
restrictivo, modo chaqueta y modo cámara.

Criterio: llega a ESTABLE_PREESTERILIZACION y a ESTERILIZACION y termina
COMPLETADO; la cascada no arranca ESTERILIZACION en nivel «baja»; la presión
mínima de la exposición queda sobre el umbral de CIC-04 (Psat − 2); sin
aislamientos; P_trabajo dentro del tope.

Antes de PAM (dev, alpha.25) con la misma planta: Instrumental 121 no salía
de CALENTAMIENTO en ningún caso (timeout, ciclo 27) y Líquidos restrictivo en
modo chaqueta fallaba por no sostener la condición estable. Lo que sigue sin
cumplir queda xfail(strict=True) con su motivo (fuera del alcance de PAM)."""
import logging

import pytest

from autoclave.core.managers.catalogo_parametros import consigna_chaqueta
from autoclave.core.runtime.steam import p_saturacion_kpa
from tests.helpers import planta_vapor as pv

pytestmark = pytest.mark.req("PAM")

DESFASE_SONDA_K = 0.6
PROGRAMAS = {"liquidos": pv.PROGRAMA_LIQUIDOS,
             "instrumental_121": pv.RAIZ / "src" / "autoclave" / "cycles" / "factory"
             / "instrumental_121.json"}


@pytest.fixture(autouse=True)
def _sin_log():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


class _PlantaDesfase(pv.PlantaVapor):
    """La Principal (temp_camara) lee DESFASE_SONDA_K bajo la sonda real; las
    demás sondas sin cambio (temp_2_camara ≈ Tsat, como en el ciclo 27)."""

    def publicar(self, estado):
        super().publicar(estado)
        estado.sensores_temp["temp_camara"] = self.t_sonda - DESFASE_SONDA_K


def _correr(monkeypatch, programa, caudal, modo):
    registro = {"nivel_entrada": None, "p_trabajo": [], "tope": None}

    class _Ester(pv.EsterilizacionFase):
        def update(self):
            r = super().update()
            if registro["nivel_entrada"] is None and self._inicializado:
                cas = self.estado.cascada_chaqueta
                registro["nivel_entrada"] = cas.get("nivel") if isinstance(cas, dict) else "-"
            return r

    class _Cal(pv.CalentamientoFase):
        def update(self):
            r = super().update()
            if self.estado.presion_trabajo is not None:
                registro["p_trabajo"].append(self.estado.presion_trabajo)
            return r

    monkeypatch.setattr(pv, "PlantaVapor", _PlantaDesfase)
    monkeypatch.setattr(pv, "EsterilizacionFase", _Ester)
    monkeypatch.setattr(pv, "CalentamientoFase", _Cal)
    prog = pv._programa(PROGRAMAS[programa])
    ajustes = dict(pv.AJUSTES_LIQUIDOS) if programa == "liquidos" else {}
    ajustes.update(pv.VARIANTES_CAUDAL[caudal])
    t_est = prog.get_param("esterilizacion", "temperatura_esterilizacion")
    planta_kw = dict(ajustes=ajustes, p_chaqueta_inicial=consigna_chaqueta(
        t_est, prog.get_param("esterilizacion", "presion_add_esterilizacion")))
    r = pv.simular(modo, prog, limite_s=7200.0, monkeypatch=monkeypatch, planta_kw=planta_kw)
    t_obj = prog.get_param("calentamiento", "temperatura_calentamiento")
    registro["tope"] = (p_saturacion_kpa(t_obj)
                        + prog.get_param("calentamiento", "presion_add_calentamiento")
                        - (prog.get_param("calentamiento", "histeresis_cierre_camara") + 1.0))
    registro["p_cic04"] = p_saturacion_kpa(t_est) - prog.get_param(
        "esterilizacion", "brecha_error_presion")
    return r, registro


_NO_CUMPLE = {
    ("instrumental_121", "restrictivo", "chaqueta"):
        "fuera de alcance: la rampa no supera ≈207,7 kPa por el corte A14-M2 de la chaqueta "
        "(≈224 kPa) con caudal restrictivo (como el 134 °C excluido de CAS-04)",
    ("liquidos", "restrictivo", "chaqueta"):
        "caracterización: con caudal restrictivo la chaqueta no repone la pérdida de la cámara "
        "y la Principal (−0,6 K) cae bajo T_est − 0,1 en la exposición (antes de PAM no "
        "salía de CALENTAMIENTO)",
}

_CASOS = [(p, c, m) for p in PROGRAMAS for c in ("abierto", "restrictivo")
          for m in ("chaqueta", "camara")]


@pytest.mark.parametrize(
    "programa,caudal,modo",
    [pytest.param(*caso, marks=pytest.mark.xfail(strict=True, reason=_NO_CUMPLE[caso]))
     if caso in _NO_CUMPLE else caso for caso in _CASOS],
    ids=[f"{p}|{c}|{m}" for p, c, m in _CASOS])
def test_desfase_de_sonda_0_6_k_llega_a_esterilizar(monkeypatch, programa, caudal, modo):
    r, reg = _correr(monkeypatch, programa, caudal, modo)
    assert r.inicio_ester_s is not None, (r.resultado, r.motivo)
    assert r.resultado == "COMPLETADO", (r.resultado, r.motivo, r.alarma)
    assert reg["p_trabajo"], "sin presión de trabajo fijada"
    assert max(reg["p_trabajo"]) <= reg["tope"] + 1e-9
    assert r.p_min_ester > reg["p_cic04"]
    assert r.aislamientos == 0
    if modo == "chaqueta":
        assert reg["nivel_entrada"] != "baja"
