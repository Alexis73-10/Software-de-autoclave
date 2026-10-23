"""T4 (E2, tanda 2026-10-14): cámara segura con el sensor Principal, "NO ABRIR"
en /status y condición de inicio de ciclo (planeacion_fin_de_ciclo_y_puertas §5)."""

import math
from types import SimpleNamespace

import pytest

from autoclave.core.runtime.camara_segura import evaluar

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}


def _estado(pres=101.3, **temps):
    t = {"temp_camara": 40.0, "temp_2_camara": 40.0, "temp_ref": 40.0}
    t.update(temps)
    return SimpleNamespace(sensores_pres={"pres_camara": pres}, sensores_temp=t)


class _Config(dict):
    def get(self, k, default=None):
        return super().get(k, default)


def test_segura_en_rango():
    assert evaluar(_estado(), _Config(_CFG), None) == (True, "")


@pytest.mark.parametrize("pres,motivo", [
    (120.0, "Sobrepresión"), (80.0, "vacío"), (None, "presión"), (math.nan, "presión")])
def test_presion_fuera_o_ausente_no_es_segura(pres, motivo):
    segura, texto = evaluar(_estado(pres=pres), _Config(_CFG), None)
    assert segura is False and motivo in texto


@pytest.mark.parametrize("temp", [80.1, None, math.inf])
def test_temperatura_alta_o_ausente_no_es_segura(temp):
    segura, _ = evaluar(_estado(temp_camara=temp), _Config(_CFG), None)
    assert segura is False


def test_limite_exacto_es_seguro():
    assert evaluar(_estado(pres=111.3, temp_camara=80.0), _Config(_CFG), None)[0] is True


@pytest.mark.parametrize("falta", list(_CFG))
def test_sin_configuracion_falla_cerrada(falta):
    cfg = _Config({k: v for k, v in _CFG.items() if k != falta})
    segura, texto = evaluar(_estado(), cfg, None)
    assert segura is False and falta in texto


def test_usa_el_sensor_principal_del_programa():
    programa = SimpleNamespace(sensores={"temp_camara": "no_en_uso",
                                         "temp_2_camara": "principal", "temp_ref": "no_en_uso"})
    estado = _estado(temp_camara=30.0, temp_2_camara=95.0)
    assert evaluar(estado, _Config(_CFG), programa)[0] is False
    estado = _estado(temp_camara=None, temp_2_camara=30.0)    # temp_camara no en uso
    assert evaluar(estado, _Config(_CFG), programa)[0] is True


def test_principal_none_no_es_segura_aunque_otra_sonda_lea():
    programa = SimpleNamespace(sensores={"temp_camara": "no_en_uso",
                                         "temp_2_camara": "no_en_uso", "temp_ref": "principal"})
    assert evaluar(_estado(temp_ref=None), _Config(_CFG), programa)[0] is False


# ── /status: camara_segura y NO ABRIR ────────────────────────────────────────

import threading                                                    # noqa: E402
from unittest.mock import MagicMock                                 # noqa: E402
from fastapi.testclient import TestClient                           # noqa: E402
from autoclave.state_machine.machine.enum_global import GlobalState  # noqa: E402
from tests.backend_doble import cargar_servidor                     # noqa: E402


def _cliente(pres=101.3, temp=40.0, vigentes=True):
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.sensores_pres = {"pres_camara": pres}
    ctx.estado.sensores_temp = {"temp_camara": temp}
    ctx.config_manager = _Config(_CFG)
    ctx.profile = None
    ctx.programas_para_seguridad.return_value = []
    ctx.temp_max_tras_ciclo.return_value = None
    ctx.control_loop.datos_vigentes = vigentes
    # S9, revisión ★ pasada 3 (R3-M1): el NO ABRIR usa la presión vigente
    ctx.control_loop.presion_vigente = vigentes
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app)


def test_status_publica_camara_segura():
    datos = _cliente().get("/status").json()
    assert datos["camara_segura"] is True and datos["no_abrir"] is False
    assert datos["camara_segura_motivo"] == ""


def test_status_no_abrir_con_cámara_caliente():
    datos = _cliente(temp=95.0).get("/status").json()
    assert datos["camara_segura"] is False and datos["no_abrir"] is True
    assert "Temperatura" in datos["camara_segura_motivo"]


def test_status_no_abrir_con_datos_no_vigentes():
    # SAF-01 de T4: enlace caído = lecturas viejas = NO ABRIR
    datos = _cliente(vigentes=False).get("/status").json()
    assert datos["no_abrir"] is True and "no vigentes" in datos["camara_segura_motivo"]


def test_temp_max_del_ciclo_rige_tras_un_ciclo():
    # SAF-04 de T4: el menor entre el global (80 en la prueba) y el del ciclo
    assert evaluar(_estado(temp_camara=75.0), _Config(_CFG), None, temp_max_ciclo=70)[0] is False
    assert evaluar(_estado(temp_camara=65.0), _Config(_CFG), None, temp_max_ciclo=70)[0] is True


def test_status_no_abrir_sin_lectura():
    datos = _cliente(pres=None).get("/status").json()
    assert datos["no_abrir"] is True


# ── Condición de inicio (D-04) ───────────────────────────────────────────────

from tests.test_adenda_estados import _make                          # noqa: E402
from autoclave.state_machine.states.preparado import preparado_state  # noqa: E402


def _preparado(**overrides):
    obj, am, set_do = _make(preparado_state, None, **overrides)
    obj.config = _Config({**_CFG, "presion_empaque": 300, "tiempo_estable_alarma": 0,
                          "temp_segura_drenaje": 60.0, "rango_temp_drenaje": 5.0})
    obj.mantener_chaqueta = lambda: True
    obj.mantener_drenaje = lambda: True
    obj.mantener_presion_camara = lambda: True
    return obj


def test_preparado_no_listo_con_camara_caliente():
    assert _preparado(temp_camara=95.0).esta_preparado() is False


def test_preparado_listo_con_camara_segura():
    assert _preparado(temp_camara=40.0).esta_preparado() is True


def test_preparado_usa_los_programas_de_seguridad():
    obj = _preparado(temp_camara=40.0, temp_ref=95.0)
    referencia_principal = SimpleNamespace(sensores={"temp_camara": "no_en_uso",
                                                     "temp_2_camara": "no_en_uso",
                                                     "temp_ref": "principal"})
    obj.programas_seguridad = lambda: [referencia_principal]
    assert obj.esta_preparado() is False
